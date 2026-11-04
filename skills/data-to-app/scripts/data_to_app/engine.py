"""Identity-aware snapshot imports and a local, reviewable three-way merge.

Source values remain strings. SQLite stores source rows and local overrides
separately; a new source snapshot cannot silently replace a local correction.
"""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import re
import sqlite3
import threading
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


MAX_ROWS = 50_000
MAX_COLUMNS = 200
MAX_CELL = 65_536
MAX_CELLS = 1_000_000
MAX_TABLES = 100
_ID_NAME = re.compile(r"(^|_)(id|uuid|sku|code|key|number)$", re.I)
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_LEADING_ZERO = re.compile(r"^[+-]?0\d+$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T.+)?$")


class DataError(ValueError):
    """Input or model cannot be processed without guessing or data loss."""


class RevisionConflict(DataError):
    """The caller's view is stale; refresh before applying the operation."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _columns(table):
    if not isinstance(table, dict):
        raise DataError("A table must be an object with columns and rows.")
    columns = table.get("columns")
    if (not isinstance(columns, list) or not columns or len(columns) > MAX_COLUMNS
            or any(not isinstance(c, str) or not c.strip() or len(c) > 256 or "\x00" in c for c in columns)
            or len(set(columns)) != len(columns)):
        raise DataError("Table headers must be unique, nonempty strings (at most 200 columns).")
    return columns


def _checked_rows(table):
    columns = _columns(table)
    rows = table.get("rows")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS or len(rows) * len(columns) > MAX_CELLS:
        raise DataError(f"A table must contain at most {MAX_ROWS:,} rows and {MAX_CELLS:,} cells.")
    expected = set(columns)
    for index, row in enumerate(rows, 2):
        if not isinstance(row, dict) or set(row) != expected:
            raise DataError(f"Row {index} does not match the table headers.")
        if any(not isinstance(v, str) or len(v) > MAX_CELL or "\x00" in v for v in row.values()):
            raise DataError(f"Row {index} contains an unsupported value or an oversized cell.")
    return rows


def _key_fields(value, columns):
    if isinstance(value, str):
        value = [value]
    if (not isinstance(value, list) or not value or len(value) > 8
            or any(not isinstance(c, str) or c not in columns for c in value)
            or len(set(value)) != len(value)):
        raise DataError("A key must name one to eight distinct existing columns.")
    return value


def _key(row, fields):
    values = tuple(row[c] for c in fields)
    return values if all(v.strip() for v in values) else None


def _decimal(value):
    if not isinstance(value, str) or not _NUMBER.fullmatch(value.strip()):
        return None
    try:
        result = Decimal(value.strip())
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _is_date(value):
    if not _ISO_DATE.fullmatch(value):
        return False
    try:
        (datetime.fromisoformat if "T" in value else date.fromisoformat)(value)
        return True
    except ValueError:
        return False


def profile_table(table):
    """Return bounded evidence about shape, types and statistical key candidates."""
    columns = _columns(table)
    rows = _checked_rows(table)
    duplicate_count = len(rows) - len({_json(row) for row in rows})
    unique_rows = list({_json(row): row for row in rows}.values())
    profiles = []
    candidates = []
    for name in columns:
        values = [row[name] for row in rows]
        populated = [v for v in values if v.strip()]
        leading_zero = any(_LEADING_ZERO.fullmatch(v) for v in populated)
        if _ID_NAME.search(name) or leading_zero:
            kind = "identifier"
        elif populated and all(v.casefold() in {"true", "false", "yes", "no"} for v in populated):
            kind = "boolean"
        elif populated and all(_decimal(v) is not None for v in populated):
            kind = "number"
        elif populated and all(_is_date(v) for v in populated):
            kind = "date"
        else:
            kind = "text"
        examples = list(dict.fromkeys(populated))[:5]
        profiles.append({"name": name, "kind": kind, "nulls": len(values) - len(populated),
                         "distinct": len(set(populated)), "leading_zero": leading_zero,
                         "examples": [v[:200] for v in examples]})
        if unique_rows and all(row[name].strip() for row in unique_rows) and len({row[name] for row in unique_rows}) == len(unique_rows):
            candidates.append([name])
    # Composite search is deliberately bounded. Uniqueness is evidence, not a
    # business-identity decision; combinations must still be confirmed by the agent.
    ranked = sorted(profiles, key=lambda p: (not bool(_ID_NAME.search(p["name"])), -p["distinct"]))
    singles = {candidate[0] for candidate in candidates}
    eligible = [p["name"] for p in ranked if not p["nulls"] and p["name"] not in singles][:12]
    for pair in itertools.combinations(eligible, 2):
        if unique_rows and len({tuple(row[c] for c in pair) for row in unique_rows}) == len(unique_rows):
            candidates.append(list(pair))
        if len(candidates) >= 20:
            break
    candidates.sort(key=lambda key: (len(key), not any(_ID_NAME.search(c) for c in key), key))
    warnings = list(table.get("warnings", []))
    if duplicate_count:
        warnings.append(f"{duplicate_count} identical repeated row(s); review export overlap.")
    if candidates:
        warnings.append("Statistical uniqueness does not establish a stable business identity. Confirm the key.")
    elif rows:
        warnings.append("No nonempty unique key found in the bounded search. Supply an explicit business key.")
    if any(p["leading_zero"] for p in profiles):
        warnings.append("Leading-zero identifiers are preserved as strings.")
    return {"source": table.get("source", ""), "format": table.get("format", "unknown"),
            "row_count": len(rows), "duplicate_row_count": duplicate_count,
            "columns": profiles, "candidate_keys": candidates[:20], "warnings": warnings}


def probe_join(left, right, left_keys, right_keys):
    """Show cardinality and coverage without silently performing a business join."""
    lfields = _key_fields(left_keys, _columns(left))
    rfields = _key_fields(right_keys, _columns(right))
    if len(lfields) != len(rfields):
        raise DataError("Both join keys must have the same number of fields.")
    lrows, rrows = _checked_rows(left), _checked_rows(right)
    lcounts = Counter(k for row in lrows if (k := _key(row, lfields)) is not None)
    rcounts = Counter(k for row in rrows if (k := _key(row, rfields)) is not None)
    matched = sum(1 for row in lrows if (k := _key(row, lfields)) is not None and k in rcounts)
    projected = sum(max(rcounts.get(_key(row, lfields), 0), 1) for row in lrows)
    warnings = []
    if projected > len(lrows):
        warnings.append("The right key repeats: this left join would multiply records. Do not aggregate joined measures without a grain decision.")
    if matched != len(lrows):
        warnings.append("Some left records have empty or unmatched keys.")
    return {"left_rows": len(lrows), "right_rows": len(rrows),
            "left_distinct_keys": len(lcounts), "right_distinct_keys": len(rcounts),
            "left_cardinality": "unique" if max(lcounts.values(), default=0) <= 1 else "repeated",
            "right_cardinality": "unique" if max(rcounts.values(), default=0) <= 1 else "repeated",
            "matched_left_rows": matched, "unmatched_left_rows": len(lrows) - matched,
            "coverage": matched / len(lrows) if lrows else 0.0,
            "projected_left_join_rows": projected, "multiplies_rows": projected > len(lrows),
            "warnings": warnings}


def _validate_manifest(manifest):
    if (not isinstance(manifest, dict) or isinstance(manifest.get("version"), bool)
            or manifest.get("version") != 1):
        raise DataError("The model must use version 1.")
    title = manifest.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise DataError("The model needs a nonempty title of at most 200 characters.")
    tables = manifest.get("tables")
    if not isinstance(tables, list) or not tables or len(tables) > MAX_TABLES:
        raise DataError("The model needs one to 100 tables.")
    ids = set()
    for table in tables:
        if not isinstance(table, dict):
            raise DataError("Each model table must be an object.")
        ident = table.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", ident) or ident in ids:
            raise DataError("Table ids must be distinct short identifiers.")
        ids.add(ident)
        if "label" in table and (not isinstance(table["label"], str) or len(table["label"]) > 200):
            raise DataError("A table label must be a string of at most 200 characters.")
        columns = _columns(table)
        if not isinstance(table.get("key"), list):
            raise DataError("Model key fields must be an explicit list of column names.")
        key = _key_fields(table.get("key"), columns)
        editable = table.get("editable", [])
        if (not isinstance(editable, list)
                or any(not isinstance(c, str) or c not in columns or c in key for c in editable)
                or len(set(editable)) != len(editable)):
            raise DataError(f"Editable fields in {ident} must exist and cannot include key fields.")
        views = table.get("views", [])
        if not isinstance(views, list) or len(views) > 30:
            raise DataError("A table can have at most 30 views.")
        view_ids = set()
        for view in views:
            if (not isinstance(view, dict) or not isinstance(view.get("id"), str)
                    or not view["id"] or len(view["id"]) > 64 or view["id"] in view_ids):
                raise DataError("Views need distinct string ids.")
            view_ids.add(view["id"])
            rule = view.get("rule")
            if (not isinstance(rule, dict) or rule.get("left") not in columns
                    or not isinstance(rule.get("op"), str)
                    or rule.get("op") not in {"eq", "ne", "lt", "lte", "gt", "gte", "contains"}):
                raise DataError("A view needs a supported comparison and existing left field.")
            if ("right_field" in rule) == ("value" in rule):
                raise DataError("A view comparison needs exactly one right_field or value.")
            if "right_field" in rule and rule["right_field"] not in columns:
                raise DataError("The view's right field does not exist.")
            if "value" in rule and not isinstance(rule["value"], str):
                raise DataError("A view literal must be a string.")
            if not isinstance(rule.get("type", "text"), str) or rule.get("type", "text") not in {"text", "decimal"}:
                raise DataError("View comparison type must be text or decimal.")
    return json.loads(_json(manifest))


def _snapshot(table, model):
    columns = _columns(table)
    rows = _checked_rows(table)
    if set(columns) != set(model["columns"]):
        raise DataError("Import headers changed. Review the model before importing a different schema.")
    keyed, duplicate_count = {}, 0
    for index, row in enumerate(rows, 2):
        values = _key(row, model["key"])
        if values is None:
            raise DataError(f"Row {index} has an empty key. No rows were imported.")
        ident = _hash(list(values))
        if ident in keyed:
            if keyed[ident] != row:
                raise DataError(f"Rows disagree for the same key at row {index}. Resolve the duplicate before importing.")
            duplicate_count += 1
        else:
            keyed[ident] = dict(row)
    digest = _hash({"columns": model["columns"], "rows": sorted(keyed.items())})
    return keyed, duplicate_count, digest


class Store:
    """A SQLite-backed local workspace with optimistic revision checks."""

    def __init__(self, db_path):
        self.path = Path(db_path)
        if self.path.is_symlink():
            raise DataError("The database path cannot be a symbolic link.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=10000")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS records (
                table_id TEXT NOT NULL, row_id TEXT NOT NULL, source TEXT NOT NULL,
                overrides TEXT NOT NULL DEFAULT '{}', missing INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (table_id, row_id));
            CREATE TABLE IF NOT EXISTS conflicts (
                id TEXT PRIMARY KEY, table_id TEXT NOT NULL, row_id TEXT NOT NULL,
                field TEXT NOT NULL, base TEXT NOT NULL, local TEXT NOT NULL,
                incoming TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'field',
                FOREIGN KEY (table_id,row_id) REFERENCES records(table_id,row_id));
            CREATE TABLE IF NOT EXISTS imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT, table_id TEXT NOT NULL,
                filename TEXT NOT NULL, digest TEXT NOT NULL, file_digest TEXT,
                counts TEXT NOT NULL, created_at TEXT NOT NULL);
        """)

    def close(self):
        with self._lock:
            self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def _transaction(self):
        if self._db.in_transaction:
            raise DataError("A mutation cannot run inside a read snapshot.")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        else:
            self._db.execute("COMMIT")

    @contextmanager
    def read_snapshot(self):
        """Keep related reads and their revision in one SQLite snapshot.

        This can be nested by callers combining bootstrap/conflict/history data.
        Independent CLI connections may commit while the snapshot is open; the
        reader continues to see the matching old data *and* old revision.
        """
        with self._lock:
            outermost = not self._db.in_transaction
            if outermost:
                self._db.execute("BEGIN")
            try:
                yield self
            except BaseException:
                if outermost:
                    self._db.execute("ROLLBACK")
                raise
            else:
                if outermost:
                    self._db.execute("COMMIT")

    def _get_meta(self, key, default=None):
        row = self._db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def _set_meta(self, key, value):
        self._db.execute("INSERT INTO metadata(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, _json(value)))

    def _revision(self):
        return self._get_meta("revision", 0)

    def _check_revision(self, expected):
        if isinstance(expected, bool) or not isinstance(expected, int) or expected != self._revision():
            raise RevisionConflict("The workspace changed. Refresh and review before applying this operation.")

    def _bump(self):
        revision = self._revision() + 1
        self._set_meta("revision", revision)
        return revision

    def manifest(self):
        with self.read_snapshot():
            manifest = self._get_meta("manifest")
            if manifest is None:
                raise DataError("The workspace has not been initialized.")
            return manifest

    def _model(self, table_id):
        if not isinstance(table_id, str):
            raise DataError("Unknown table.")
        for model in self.manifest()["tables"]:
            if model["id"] == table_id:
                return model
        raise DataError("Unknown table.")

    def bootstrap(self, manifest, sources_by_table_id):
        model = _validate_manifest(manifest)
        if not isinstance(sources_by_table_id, dict) or set(sources_by_table_id) != {t["id"] for t in model["tables"]}:
            raise DataError("Each model table needs exactly one matching source table.")
        prepared = [(table, *_snapshot(sources_by_table_id[table["id"]], table)) for table in model["tables"]]
        with self._lock, self._transaction():
            if self._get_meta("manifest") is not None:
                raise DataError("This workspace is already initialized; it was not overwritten.")
            self._set_meta("manifest", model)
            self._set_meta("revision", 1)
            for table, keyed, duplicates, digest in prepared:
                ident = table["id"]
                for rid, row in keyed.items():
                    self._db.execute("INSERT INTO records(table_id,row_id,source,overrides,missing) VALUES (?,?,?,'{}',0)", (ident, rid, _json(row)))
                self._set_meta("digest:" + ident, digest)
                counts = {"new": len(keyed), "updated": 0, "unchanged": 0, "missing": 0, "conflicts": 0, "duplicates": duplicates}
                self._record_import(ident, sources_by_table_id[ident], digest, counts)
        return self.summary()

    def _record_import(self, table_id, table, digest, counts):
        filename = Path(str(table.get("source", table_id))).name
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._db.execute("INSERT INTO imports(table_id,filename,digest,file_digest,counts,created_at) VALUES (?,?,?,?,?,?)", (table_id, filename, digest, table.get("file_digest"), _json(counts), now))

    def summary(self):
        with self.read_snapshot():
            self.manifest()
            records = self._db.execute("SELECT overrides,missing FROM records").fetchall()
            return {"revision": self._revision(), "active_rows": sum(not row["missing"] for row in records),
                    "missing_rows": sum(bool(row["missing"]) for row in records),
                    "local_edits": sum(len(json.loads(row["overrides"])) for row in records),
                    "edited_rows": sum(bool(json.loads(row["overrides"])) for row in records),
                    "conflicts": self._db.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0],
                    "imports": self._db.execute("SELECT COUNT(*) FROM imports").fetchone()[0]}

    def tables(self):
        with self.read_snapshot():
            result = self.manifest()["tables"]
            for model in result:
                rows = self._db.execute("SELECT overrides,missing FROM records WHERE table_id=?", (model["id"],)).fetchall()
                model.update({"row_count": sum(not r["missing"] for r in rows),
                              "missing_rows": sum(bool(r["missing"]) for r in rows),
                              "local_edits": sum(len(json.loads(r["overrides"])) for r in rows),
                              "conflicts": self._db.execute("SELECT COUNT(*) FROM conflicts WHERE table_id=?", (model["id"],)).fetchone()[0]})
            return result

    def _record_object(self, row):
        source, overrides = json.loads(row["source"]), json.loads(row["overrides"])
        return {"id": row["row_id"], "values": {**source, **overrides}, "source": source,
                "overrides": list(overrides), "missing": bool(row["missing"])}

    def get_row(self, table_id, row_id):
        """Fetch an exact record and revision without scanning a truncated page."""
        if not isinstance(row_id, str) or not re.fullmatch(r"[0-9a-f]{64}", row_id):
            raise DataError("Invalid record identity.")
        with self.read_snapshot():
            self._model(table_id)
            row = self._db.execute("SELECT * FROM records WHERE table_id=? AND row_id=?", (table_id, row_id)).fetchone()
            if row is None:
                raise DataError("This record is not available in the workspace.")
            return {"row": self._record_object(row), "revision": self._revision()}

    @staticmethod
    def _matches_view(values, rule):
        left = values[rule["left"]]
        right = values[rule["right_field"]] if "right_field" in rule else rule["value"]
        if rule.get("type", "text") == "decimal":
            left, right = _decimal(left), _decimal(right)
            if left is None or right is None:
                return False
        op = rule["op"]
        if op == "contains":
            return str(right).casefold() in str(left).casefold()
        return {"eq": lambda: left == right, "ne": lambda: left != right,
                "lt": lambda: left < right, "lte": lambda: left <= right,
                "gt": lambda: left > right, "gte": lambda: left >= right}[op]()

    def rows(self, table_id, search="", view=None, include_missing=False, offset=0, limit=50):
        if not isinstance(search, str) or len(search) > 2000:
            raise DataError("Search text must be at most 2,000 characters.")
        if (isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or offset > 1_000_000
                or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500):
            raise DataError("Invalid page range; limit must be between 1 and 500.")
        with self.read_snapshot():
            model = self._model(table_id)
            rule = None
            if view:
                selected = next((v for v in model.get("views", []) if v["id"] == view), None)
                if selected is None:
                    raise DataError("Unknown view.")
                rule = selected["rule"]
            needle = search.casefold()
            found = []
            for row in self._db.execute("SELECT * FROM records WHERE table_id=? ORDER BY rowid", (table_id,)):
                if row["missing"] and not include_missing:
                    continue
                obj = self._record_object(row)
                if needle and not any(needle in value.casefold() for value in obj["values"].values()):
                    continue
                if rule and not self._matches_view(obj["values"], rule):
                    continue
                found.append(obj)
            return {"rows": found[offset:offset + limit], "total": len(found), "revision": self._revision()}

    def edit_row(self, table_id, row_id, changes, expected_revision):
        if not isinstance(row_id, str) or not re.fullmatch(r"[0-9a-f]{64}", row_id):
            raise DataError("Invalid record identity.")
        with self._lock, self._transaction():
            self._check_revision(expected_revision)
            model = self._model(table_id)
            if (not isinstance(changes, dict) or not changes or any(k not in model.get("editable", []) for k in changes)
                    or any(not isinstance(v, str) or len(v) > MAX_CELL or "\x00" in v for v in changes.values())):
                raise DataError("Edit only permitted fields using bounded string values. Key fields cannot be changed.")
            row = self._db.execute("SELECT * FROM records WHERE table_id=? AND row_id=?", (table_id, row_id)).fetchone()
            if row is None:
                raise DataError("The record no longer exists.")
            source, overrides = json.loads(row["source"]), json.loads(row["overrides"])
            before = dict(overrides)
            for field, value in changes.items():
                cid = _hash([table_id, row_id, field])
                if value == source[field]:
                    overrides.pop(field, None)
                    self._db.execute("DELETE FROM conflicts WHERE id=?", (cid,))
                else:
                    overrides[field] = value
                    self._db.execute("UPDATE conflicts SET local=? WHERE id=?", (_json(value), cid))
            if before != overrides:
                self._db.execute("UPDATE records SET overrides=? WHERE table_id=? AND row_id=?", (_json(overrides), table_id, row_id))
                self._bump()
            updated = self._db.execute("SELECT * FROM records WHERE table_id=? AND row_id=?", (table_id, row_id)).fetchone()
            return {"revision": self._revision(), "row": self._record_object(updated)}

    def _conflict_object(self, row, model=None, source=None):
        result = dict(row)
        for field in ("base", "local", "incoming"):
            result[field] = json.loads(result[field])
        model = model or self._model(result["table_id"])
        if source is None:
            record = self._db.execute("SELECT source FROM records WHERE table_id=? AND row_id=?", (result["table_id"], result["row_id"])).fetchone()
            source = json.loads(record[0])
        result["key_values"] = {field: source[field] for field in model["key"]}
        return result

    def conflicts(self):
        with self.read_snapshot():
            return [self._conflict_object(row) for row in self._db.execute("SELECT * FROM conflicts ORDER BY table_id,row_id,field")]

    def _plan_import(self, table_id, table):
        model = self._model(table_id)
        incoming, duplicate_count, digest = _snapshot(table, model)
        current = {r["row_id"]: r for r in self._db.execute("SELECT * FROM records WHERE table_id=? ORDER BY rowid", (table_id,))}
        old_conflicts = {(c["row_id"], c["field"]): dict(c) for c in self._db.execute("SELECT * FROM conflicts WHERE table_id=?", (table_id,))}
        counts = {"new": 0, "updated": 0, "unchanged": 0, "missing": 0, "conflicts": 0, "duplicates": duplicate_count}
        records, conflicts = [], []
        for rid, new_source in incoming.items():
            if rid not in current:
                counts["new"] += 1
                records.append((table_id, rid, _json(new_source), "{}", 0))
                continue
            row = current[rid]
            old_source, overrides = json.loads(row["source"]), json.loads(row["overrides"])
            counts["updated" if new_source != old_source or row["missing"] else "unchanged"] += 1
            for field in list(overrides):
                local = overrides[field]
                existing = old_conflicts.get((rid, field))
                if new_source[field] == local:
                    del overrides[field]
                elif new_source[field] != old_source[field] or existing:
                    conflict = {"id": _hash([table_id, rid, field]), "table_id": table_id, "row_id": rid,
                                "field": field, "base": existing["base"] if existing else _json(old_source[field]),
                                "local": _json(local), "incoming": _json(new_source[field]), "kind": "field"}
                    conflicts.append(conflict)
            records.append((table_id, rid, _json(new_source), _json(overrides), 0))
        for rid, row in current.items():
            if rid not in incoming:
                if not row["missing"]:
                    counts["missing"] += 1
                records.append((table_id, rid, row["source"], row["overrides"], 1))
                conflicts.extend(c for (crid, _), c in old_conflicts.items() if crid == rid)
        counts["conflicts"] = len(conflicts)
        warnings = list(table.get("warnings", []))
        if duplicate_count:
            warnings.append(f"Collapsed {duplicate_count} identical duplicate row(s).")
        if counts["missing"]:
            warnings.append("Absent records will be marked missing and retained, including local edits.")
        preview = []
        for conflict in conflicts[:100]:
            source = incoming.get(conflict["row_id"]) or json.loads(current[conflict["row_id"]]["source"])
            preview.append(self._conflict_object(conflict, model, source))
        if len(conflicts) > 100:
            warnings.append("Preview shows the first 100 conflicts; all conflicts remain available after import.")
        result = {"revision": self._revision(), "counts": counts, "warnings": warnings,
                  "conflicts": preview, "no_op": digest == self._get_meta("digest:" + table_id)}
        return result, records, conflicts, digest

    def preview_import(self, table_id, table):
        with self.read_snapshot():
            result, _, _, _ = self._plan_import(table_id, table)
            return result

    def apply_import(self, table_id, table, expected_revision):
        with self._lock, self._transaction():
            self._check_revision(expected_revision)
            result, records, conflicts, digest = self._plan_import(table_id, table)
            if result["no_op"]:
                return result
            self._db.executemany("INSERT INTO records(table_id,row_id,source,overrides,missing) VALUES (?,?,?,?,?) ON CONFLICT(table_id,row_id) DO UPDATE SET source=excluded.source,overrides=excluded.overrides,missing=excluded.missing", records)
            self._db.execute("DELETE FROM conflicts WHERE table_id=?", (table_id,))
            self._db.executemany("INSERT INTO conflicts(id,table_id,row_id,field,base,local,incoming,kind) VALUES (:id,:table_id,:row_id,:field,:base,:local,:incoming,:kind)", conflicts)
            self._set_meta("digest:" + table_id, digest)
            self._record_import(table_id, table, digest, result["counts"])
            result["revision"] = self._bump()
            return result

    def resolve_conflict(self, conflict_id, choice, expected_revision):
        if not isinstance(conflict_id, str) or not re.fullmatch(r"[0-9a-f]{64}", conflict_id):
            raise DataError("Invalid conflict identity.")
        if not isinstance(choice, str) or choice not in {"local", "source"}:
            raise DataError("Choose local or source to resolve a conflict.")
        with self._lock, self._transaction():
            self._check_revision(expected_revision)
            conflict = self._db.execute("SELECT * FROM conflicts WHERE id=?", (conflict_id,)).fetchone()
            if conflict is None:
                raise DataError("The conflict no longer exists. Refresh the workspace.")
            if choice == "source":
                row = self._db.execute("SELECT overrides FROM records WHERE table_id=? AND row_id=?", (conflict["table_id"], conflict["row_id"])).fetchone()
                overrides = json.loads(row[0])
                overrides.pop(conflict["field"], None)
                self._db.execute("UPDATE records SET overrides=? WHERE table_id=? AND row_id=?", (_json(overrides), conflict["table_id"], conflict["row_id"]))
            self._db.execute("DELETE FROM conflicts WHERE id=?", (conflict_id,))
            return {"revision": self._bump()}

    def history(self):
        with self.read_snapshot():
            result = []
            for row in self._db.execute("SELECT * FROM imports ORDER BY id DESC"):
                item = dict(row)
                counts = json.loads(item.pop("counts"))
                item["counts"] = counts
                item.update(counts)
                result.append(item)
            return result

    def export_csv(self, table_id, safe=True, include_missing=False):
        with self.read_snapshot():
            model = self._model(table_id)
            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator="\r\n")

            def cell(value):
                stripped = value.lstrip()
                if safe and (stripped.startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
                    return "'" + value
                return value

            writer.writerow([cell(c) for c in model["columns"]])
            for row in self._db.execute("SELECT * FROM records WHERE table_id=? ORDER BY rowid", (table_id,)):
                if row["missing"] and not include_missing:
                    continue
                obj = self._record_object(row)
                writer.writerow([cell(obj["values"][c]) for c in model["columns"]])
            return output.getvalue()
