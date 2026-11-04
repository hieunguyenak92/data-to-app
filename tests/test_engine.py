import copy
import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/data-to-app/scripts"))
from data_to_app.engine import DataError, RevisionConflict, Store, probe_join, profile_table


COLUMNS = ["sku", "name", "stock", "reorder_level", "notes"]
MANIFEST = {"version": 1, "title": "Inventory", "tables": [{
    "id": "products", "label": "Products", "columns": COLUMNS,
    "key": ["sku"], "editable": ["reorder_level", "notes"],
    "views": [{"id": "low", "label": "Low stock", "rule": {
        "left": "stock", "op": "lt", "right_field": "reorder_level", "type": "decimal"}}]}]}


def source(rows=None):
    return {"columns": COLUMNS.copy(), "source": "products.csv", "format": "csv", "rows": rows if rows is not None else [
        {"sku": "001", "name": "Paper", "stock": "5", "reorder_level": "10", "notes": ""},
        {"sku": "002", "name": "Pens", "stock": "20", "reorder_level": "4", "notes": ""},
        {"sku": "003", "name": "Folders", "stock": "3", "reorder_level": "5", "notes": ""}]}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.sqlite"
        self.store = Store(self.path)
        self.store.bootstrap(copy.deepcopy(MANIFEST), {"products": source()})

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def row(self, sku="001", missing=False):
        return next(row for row in self.store.rows("products", include_missing=missing)["rows"] if row["values"]["sku"] == sku)

    def edit(self, changes, sku="001"):
        return self.store.edit_row("products", self.row(sku)["id"], changes, self.store.summary()["revision"])

    def apply(self, table):
        return self.store.apply_import("products", table, self.store.summary()["revision"])

    def conflict(self):
        self.edit({"notes": "Keep local"})
        table = source()
        table["rows"][0]["notes"] = "New supplier note"
        self.apply(table)
        return table

    def test_bootstrap_preserves_keys_and_computes_views(self):
        self.assertEqual(self.store.summary()["active_rows"], 3)
        self.assertEqual(self.row()["values"]["sku"], "001")
        self.assertEqual(self.store.rows("products", view="low")["total"], 2)
        self.assertEqual(self.store.rows("products", search="PAPER")["total"], 1)
        self.assertEqual(self.store.tables()[0]["row_count"], 3)

    def test_local_override_survives_unrelated_source_update(self):
        self.edit({"notes": "Call first"})
        table = source()
        table["rows"][0]["stock"] = "8"
        preview = self.store.preview_import("products", table)
        self.assertEqual(preview["counts"]["conflicts"], 0)
        self.apply(table)
        row = self.row()
        self.assertEqual(row["values"]["notes"], "Call first")
        self.assertEqual(row["values"]["stock"], "8")
        self.assertEqual(row["source"]["notes"], "")
        self.assertEqual(row["overrides"], ["notes"])

    def test_divergence_preserves_local_and_exposes_three_versions(self):
        table = self.conflict()
        conflict = self.store.conflicts()[0]
        self.assertEqual((conflict["base"], conflict["local"], conflict["incoming"]), ("", "Keep local", "New supplier note"))
        self.assertEqual(conflict["key_values"], {"sku": "001"})
        self.assertEqual(self.row()["values"]["notes"], "Keep local")
        preview = self.store.preview_import("products", table)
        self.assertEqual(preview["conflicts"][0]["key_values"], {"sku": "001"})

    def test_repeated_snapshot_is_noop_and_keeps_unresolved_conflict(self):
        table = self.conflict()
        before = self.store.summary()
        history = len(self.store.history())
        result = self.apply(table)
        self.assertTrue(result["no_op"])
        self.assertEqual(self.store.summary(), before)
        self.assertEqual(len(self.store.history()), history)
        self.assertEqual(len(self.store.conflicts()), 1)

    def test_reordered_snapshot_is_idempotent(self):
        table = source()
        table["rows"].reverse()
        self.assertTrue(self.apply(table)["no_op"])
        self.assertEqual(self.store.summary()["revision"], 1)

    def test_next_changed_source_keeps_original_conflict_base(self):
        table = self.conflict()
        table["rows"][0]["notes"] = "Third source version"
        self.apply(table)
        conflict = self.store.conflicts()[0]
        self.assertEqual(conflict["base"], "")
        self.assertEqual(conflict["incoming"], "Third source version")
        self.assertEqual(conflict["local"], "Keep local")

    def test_source_convergence_removes_override_and_conflict(self):
        table = self.conflict()
        table["rows"][0]["notes"] = "Keep local"
        self.apply(table)
        self.assertEqual(self.row()["overrides"], [])
        self.assertEqual(self.store.conflicts(), [])
        self.assertEqual(self.row()["source"]["notes"], "Keep local")

    def test_resolve_source_uses_latest_source_value(self):
        self.conflict()
        self.store.resolve_conflict(self.store.conflicts()[0]["id"], "source", self.store.summary()["revision"])
        self.assertEqual(self.row()["values"]["notes"], "New supplier note")
        self.assertEqual(self.row()["overrides"], [])
        self.assertEqual(self.store.conflicts(), [])

    def test_resolve_local_keeps_override_until_source_changes_again(self):
        table = self.conflict()
        self.store.resolve_conflict(self.store.conflicts()[0]["id"], "local", self.store.summary()["revision"])
        self.assertEqual(self.store.conflicts(), [])
        self.assertEqual(self.row()["values"]["notes"], "Keep local")
        self.apply(table)
        self.assertEqual(self.store.conflicts(), [])
        table["rows"][0]["notes"] = "Another source"
        self.apply(table)
        self.assertEqual(len(self.store.conflicts()), 1)

    def test_edit_pending_conflict_updates_local_and_source_edit_resolves(self):
        self.conflict()
        self.edit({"notes": "Revised local"})
        self.assertEqual(self.store.conflicts()[0]["local"], "Revised local")
        self.edit({"notes": "New supplier note"})
        self.assertEqual(self.store.conflicts(), [])
        self.assertEqual(self.row()["overrides"], [])

    def test_missing_rows_retain_local_edits_and_reactivate(self):
        self.edit({"notes": "Do not discard"})
        table = source()
        table["rows"] = table["rows"][1:]
        result = self.apply(table)
        self.assertEqual(result["counts"]["missing"], 1)
        self.assertEqual(self.store.rows("products")["total"], 2)
        self.assertTrue(self.row(missing=True)["missing"])
        self.assertEqual(self.row(missing=True)["values"]["notes"], "Do not discard")
        self.apply(source())
        self.assertFalse(self.row()["missing"])
        self.assertEqual(self.row()["values"]["notes"], "Do not discard")

    def test_identical_duplicates_collapse_with_warning(self):
        table = source()
        table["rows"].append(dict(table["rows"][0]))
        preview = self.store.preview_import("products", table)
        self.assertEqual(preview["counts"]["duplicates"], 1)
        self.assertTrue(preview["warnings"])
        self.assertTrue(self.apply(table)["no_op"])
        self.assertEqual(self.store.summary()["active_rows"], 3)

    def test_conflicting_duplicate_rejects_whole_snapshot(self):
        table = source()
        table["rows"][0]["stock"] = "100"
        duplicate = dict(table["rows"][1])
        duplicate["notes"] = "Different"
        table["rows"].append(duplicate)
        before = self.store.summary()
        with self.assertRaisesRegex(DataError, "same key"):
            self.apply(table)
        self.assertEqual(self.store.summary(), before)
        self.assertEqual(self.row()["values"]["stock"], "5")

    def test_schema_change_rejected_before_mutation(self):
        table = source()
        table["columns"].append("new_column")
        for row in table["rows"]:
            row["new_column"] = ""
        with self.assertRaisesRegex(DataError, "headers changed"):
            self.apply(table)
        self.assertEqual(self.store.summary()["revision"], 1)

    def test_reordered_headers_are_not_a_schema_change(self):
        table = source()
        table["columns"].reverse()
        self.assertTrue(self.apply(table)["no_op"])

    def test_empty_key_and_non_string_values_rejected(self):
        for value in ("", "   "):
            table = source()
            table["rows"][0]["sku"] = value
            with self.assertRaisesRegex(DataError, "empty key"):
                self.apply(table)
        table = source()
        table["rows"][0]["stock"] = 42
        with self.assertRaises(DataError):
            self.apply(table)
        self.assertEqual(self.store.summary()["revision"], 1)

    def test_stale_operations_cannot_overwrite_a_new_edit(self):
        old = self.store.summary()["revision"]
        self.edit({"notes": "Newest"})
        with self.assertRaises(RevisionConflict):
            self.store.edit_row("products", self.row()["id"], {"notes": "Stale"}, old)
        with self.assertRaises(RevisionConflict):
            self.store.apply_import("products", source(), old)
        self.assertEqual(self.row()["values"]["notes"], "Newest")

    def test_second_connection_observes_global_revision(self):
        other = Store(self.path)
        try:
            old = other.summary()["revision"]
            self.edit({"notes": "First connection"})
            with self.assertRaises(RevisionConflict):
                other.edit_row("products", self.row()["id"], {"notes": "Stale connection"}, old)
        finally:
            other.close()

    def test_rows_and_revision_use_same_snapshot_during_external_commit(self):
        other = Store(self.path)
        ident = self.row()["id"]
        original_revision = self.store._revision
        committed = False

        def commit_before_revision_read():
            nonlocal committed
            if not committed:
                committed = True
                other.edit_row("products", ident, {"notes": "External change"}, 1)
            return original_revision()

        try:
            # This hook commits after rows were read but before their revision is
            # fetched. A per-instance lock alone cannot protect this boundary.
            with patch.object(self.store, "_revision", side_effect=commit_before_revision_read):
                page = self.store.rows("products")
            old = next(r for r in page["rows"] if r["id"] == ident)
            self.assertEqual(old["values"]["notes"], "")
            self.assertEqual(page["revision"], 1)
            self.assertEqual(self.store.summary()["revision"], 2)
            with self.assertRaises(RevisionConflict):
                self.store.edit_row("products", ident, {"notes": "Stale"}, page["revision"])
        finally:
            other.close()

    def test_public_nested_read_snapshot_keeps_combined_calls_consistent(self):
        other = Store(self.path)
        ident = self.row()["id"]
        try:
            with self.store.read_snapshot():
                self.assertEqual(self.store.summary()["revision"], 1)
                other.edit_row("products", ident, {"notes": "External"}, 1)
                self.assertEqual(self.store.rows("products")["revision"], 1)
                self.assertEqual(self.row()["values"]["notes"], "")
            self.assertEqual(self.row()["values"]["notes"], "External")
        finally:
            other.close()

    def test_permissions_and_malformed_identity_do_not_mutate(self):
        for changes in ({"sku": "999"}, {"stock": "99"}, {"unknown": "x"}, {"notes": 5}):
            with self.assertRaises(DataError):
                self.edit(changes)
        with self.assertRaises(DataError):
            self.store.edit_row("products", {}, {"notes": "x"}, 1)
        with self.assertRaises(RevisionConflict):
            self.store.edit_row("products", self.row()["id"], {"notes": "x"}, True)
        self.assertEqual(self.store.summary()["revision"], 1)

    def test_noop_edit_keeps_revision(self):
        self.edit({"notes": ""})
        self.assertEqual(self.store.summary()["revision"], 1)

    def test_safe_export_does_not_change_raw_source_or_values(self):
        dangerous = '  =HYPERLINK("https://example.test","open")'
        self.edit({"notes": dangerous})
        safe = list(csv.DictReader(io.StringIO(self.store.export_csv("products"))))
        raw = list(csv.DictReader(io.StringIO(self.store.export_csv("products", safe=False))))
        self.assertEqual(safe[0]["notes"], "'" + dangerous)
        self.assertEqual(raw[0]["notes"], dangerous)
        self.assertEqual(self.row()["values"]["notes"], dangerous)
        self.assertEqual(raw[0]["sku"], "001")

    def test_store_persists_conflicts_over_restart(self):
        self.conflict()
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.row()["values"]["notes"], "Keep local")
        self.assertEqual(self.store.conflicts()[0]["incoming"], "New supplier note")

    def test_existing_workspace_not_overwritten(self):
        self.edit({"notes": "Important"})
        with self.assertRaisesRegex(DataError, "already initialized"):
            self.store.bootstrap(MANIFEST, {"products": source()})
        self.assertEqual(self.row()["values"]["notes"], "Important")

    def test_invalid_model_and_failed_bootstrap_leave_no_partial_data(self):
        with Store(Path(self.temp.name) / "empty.sqlite") as store:
            model = copy.deepcopy(MANIFEST)
            model["tables"][0]["editable"] = ["sku"]
            with self.assertRaises(DataError):
                store.bootstrap(model, {"products": source()})
            broken = source()
            broken["rows"][0]["sku"] = ""
            with self.assertRaises(DataError):
                store.bootstrap(MANIFEST, {"products": broken})
            store.bootstrap(MANIFEST, {"products": source()})
            self.assertEqual(store.summary()["active_rows"], 3)

    def test_search_and_view_arguments_are_bounded(self):
        with self.assertRaises(DataError):
            self.store.rows("products", limit=-1)
        with self.assertRaises(DataError):
            self.store.rows("products", view="unknown")
        with self.assertRaises(DataError):
            self.store.rows("products", search="x" * 2001)
        self.assertEqual(self.store.rows("products", search="' OR 1=1 --")["total"], 0)


class AnalysisTests(unittest.TestCase):
    def test_profile_preserves_identifier_semantics_and_nulls(self):
        table = source()
        table["rows"].append(dict(table["rows"][0]))
        profile = profile_table(table)
        sku = next(c for c in profile["columns"] if c["name"] == "sku")
        self.assertEqual(sku["kind"], "identifier")
        self.assertTrue(sku["leading_zero"])
        self.assertEqual(profile["duplicate_row_count"], 1)
        self.assertIn(["sku"], profile["candidate_keys"])
        self.assertTrue(any("business identity" in warning for warning in profile["warnings"]))

    def test_profile_composite_key_candidate(self):
        table = {"columns": ["warehouse", "sku"], "rows": [
            {"warehouse": "A", "sku": "1"}, {"warehouse": "A", "sku": "2"},
            {"warehouse": "B", "sku": "1"}, {"warehouse": "B", "sku": "2"}]}
        self.assertTrue(any(set(k) == {"warehouse", "sku"} for k in profile_table(table)["candidate_keys"]))

    def test_join_detects_cardinality_multiplication_and_unmatched_keys(self):
        left = {"columns": ["product"], "rows": [{"product": "A"}, {"product": "A"}, {"product": "B"}, {"product": "C"}]}
        right = {"columns": ["sku"], "rows": [{"sku": "A"}, {"sku": "A"}, {"sku": "B"}]}
        result = probe_join(left, right, ["product"], ["sku"])
        self.assertEqual(result["projected_left_join_rows"], 6)
        self.assertEqual(result["unmatched_left_rows"], 1)
        self.assertEqual(result["coverage"], .75)
        self.assertTrue(result["multiplies_rows"])
        self.assertEqual(result["right_cardinality"], "repeated")

    def test_join_keeps_exact_identity_strings(self):
        result = probe_join({"columns": ["id"], "rows": [{"id": "001"}]},
                            {"columns": ["id"], "rows": [{"id": "1"}]}, "id", "id")
        self.assertEqual(result["matched_left_rows"], 0)


if __name__ == "__main__":
    unittest.main()
