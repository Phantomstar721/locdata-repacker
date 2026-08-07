from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence, Tuple

from .format import (
    ENCODING_LABELS,
    SUPPORTED_ENCODINGS,
    LocdataFormatError,
    pack_locdata,
    read_editable,
    unpack_locdata,
    write_editable,
)


def unpack_file(source: Path, target: Path, encoding: Optional[str] = None) -> Tuple[int, str]:
    document = unpack_locdata(source, encoding)
    write_editable(document, target)
    return len(document.entries), document.encoding


def repack_file(source: Path, target: Path) -> Tuple[int, str]:
    document = read_editable(source)
    pack_locdata(document, target)
    return len(document.entries), document.encoding


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unpack and repack Fantasy Wars locdata.md files.")
    subparsers = parser.add_subparsers(dest="operation")
    unpack = subparsers.add_parser("unpack", help="Convert locdata.md to editable JSON text")
    unpack.add_argument("source", type=Path)
    unpack.add_argument("-o", "--output", type=Path)
    unpack.add_argument(
        "-e",
        "--encoding",
        choices=SUPPORTED_ENCODINGS,
        help="Override the detected code page (default: detect automatically).",
    )
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
            count, encoding = unpack_file(args.source, target, args.encoding)
            source_of_choice = "forced" if args.encoding else "detected"
            print("Unpacked {:,} entries to {}".format(count, target))
            print("Encoding ({}): {}".format(source_of_choice, ENCODING_LABELS[encoding]))
        else:
            target = args.output or args.source.with_name("locdata.md")
            count, encoding = repack_file(args.source, target)
            print("Repacked {:,} entries to {}".format(count, target))
            print("Encoding: {}".format(ENCODING_LABELS[encoding]))
    except (OSError, LocdataFormatError) as exc:
        print("Error: {}".format(exc))
        return 1
    return 0

