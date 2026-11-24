"""llm-motif command-line tool."""
from __future__ import annotations

import json
from pathlib import Path

import click
from llm_mitigation.env import load_env

from . import check as check_mod
from . import review as review_mod
from . import stages
from .core import Vocab, load_cfg, stage_cfg
from .fake import get_provider

STAGES = click.Choice(["profile", "abstract"])


@click.group()
@click.option("--config", "config_path", type=click.Path(exists=True, dir_okay=False), default=None,
              help="config.yaml (default: the one next to this package)")
@click.option("--model", default=None, help="override the model in config.yaml (e.g. claude-opus-5-5, claude-haiku-5-5)")
@click.option("--source", type=click.Choice(["aiid", "avid"]), default=None,
              help="only this source (default: scope.sources in config.yaml)")
@click.option("--record-class", "record_classes", multiple=True,
              help="AVID record classes to use, repeatable (default: scope.avid_record_classes)")
@click.option("--per-source", "per_source", multiple=True, metavar="SOURCE=N",
              help="take the first N incidents of a source, repeatable, e.g. --per-source aiid=20 --per-source avid=10")
@click.pass_context
def main(ctx, config_path, model, source, record_classes, per_source):
    """Propose RiskMotifs from AIID incidents and AVID records with an LLM, for human review."""
    load_env()                                   # ANTHROPIC_API_KEY etc. from the repository's .env
    ctx.obj = load_cfg(config_path, {"model": model})
    if source:
        ctx.obj["scope"]["sources"] = [source]
    if record_classes:
        ctx.obj["scope"]["avid_record_classes"] = list(record_classes)
    if per_source:
        per = {}
        for item in per_source:
            src, _, n = item.partition("=")
            if src not in ("aiid", "avid") or not n.isdigit():
                raise click.BadParameter(f"{item!r}: expected aiid=N or avid=N", param_hint="--per-source")
            per[src] = int(n)
        ctx.obj["scope"]["sources"] = sorted(per)
        ctx.obj["scope"]["per_source"] = per


@main.command()
@click.option("--stage", type=STAGES, default="profile")
@click.option("--limit", type=int, default=None, help="only the first N incidents (profile) or groups (abstract)")
@click.pass_obj
def estimate(cfg, stage, limit):
    """Calls, approximate tokens and cost for one stage. No API call."""
    click.echo(json.dumps(stages.estimate(cfg, Vocab(), stage, limit), indent=2))


@main.command()
@click.option("--stage", type=STAGES, required=True)
@click.option("--dry-run", is_flag=True, help="render prompts to output/prompts_preview/<stage>/ without any API call")
@click.option("--limit", type=int, default=None)
@click.pass_obj
def run(cfg, stage, dry_run, limit):
    """profile: one call per incident -> output/profiles.jsonl; abstract: one call per group -> output/motifs.jsonl"""
    vocab = Vocab()
    if dry_run:
        n = stages.dry_run(cfg, vocab, stage, limit)
        click.echo(f"dry run: {n} prompts written to {Path(cfg.path('output_dir')) / 'prompts_preview' / stage}")
        return
    provider = get_provider(stage_cfg(cfg, stage))   # Claude with this stage's effort level
    fn = stages.run_profiles if stage == "profile" else stages.run_motifs
    click.echo(f"run {stage}: {json.dumps(fn(cfg, provider, vocab, limit, log=click.echo), sort_keys=True)}")


@main.command()
@click.pass_obj
def group(cfg):
    """General groups (shape + top risk) and specific groups (shape + context value) -> output/groups.csv (no LLM)."""
    rows = stages.group_profiles(cfg)
    for level in ("general", "specific"):
        lv = [r for r in rows if r["level"] == level]
        kept = [r for r in lv if r["abstracted"] == "yes"]
        click.echo(f"group: {level}: {len(lv)} groups, {len(kept)} will be abstracted")


@main.command()
@click.pass_obj
def check(cfg):
    """Behaviour test with the pipeline's MotifDetectionShape -> output/check.csv"""
    click.echo(f"check: {json.dumps(check_mod.run_check(cfg))}")


@main.command("review-export")
@click.option("--xlsx", is_flag=True, help="write review_sheet.xlsx (with an accept/reject dropdown)")
@click.option("--force", is_flag=True, help="overwrite a sheet that already holds decisions")
@click.pass_obj
def review_export(cfg, xlsx, force):
    """output/review_sheet.csv: one row per motif proposal, empty reviewer and decision columns."""
    click.echo(f"review sheet: {review_mod.export(cfg, xlsx=xlsx, force=force)}")


@main.command()
@click.option("--review", "review_path", type=click.Path(exists=True, dir_okay=False), required=True)
@click.pass_obj
def apply(cfg, review_path):
    """Accepted motifs -> staging/accepted_motif*.csv (mapped by the main pipeline with RML)."""
    click.echo(f"apply: {json.dumps(review_mod.apply(cfg, Path(review_path)))}")


@main.command("all")
@click.option("--limit", type=int, default=None, help="only the first N incidents")
@click.option("--yes", is_flag=True, help="do not ask before calling the API")
@click.pass_context
def all_(ctx, limit, yes):
    """estimate -> (confirm) -> profile -> group -> estimate -> (confirm) -> abstract -> check -> review-export"""
    cfg, vocab = ctx.obj, Vocab()
    for stage in ("profile", "abstract"):
        if stage == "abstract":
            ctx.invoke(group)
        e = stages.estimate(cfg, vocab, stage, limit if stage == "profile" else None)
        click.echo(json.dumps(e, indent=2))
        if e["calls"] and not yes and cfg["provider"] != "fake":
            click.confirm(f"Stage {stage}: make {e['calls']} API calls with {cfg['model']} "
                          f"(about ${e['cost_usd_configured_model']})?", abort=True)
        provider = get_provider(stage_cfg(cfg, stage))   # Claude with this stage's effort level
        fn = stages.run_profiles if stage == "profile" else stages.run_motifs
        click.echo(f"run {stage}: {json.dumps(fn(cfg, provider, vocab, limit if stage == 'profile' else None, log=click.echo))}")
    ctx.invoke(check)
    ctx.invoke(review_export, xlsx=False, force=False)


if __name__ == "__main__":
    main()
