"""Regressions for source-selection bugs found during independent review."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/data-to-app/scripts"))
from data_to_app.build import build_app  # noqa: E402
from data_to_app.engine import Store  # noqa: E402


@unittest.skipUnless(importlib.util.find_spec("openpyxl"), "Optional XLSX reader is not installed")
class WorksheetSelectionTests(unittest.TestCase):
    def setUp(self):
        import openpyxl

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.workbook_path = self.folder / "roster.xlsx"
        self.app = self.folder / "app"
        self.book = openpyxl.Workbook()
        self.addCleanup(self.book.close)
        archive = self.book.active
        archive.title = "Archive"
        archive.append(["id", "status"])
        archive.append(["archived-person", "archived"])
        current = self.book.create_sheet("Current")
        current.append(["id", "status"])
        current.append(["current-person", "new"])
        self.book.save(self.workbook_path)
        model = self.folder / "model.json"
        model.write_text(json.dumps({"version": 1, "title": "Current roster", "tables": [{
            "id": "roster", "source": "roster.xlsx", "sheet": "Current",
            "columns": ["id", "status"], "key": ["id"], "editable": ["status"],
        }]}), encoding="utf-8")
        build_app(self.folder, self.app, model)
        self.book["Current"]["B2"] = "updated"
        self.book.save(self.workbook_path)

    def cli_import(self, *arguments):
        result = subprocess.run([
            sys.executable, str(ROOT / "skills/data-to-app/scripts/dta.py"),
            "import", str(self.app), "--table", "roster", "--file", str(self.workbook_path),
            *arguments,
        ], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_cli_import_uses_models_configured_sheet_by_default(self):
        preview = self.cli_import()
        self.assertEqual(preview["counts"]["new"], 0)
        self.assertEqual(preview["counts"]["updated"], 1)
        self.assertEqual(preview["counts"]["missing"], 0)
        self.cli_import("--apply")
        with Store(self.app / ".data/app.sqlite") as store:
            rows = store.rows("roster")["rows"]
        self.assertEqual([row["values"] for row in rows], [{"id": "current-person", "status": "updated"}])

    def test_explicit_cli_sheet_remains_a_deliberate_override(self):
        preview = self.cli_import("--sheet", "Archive")
        self.assertEqual(preview["counts"]["new"], 1)
        self.assertEqual(preview["counts"]["missing"], 1)


if __name__ == "__main__":
    unittest.main()
