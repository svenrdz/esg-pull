from __future__ import annotations
from typing import Optional

import rich
import click

from esgpull import Context
from esgpull.cli.decorators import args, opts
from esgpull.cli.utils import totable, load_facets


@click.command()
@opts.distrib
@opts.dry_run
@opts.date
@opts.file
@opts.since
@opts.latest
@opts.data_node
@opts.one
@opts.options
@opts.replica
@opts.selection_file
@opts.slice
@opts.zero
@args.facets
def search(
    facets: list[str],
    date: bool,
    data_node: bool,
    distrib: bool,
    dry_run: bool,
    file: bool,
    latest: Optional[bool],
    replica: Optional[bool],
    selection_file: Optional[str],
    since: Optional[str],
    options: list[str],
    one: bool,
    zero: bool,
    slice_: slice,
) -> None:
    """
    Search datasets/files on ESGF

    More info
    """

    # TODO: bug with slice_:
    # -> numeric ids are not consistent due to sort by instance_id
    ctx = Context(distrib=distrib, latest=latest, since=since, replica=replica)
    if zero:
        slice_ = slice(0, 0)
    elif one:
        slice_ = slice(0, 1)
    offset = slice_.start
    size = slice_.stop - slice_.start
    load_facets(ctx, facets, selection_file)
    if file:
        hits = ctx.file_hits
    else:
        hits = ctx.hits
    if dry_run:
        queries = ctx._build_queries_search(
            hits, file=file, max_results=size, offset=offset
        )
        rich.print(queries)
    elif options:
        ctx.query.facets = options
        results = ctx.options()
        rich.print(results)
    else:
        results = ctx.search(file=file, max_results=size, offset=offset)
        nb = sum(hits)
        item_type = "file" if file else "dataset"
        click.echo(f"Found {nb} {item_type}{'s' if nb > 1 else ''}.")
        if len(results):
            rich.print(totable(results, data_node, date, slice_))