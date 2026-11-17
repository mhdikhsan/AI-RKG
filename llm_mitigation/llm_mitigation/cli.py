"""llm-mitigation command-line tool."""
from __future__ import annotations

import json
from pathlib import Path

import click

from . import apply as apply_mod
from . import review as review_mod
from . import run as run_mod
from .config import load_config, load_inputs, write_csv
from .shortlist import SHORTLIST_COLS, build_shortlist


@click.group()
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False), default=None,
              help="config.yaml (default: the one next to this package)")
@click.option("--model", default=None, help="override the model in config.yaml (e.g. claude-haiku-5-5)")
@click.pass_context
def main(ctx, config_path, model):
    """Propose mitigation->risk links with an LLM, for human review."""
    ctx.obj = load_config(config_path, {"model": model})


@main.command()
@click.pass_obj
def shortlist(cfg):
    """Deterministic top-k controls per risk (TF-IDF, no LLM) -> output/shortlist.csv"""
    risks, controls, groups = load_inputs(cfg)
    rows = build_shortlist(risks, controls, groups, cfg["shortlist"]["k"], cfg["shortlist"]["control_fields"])
    out = Path(cfg.path("output_dir")) / "shortlist.csv"
    write_csv(out, SHORTLIST_COLS, rows)
    n_risks = len({r["risk_id"] for r in rows})
    click.echo(f"shortlist: {len(rows)} rows for {n_risks} of {len(risks)} risks (k={cfg['shortlist']['k']}) -> {out}")


@main.command()
@click.option("--limit", type=int, default=None, help="only the first N risks")
@click.option("--exact", is_flag=True, help="count input tokens with the API's token-counting endpoint")
@click.pass_obj
def estimate(cfg, limit, exact):
    """Calls, approximate tokens and cost for the configured model. No generation call."""
    e = run_mod.estimate(cfg, limit, exact)
    click.echo(json.dumps(e, indent=2))


@main.command()
@click.option("--dry-run", is_flag=True, help="render prompts to output/prompts_preview/ without any API call")
@click.option("--limit", type=int, default=None, help="only the first N risks")
@click.pass_obj
def run(cfg, dry_run, limit):
    """One LLM call per risk with its shortlist -> output/candidates.csv (cached)."""
    if dry_run:
        n = run_mod.dry_run(cfg, limit)
        click.echo(f"dry run: {n} prompts written to {Path(cfg.path('output_dir')) / 'prompts_preview'}")
        return
    stats = run_mod.run(cfg, limit=limit, log=click.echo)
    click.echo(f"run: {json.dumps(stats, sort_keys=True)}")


@main.command("review-export")
@click.option("--xlsx", is_flag=True, help="write review_sheet.xlsx (with an accept/reject dropdown)")
@click.option("--force", is_flag=True, help="overwrite a sheet that already holds decisions")
@click.pass_obj
def review_export(cfg, xlsx, force):
    """output/review_sheet.csv with empty reviewer and decision columns."""
    click.echo(f"review sheet: {review_mod.export(cfg, xlsx=xlsx, force=force)}")


@main.command()
@click.option("--review", "review_path", type=click.Path(exists=True, dir_okay=False), required=True)
@click.pass_obj
def apply(cfg, review_path):
    """Keep decision=accept rows -> staging/accepted_mitigation_links.csv"""
    stats = apply_mod.apply(cfg, Path(review_path))
    click.echo(f"apply: {json.dumps(stats)} -> {cfg.path('accepted_out')}")


@main.command("all")
@click.option("--limit", type=int, default=None)
@click.option("--yes", is_flag=True, help="do not ask before calling the API")
@click.pass_context
def all_(ctx, limit, yes):
    """shortlist -> estimate -> (confirm) -> run -> review-export"""
    cfg = ctx.obj
    ctx.invoke(shortlist)
    e = run_mod.estimate(cfg, limit)
    click.echo(json.dumps(e, indent=2))
    if e["calls"] and not yes:
        click.confirm(f"Make {e['calls']} API calls with {cfg['model']} "
                      f"(about ${e['cost_usd_configured_model']})?", abort=True)
    ctx.invoke(run, dry_run=False, limit=limit)
    ctx.invoke(review_export, xlsx=False, force=False)


if __name__ == "__main__":
    main()
