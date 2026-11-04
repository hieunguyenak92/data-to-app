#!/usr/bin/env python3
"""Data to App: inspect data, test relationships and build portable local apps."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from data_to_app.build import build_app, build_demo
from data_to_app.engine import DataError, Store, probe_join, profile_table
from data_to_app.io import discover_sources, read_table


def emit(value, path=None):
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path:
        target = Path(path)
        with target.open("x", encoding="utf-8") as stream:
            stream.write(content)
    else:
        sys.stdout.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Profile source values and candidate identities.")
    inspect.add_argument("input")
    inspect.add_argument("--out")
    inspect.add_argument("--sheet", help="XLSX worksheet name (single file only).")
    build = commands.add_parser("build", help="Generate a self-contained local application.")
    build.add_argument("input")
    build.add_argument("--out", required=True)
    build.add_argument("--manifest", required=True)
    demo = commands.add_parser("demo", help="Build the synthetic inventory example.")
    demo.add_argument("--out", required=True)
    join = commands.add_parser("join-check", help="Probe relationship cardinality before using a join.")
    join.add_argument("left")
    join.add_argument("right")
    join.add_argument("--left-key", required=True, help="Comma-separated column names.")
    join.add_argument("--right-key", required=True, help="Comma-separated column names.")
    imp = commands.add_parser("import", help="Preview a full table snapshot; --apply commits it.")
    imp.add_argument("app")
    imp.add_argument("--table", required=True)
    imp.add_argument("--file", required=True)
    imp.add_argument("--sheet")
    imp.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            paths = discover_sources(args.input)
            if args.sheet and len(paths) != 1:
                raise DataError("Use --sheet with one XLSX file.")
            profiles = []
            for path in paths:
                table = read_table(path, sheet=args.sheet)
                profiles.append({"source": str(path), **profile_table(table)})
            emit({"tables": profiles, "note": "Key/type suggestions are observations, not business rules. Confirm identity and row grain before building."}, args.out)
        elif args.command == "build":
            emit(build_app(args.input, args.out, args.manifest))
        elif args.command == "demo":
            emit(build_demo(args.out))
        elif args.command == "join-check":
            emit(probe_join(read_table(args.left), read_table(args.right),
                [part.strip() for part in args.left_key.split(",")],
                [part.strip() for part in args.right_key.split(",")]))
        elif args.command == "import":
            root = Path(args.app).resolve()
            database = root / ".data" / "app.sqlite"
            if not database.is_file() or database.is_symlink():
                raise DataError("Choose an existing generated app with .data/app.sqlite.")
            store = Store(database)
            try:
                model = next((item for item in store.tables() if item["id"] == args.table), None)
                if model is None:
                    raise DataError("Choose an existing table for this import.")
                sheet = args.sheet if args.sheet is not None else model.get("sheet")
                table = read_table(args.file, sheet=sheet)
                preview = store.preview_import(args.table, table)
                result = store.apply_import(args.table, table, preview["revision"]) if args.apply else preview
                emit({"applied": args.apply, **result})
            finally:
                close = getattr(store, "close", None)
                if close:
                    close()
    except (DataError, OSError, ValueError) as exc:
        sys.stderr.write(f"Data to App: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
