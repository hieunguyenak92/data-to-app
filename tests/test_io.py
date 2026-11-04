import importlib.util
import io
import sys
import tempfile
import unittest
import zipfile
from xml.etree import ElementTree
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/data-to-app/scripts"))
from data_to_app.engine import DataError
from data_to_app.io import discover_sources, read_table


class CSVTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, content, name="input.csv"):
        path = self.folder / name
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return path

    def test_bom_delimiter_multiline_and_leading_zero_values(self):
        table = read_table(self.write('\ufeffsku;name;notes\r\n001;"Pen; blue";"line one\nline two"\r\n'))
        self.assertEqual(table["columns"], ["sku", "name", "notes"])
        self.assertEqual(table["rows"][0], {"sku": "001", "name": "Pen; blue", "notes": "line one\nline two"})
        self.assertEqual(len(table["file_digest"]), 64)

    def test_blank_records_are_explicitly_skipped(self):
        table = read_table(self.write("id,name\n1,one\n,\n\n2,two\n"))
        self.assertEqual(len(table["rows"]), 2)
        self.assertTrue(table["warnings"])

    def test_invalid_headers_and_malformed_rows(self):
        for content in ("", "id,id\n1,2", "id, id \n1,2", "id,\n1,2", "id,name\n1,a,extra", 'id,name\n1,"unterminated'):
            with self.subTest(content=content):
                with self.assertRaises(DataError):
                    read_table(self.write(content))

    def test_encoding_and_nul_reject_without_lossy_replacement(self):
        for content in (b"id,name\n1,\xff", b"id,name\n1,a\x00"):
            with self.assertRaises(DataError):
                read_table(self.write(content))

    def test_file_row_and_cell_limits(self):
        path = self.write("id,name\n1,test\n")
        with patch("data_to_app.io.MAX_FILE_BYTES", 4):
            with self.assertRaises(DataError):
                read_table(path)
        with patch("data_to_app.io.MAX_ROWS", 1):
            with self.assertRaises(DataError):
                read_table(self.write("id,name\n1,a\n2,b\n"))
        with patch("data_to_app.io.MAX_CELL", 2):
            with self.assertRaises(DataError):
                read_table(self.write("id,name\n1,longvalue\n"))

    def test_discovery_is_top_level_and_rejects_symlink_sources(self):
        path = self.write("id\n001\n", "a.csv")
        self.write("ignored", "note.txt")
        nested = self.folder / "nested"
        nested.mkdir()
        (nested / "hidden.csv").write_text("id\n2")
        self.assertEqual(discover_sources(self.folder), [path])
        link = self.folder / "alias.csv"
        try:
            link.symlink_to(path)
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic link creation unavailable")
        with self.assertRaises(DataError):
            read_table(link)
        with self.assertRaises(DataError):
            discover_sources(self.folder)

    def test_empty_directory_and_unsupported_extension(self):
        with self.assertRaises(DataError):
            discover_sources(self.folder)
        with self.assertRaises(DataError):
            read_table(self.write("id\n1", "data.xls"))

    def test_xlsx_preflight_rejects_xml_entities_before_optional_import(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("xl/workbook.xml", '<!DOCTYPE x [<!ENTITY e "x">]><x>&e;</x>')
        with self.assertRaisesRegex(DataError, "entities"):
            read_table(self.write(output.getvalue(), "unsafe.xlsx"))

    def test_xlsx_preflight_rejects_expansion_limit(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", "x" * 100)
        with patch("data_to_app.io.MAX_ZIP_BYTES", 10):
            with self.assertRaisesRegex(DataError, "expanded"):
                read_table(self.write(output.getvalue(), "large.xlsx"))

    def test_xlsx_dependency_failure_is_actionable(self):
        if importlib.util.find_spec("openpyxl") is not None:
            self.skipTest("Optional dependency available; real XLSX cases cover this interpreter")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("xl/workbook.xml", "<x/>")
        with self.assertRaisesRegex(DataError, "optional openpyxl"):
            read_table(self.write(output.getvalue(), "data.xlsx"))


@unittest.skipUnless(importlib.util.find_spec("openpyxl") is not None, "openpyxl optional dependency unavailable")
class XLSXTests(unittest.TestCase):
    setUp = CSVTests.setUp
    tearDown = CSVTests.tearDown

    def workbook(self):
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = "Stock"
        return book, sheet

    def save(self, book):
        path = self.folder / "data.xlsx"
        book.save(path)
        book.close()
        return path

    def test_formatted_identifiers_dates_and_numeric_warning(self):
        book, sheet = self.workbook()
        sheet.append(["sku", "date", "rate"])
        sheet.append([12, date(2026, 11, 4), .15])
        sheet["A2"].number_format = "00000"
        sheet["C2"].number_format = "0%"
        table = read_table(self.save(book))
        self.assertEqual(table["rows"][0]["sku"], "00012")
        self.assertTrue(table["rows"][0]["date"].startswith("2026-11-04"))
        self.assertEqual(table["rows"][0]["rate"], "0.15")
        self.assertTrue(any("review units" in warning for warning in table["warnings"]))

    def test_uncached_formula_rejects_instead_of_inventing_value(self):
        book, sheet = self.workbook()
        sheet.append(["id", "total"])
        sheet.append(["001", "=1+2"])
        with self.assertRaisesRegex(DataError, "no cached value"):
            read_table(self.save(book))

    def test_cached_formula_is_read_and_disclosed(self):
        book, sheet = self.workbook()
        sheet.append(["id", "total"])
        sheet.append(["001", "=1+2"])
        path = self.save(book)
        updated = io.BytesIO()
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(updated, "w") as target:
            for item in source.infolist():
                content = source.read(item)
                if item.filename == "xl/worksheets/sheet1.xml":
                    element = ElementTree.fromstring(content)
                    namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                    value = element.find('.//s:c[@r="B2"]/s:v', namespace)
                    self.assertIsNotNone(value)
                    value.text = "3"
                    content = ElementTree.tostring(element)
                target.writestr(item, content)
        path.write_bytes(updated.getvalue())
        table = read_table(path)
        self.assertEqual(table["rows"][0]["total"], "3")
        self.assertTrue(any("cached formula" in warning for warning in table["warnings"]))

    def test_sheet_selection_is_disclosed(self):
        book, sheet = self.workbook()
        sheet.append(["id"])
        sheet.append(["001"])
        second = book.create_sheet("Other")
        second.append(["id"])
        second.append(["002"])
        path = self.save(book)
        first = read_table(path)
        self.assertTrue(any("2 sheets" in warning for warning in first["warnings"]))
        self.assertEqual(read_table(path, sheet="Other")["rows"][0]["id"], "002")
        with self.assertRaisesRegex(DataError, "does not exist"):
            read_table(path, sheet="Missing")

    def test_oversized_dimensions_fail_before_iteration(self):
        book, sheet = self.workbook()
        sheet.append(["id"])
        sheet.cell(50_002, 1).value = "large"
        with self.assertRaisesRegex(DataError, "dimensions"):
            read_table(self.save(book))


if __name__ == "__main__":
    unittest.main()
