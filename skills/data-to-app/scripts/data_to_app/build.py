"""Generate a self-contained local application from an explicit data model."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import tempfile

from .engine import DataError, Store
from .io import read_table

VERSION = "0.1.0"
SKILL_ROOT = Path(__file__).resolve().parents[2]


def read_manifest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256_000:
        raise DataError("Use a regular model.json file smaller than 256 KB.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise DataError(f"Cannot read model.json: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise DataError("The model must be an object with version: 1.")
    if not isinstance(value.get("tables"), list) or not value["tables"]:
        raise DataError("The model needs at least one table.")
    return value


def load_sources(input_path, manifest):
    """Read only the explicit model sources, all contained in the input directory."""
    input_path = Path(input_path).absolute()
    if input_path.is_symlink() or not input_path.exists():
        raise DataError("Input must be an existing regular file or directory, not a symlink.")
    base = (input_path if input_path.is_dir() else input_path.parent).resolve()
    sources = {}
    seen = set()
    for item in manifest["tables"]:
        if not isinstance(item, dict):
            raise DataError("Every model table must be an object.")
        table_id = item.get("id", "")
        if not isinstance(table_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", table_id):
            raise DataError("Use lowercase table IDs, e.g. products or order-lines.")
        if table_id in seen:
            raise DataError(f"Duplicate table ID: {table_id}")
        seen.add(table_id)
        source = item.get("source")
        if source is None and input_path.is_file() and len(manifest["tables"]) == 1:
            source = input_path.name
        source = source or f"{table_id}.csv"
        if not isinstance(source, str) or Path(source).is_absolute():
            raise DataError(f"Source for {table_id} must be relative to the input directory.")
        candidate = base / source
        # Inspect each lexical component before resolving; a symlinked parent is also unsafe.
        current = base
        for part in Path(source).parts:
            current = current / part
            if current.is_symlink():
                raise DataError(f"Symlink sources are unsupported: {source}")
        path = candidate.resolve()
        if not path.is_relative_to(base):
            raise DataError(f"Source escapes the input directory: {source}")
        table = read_table(path, sheet=item.get("sheet"))
        table["source"] = source
        if not item.get("columns"):
            item["columns"] = table["columns"]
        sources[table_id] = table
    return sources


def build_app(input_path, output_path, manifest_path):
    manifest = read_manifest(manifest_path)
    sources = load_sources(input_path, manifest)
    output = Path(output_path).absolute()
    if output.exists() or output.is_symlink():
        raise DataError(f"Output already exists: {output}. Choose a new directory.")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise DataError("The output parent must be an existing directory.")
    temp = Path(tempfile.mkdtemp(prefix=".dta-build-", dir=output.parent))
    try:
        (temp / ".data").mkdir(mode=0o700)
        store = Store(temp / ".data" / "app.sqlite")
        try:
            store.bootstrap(manifest, sources)
            summary = store.summary()
        finally:
            close = getattr(store, "close", None)
            if close:
                close()
        runtime = temp / "data_to_app"
        runtime.mkdir()
        for name in ("__init__.py", "engine.py", "io.py", "server.py"):
            shutil.copyfile(Path(__file__).parent / name, runtime / name)
        shutil.copytree(SKILL_ROOT / "assets" / "app", temp / "assets")
        (temp / "inputs").mkdir()
        for table_id, table in sources.items():
            # Preserve a normalized source snapshot without altering original inputs.
            import csv
            with (temp / "inputs" / f"{table_id}.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=table["columns"])
                writer.writeheader()
                writer.writerows(table["rows"])
        (temp / "model.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (temp / "app.py").write_text(
            '"""Run this local Data to App workspace."""\n'
            'from pathlib import Path\nfrom data_to_app.server import main\n\n'
            'if __name__ == "__main__":\n    main(Path(__file__).resolve().parent)\n', encoding="utf-8")
        shutil.copyfile(SKILL_ROOT / "LICENSE", temp / "LICENSE")
        (temp / "requirements-xlsx.txt").write_text("openpyxl==3.1.5\ndefusedxml==0.7.1\net-xmlfile==2.0.0\n", encoding="utf-8")
        (temp / ".gitignore").write_text(".data/\ninputs/\n__pycache__/\n.venv/\n", encoding="utf-8")
        (temp / "README.md").write_text(
            f'# {manifest.get("title", "Data workspace")}\n\n'
            'Run `python3 app.py --port 8765` and open the printed local URL.\n\n'
            'CSV import and this app use Python 3.10+ standard library. For XLSX uploads, '
            'install `requirements-xlsx.txt` in your environment.\n\n'
            'Your SQLite database in `.data/` contains imported records and local edits. '
            'Back up the entire app directory before removing or moving it. '
            'The app binds to loopback and is intended for one local operator.\n\n'
            'Use the Import preview before applying a complete source snapshot. '
            'Missing records are retained; conflicts preserve your local value until resolved. '
            'Export produces active effective values with spreadsheet-formula guarding.\n', encoding="utf-8")
        temp.rename(output)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return {"output": str(output), "version": VERSION, "summary": summary,
            "run": f'python3 "{output / "app.py"}" --port 8765'}


def build_demo(output_path):
    preset = SKILL_ROOT / "assets" / "examples" / "inventory"
    return build_app(preset / "initial", output_path, preset / "model.json")
