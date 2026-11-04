"""Bounded CSV and optional XLSX readers; no formula evaluation or lossy decoding."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import stat
import zipfile
from datetime import date, datetime, time
from pathlib import Path

from .engine import DataError, MAX_CELL, MAX_CELLS, MAX_COLUMNS, MAX_ROWS


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 20 * 1024 * 1024
MAX_ZIP_MEMBERS = 2000


def _regular_path(path):
    path = Path(path)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise DataError(f"Cannot open input: {exc.strerror or 'file unavailable'}.") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DataError("Input must be a regular file, not a directory, symbolic link or device.")
    if metadata.st_size > MAX_FILE_BYTES:
        raise DataError("Input exceeds the 10 MiB file limit.")
    if path.suffix.casefold() not in {".csv", ".xlsx"}:
        raise DataError("Supported inputs are UTF-8 CSV and XLSX files.")
    return path


def discover_sources(path):
    """Return explicit input or sorted, top-level CSV/XLSX files only."""
    path = Path(path)
    if path.is_symlink():
        raise DataError("Input cannot be a symbolic link.")
    if path.is_file():
        return [_regular_path(path)]
    if not path.is_dir():
        raise DataError("Input path does not exist or is not a directory.")
    candidates = sorted((p for p in path.iterdir() if p.suffix.casefold() in {".csv", ".xlsx"}), key=lambda p: p.name.casefold())
    if not candidates:
        raise DataError("No top-level CSV/XLSX files found in this folder.")
    if len(candidates) > 100:
        raise DataError("Inspect at most 100 source files at a time.")
    return [_regular_path(p) for p in candidates]


def _headers(values):
    if not values or len(values) > MAX_COLUMNS:
        raise DataError("Input needs one to 200 header columns.")
    columns = [str(value).strip() if value is not None else "" for value in values]
    if any(not value or len(value) > 256 or "\x00" in value for value in columns):
        raise DataError("Headers must be nonempty and at most 256 characters.")
    if len(set(columns)) != len(columns):
        raise DataError("Duplicate headers found after trimming surrounding whitespace.")
    return columns


def _csv_table(path, content):
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataError("CSV must be UTF-8. Export it as UTF-8 CSV instead of guessing an encoding.") from exc
    if "\x00" in text:
        raise DataError("NUL bytes are not supported in CSV files.")
    try:
        try:
            dialect = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text, newline=""), dialect, strict=True)
        first = next(reader, None)
        columns = _headers(first)
        rows, blank_rows = [], 0
        for line in reader:
            if not line or all(value == "" for value in line):
                blank_rows += 1
                continue
            if len(line) != len(columns):
                raise DataError(f"CSV record ending at line {reader.line_num} has {len(line)} fields; expected {len(columns)}.")
            if any(len(value) > MAX_CELL for value in line):
                raise DataError(f"A cell exceeds the {MAX_CELL:,}-character limit.")
            rows.append(dict(zip(columns, line)))
            if len(rows) > MAX_ROWS or len(rows) * len(columns) > MAX_CELLS:
                raise DataError(f"Input exceeds the {MAX_ROWS:,}-row / {MAX_CELLS:,}-cell limit.")
    except csv.Error as exc:
        raise DataError(f"Malformed or oversized CSV: {exc}.") from exc
    warnings = [f"Ignored {blank_rows} blank record(s)."] if blank_rows else []
    return {"columns": columns, "rows": rows, "source": str(path), "format": "csv", "warnings": warnings}


def _check_xlsx_zip(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_MEMBERS or len({m.filename for m in members}) != len(members):
                raise DataError("XLSX archive has too many or duplicate members.")
            if sum(member.file_size for member in members) > MAX_ZIP_BYTES:
                raise DataError("XLSX expanded content exceeds the 50 MiB limit.")
            for member in members:
                if member.file_size > MAX_ZIP_MEMBER_BYTES or member.flag_bits & 1:
                    raise DataError("XLSX contains an oversized or encrypted archive member.")
                if member.filename.startswith("/") or ".." in Path(member.filename).parts:
                    raise DataError("XLSX contains an unsupported archive path.")
                if member.filename.casefold().endswith((".xml", ".rels")):
                    xml = archive.read(member)
                    upper = xml.upper()
                    if b"\x00" in xml or b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
                        raise DataError("XLSX XML entities, DTDs and non-UTF-8 XML are not supported.")
                    if member.filename.casefold().endswith("sharedstrings.xml") and len(re.findall(rb"<(?:[a-zA-Z0-9_]+:)?si(?:\s|>)", xml)) > 250_000:
                        raise DataError("XLSX shared-string count exceeds the 250,000-entry limit.")
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise DataError("The XLSX ZIP archive is invalid or unreadable.") from exc


def _xlsx_value(cell, cached, warnings):
    value = cell.value
    if cell.data_type == "f":
        if cached.value is None:
            raise DataError(f"Formula cell {cell.coordinate} has no cached value. Recalculate and save the workbook, or export CSV.")
        warnings.add("Uses cached formula values; recalculate in the spreadsheet application before importing updated results.")
        value = cached.value
        if cached.data_type == "e":
            raise DataError(f"Formula cell {cell.coordinate} contains a spreadsheet error.")
    elif cell.data_type == "e":
        raise DataError(f"Cell {cell.coordinate} contains a spreadsheet error.")
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    number_format = cell.number_format or "General"
    if isinstance(value, (int, float)):
        if re.fullmatch(r"0{2,256}", number_format) and float(value).is_integer():
            sign = "-" if value < 0 else ""
            return sign + str(abs(int(value))).zfill(len(number_format))
        if number_format not in {"General", "0", "0.00", "@"}:
            warnings.add(f"Numeric display format {number_format[:80]!r} in column {cell.column_letter}: review units and display semantics.")
    return str(value)


def _xlsx_table(path, content, sheet):
    _check_xlsx_zip(content)
    try:
        import openpyxl
    except ImportError as exc:
        raise DataError("XLSX support needs the optional openpyxl dependency. Install requirements-xlsx.txt, or export UTF-8 CSV.") from exc
    formulas = cached = None
    try:
        formulas = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
        cached = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
        if sheet is not None and sheet not in formulas.sheetnames:
            raise DataError("Requested worksheet does not exist.")
        selected = sheet or formulas.sheetnames[0]
        ws, values_ws = formulas[selected], cached[selected]
        if ((ws.max_row or 0) > MAX_ROWS + 1 or (ws.max_column or 0) > MAX_COLUMNS
                or (ws.max_row or 0) * (ws.max_column or 0) > MAX_CELLS):
            raise DataError("Worksheet dimensions exceed the 50,000-row / 200-column / 1,000,000-cell limit.")
        warnings = set()
        source_rows = ws.iter_rows()
        value_rows = values_ws.iter_rows()
        header = next(source_rows, None)
        next(value_rows, None)
        if header is None:
            raise DataError("Worksheet has no header row.")
        if any(cell.data_type == "f" for cell in header):
            raise DataError("Formula headers are not supported; use explicit column names.")
        columns = _headers([cell.value for cell in header])
        rows, blanks = [], 0
        for cells, value_cells in zip(source_rows, value_rows):
            values = [_xlsx_value(cell, cache, warnings) for cell, cache in zip(cells, value_cells)]
            if all(value == "" for value in values):
                blanks += 1
                continue
            if len(values) != len(columns) or any(len(value) > MAX_CELL or "\x00" in value for value in values):
                raise DataError("Worksheet contains an unsupported row or oversized cell.")
            rows.append(dict(zip(columns, values)))
            if len(rows) > MAX_ROWS or len(rows) * len(columns) > MAX_CELLS:
                raise DataError("Worksheet exceeds the 50,000-row / 1,000,000-cell limit.")
        if blanks:
            warnings.add(f"Ignored {blanks} blank row(s).")
        if sheet is None and len(formulas.sheetnames) > 1:
            warnings.add(f"Workbook has {len(formulas.sheetnames)} sheets; selected {selected!r}. Specify a sheet to read another one.")
        return {"columns": columns, "rows": rows, "source": str(path), "format": "xlsx", "sheet": selected,
                "available_sheets": formulas.sheetnames, "warnings": sorted(warnings)}
    except DataError:
        raise
    except Exception as exc:
        raise DataError(f"Cannot read XLSX workbook ({type(exc).__name__}). Export UTF-8 CSV if unsupported.") from exc
    finally:
        if formulas is not None:
            formulas.close()
        if cached is not None:
            cached.close()


def read_table(path, sheet=None):
    path = _regular_path(path)
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_FILE_BYTES:
                raise DataError("Input must remain a regular file of at most 10 MiB.")
            content = handle.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise DataError("The input file could not be read.") from exc
    if len(content) > MAX_FILE_BYTES:
        raise DataError("Input exceeds the 10 MiB file limit.")
    table = _csv_table(path, content) if path.suffix.casefold() == ".csv" else _xlsx_table(path, content, sheet)
    table["file_digest"] = hashlib.sha256(content).hexdigest()
    return table
