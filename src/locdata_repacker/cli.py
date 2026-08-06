from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from .format import (
    LocdataFormatError,
    pack_locdata,
    read_editable,
    unpack_locdata,
    write_editable,
)


def unpack_file(source: Path, target: Path) -> int:
    document = unpack_locdata(source)
    write_editable(document, target)
    return len(document.entries)


def repack_file(source: Path, target: Path) -> int:
    document = read_editable(source)
    pack_locdata(document, target)
    return len(document.entries)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unpack and repack Fantasy Wars locdata.md files.")
    subparsers = parser.add_subparsers(dest="operation")
    unpack = subparsers.add_parser("unpack", help="Convert locdata.md to editable JSON text")
    unpack.add_argument("source", type=Path)
    unpack.add_argument("-o", "--output", type=Path)
    repack = subparsers.add_parser("repack", help="Rebuild locdata.md from edited JSON text")
    repack.add_argument("source", type=Path)
    repack.add_argument("-o", "--output", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if not args.operation:
        from .gui import run_gui

        run_gui()
        return 0
    try:
        if args.operation == "unpack":
            target = args.output or args.source.with_suffix(".txt")
            count = unpack_file(args.source, target)
            print("Unpacked {:,} entries to {}".format(count, target))
        else:
            target = args.output or args.source.with_name("locdata.md")
            count = repack_file(args.source, target)
            print("Repacked {:,} entries to {}".format(count, target))
    except (OSError, LocdataFormatError) as exc:
        print("Error: {}".format(exc))
        return 1
    return 0

