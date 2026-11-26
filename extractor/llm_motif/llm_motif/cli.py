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
    load_env()                                 
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
    click.echo(json.dumps(stages.estimate(cfg, Vocab(), stage, limit), indent=2))


@main.command()
@click.option("--stage", type=STAGES, required=True)
@click.option("--dry-run", is_flag=True, help="render prompts to output/prompts_preview/<stage>/ without any API call")
@click.option("--limit", type=int, default=None)
@click.pass_obj
def run(cfg, stage, dry_run, limit):
    vocab = Vocab()
    if dry_run:
        n = stages.dry_run(cfg, vocab, stage, limit)
        click.echo(f"dry run: {n} prompts written to {Path(cfg.path('output_dir')) / 'prompts_preview' / stage}")
        return
    provider = get_provider(stage_cfg(cfg, stage))  
    fn = stages.run_profiles if stage == "profile" else stages.run_motifs
    click.echo(f"run {stage}: {json.dumps(fn(cfg, provider, vocab, limit, log=click.echo), sort_keys=True)}")


@main.command()
@click.pass_obj
def group(cfg):
    rows = stages.group_profiles(cfg)
    for level in ("general", "specific"):
        lv = [r for r in rows if r["motif_level"] == level]
        kept = [r for r in lv if r["sent_to_llm"] == "yes"]
        click.echo(f"group: {level}: {len(lv)} groups, {len(kept)} sent to the LLM")


@main.command()
@click.pass_obj
def check(cfg):
    click.echo(f"check: {json.dumps(check_mod.run_check(cfg))}")


@main.command("review-export")
@click.option("--xlsx", is_flag=True, help="write an .xlsx sheet (with an accept/reject dropdown)")
@click.option("--force", is_flag=True, help="overwrite a sheet that already holds decisions")
@click.option("--reviewer", default=None,
              help="write this reviewer's own sheet, output/review_sheet_<name>.csv, with the reviewer column filled")
@click.pass_obj
def review_export(cfg, xlsx, force, reviewer):
    click.echo(f"review sheet: {review_mod.export(cfg, xlsx=xlsx, force=force, reviewer=reviewer)}")


REVIEWS = click.option("--review", "review_paths", type=click.Path(exists=True, dir_okay=False), multiple=True,
                       required=True, help="a filled review sheet; repeat for several reviewers")


@main.command("review-status")
@REVIEWS
@click.pass_obj
def review_status(cfg, review_paths):
    click.echo(json.dumps(review_mod.status(cfg, [Path(p) for p in review_paths]), indent=2))


@main.command()
@REVIEWS
@click.pass_obj
def apply(cfg, review_paths):
    click.echo(f"apply: {json.dumps(review_mod.apply(cfg, [Path(p) for p in review_paths]))}")


@main.command("all")
@click.option("--limit", type=int, default=None, help="only the first N incidents")
@click.option("--yes", is_flag=True, help="do not ask before calling the API")
@click.pass_context
def all_(ctx, limit, yes):
    cfg, vocab = ctx.obj, Vocab()
    for stage in ("profile", "abstract"):
        if stage == "abstract":
            ctx.invoke(group)
        e = stages.estimate(cfg, vocab, stage, limit if stage == "profile" else None)
        click.echo(json.dumps(e, indent=2))
        if e["calls"] and not yes and cfg["provider"] != "fake":
            click.confirm(f"Stage {stage}: make {e['calls']} API calls with {cfg['model']} "
                          f"(about ${e['cost_usd_configured_model']})?", abort=True)
        provider = get_provider(stage_cfg(cfg, stage))  
        fn = stages.run_profiles if stage == "profile" else stages.run_motifs
        click.echo(f"run {stage}: {json.dumps(fn(cfg, provider, vocab, limit if stage == 'profile' else None, log=click.echo))}")
    ctx.invoke(check)
    ctx.invoke(review_export, xlsx=False, force=False, reviewer=None)


if __name__ == "__main__":
    main()
