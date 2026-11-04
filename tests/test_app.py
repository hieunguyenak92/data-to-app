"""Exercise portable generation and the real HTTP editing/import contract."""
import base64
import csv
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/data-to-app/scripts"))
from data_to_app.build import build_app, build_demo  # noqa: E402 - bundled runtime path above
from data_to_app.engine import DataError  # noqa: E402
from data_to_app.server import AppServer  # noqa: E402


class BuildTests(unittest.TestCase):
    def test_new_portable_workspace_and_existing_output_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "app"
            result = build_demo(app)
            self.assertEqual(result["summary"]["active_rows"], 20)
            self.assertTrue((app / ".data/app.sqlite").is_file())
            self.assertTrue((app / "data_to_app/engine.py").is_file())
            self.assertIn("inputs/", (app / ".gitignore").read_text())
            before = (app / ".data/app.sqlite").read_bytes()
            with self.assertRaises(DataError):
                build_demo(app)
            self.assertEqual(before, (app / ".data/app.sqlite").read_bytes())

    def test_portable_entrypoint_runs_without_installed_skill_path(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "app"
            build_demo(app)
            child_env = dict(os.environ)
            child_env.pop("PYTHONPATH", None)
            child_env.pop("PYTHONHOME", None)
            child_env["PYTHONNOUSERSITE"] = "1"
            process = subprocess.Popen([sys.executable, str(app / "app.py"), "--port", "0"],
                cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=child_env)
            try:
                line = process.stdout.readline()
                self.assertIn("http://127.0.0.1:", line)
                port = int(line.strip().rsplit(":", 1)[1])
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                connection.request("GET", "/api/bootstrap")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["summary"]["active_rows"], 20)
                connection.close()
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=5)

    def test_source_path_cannot_escape_or_read_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "input"
            source.mkdir()
            (folder / "secret.csv").write_text("id,value\n1,private\n")
            model = {"version": 1, "tables": [{"id": "records", "source": "../secret.csv",
                "key": ["id"], "columns": ["id", "value"], "editable": ["value"]}]}
            config = folder / "model.json"
            config.write_text(json.dumps(model))
            with self.assertRaises(DataError):
                build_app(source, folder / "app", config)
            self.assertFalse((folder / "app").exists())

    def test_invalid_late_table_leaves_no_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "first.csv").write_text("id,value\n1,ok\n")
            (folder / "second.csv").write_text("id,value\n1,a\n1,b\n")
            tables = [{"id": name, "key": ["id"], "columns": ["id", "value"], "editable": []}
                      for name in ("first", "second")]
            model = folder / "model.json"
            model.write_text(json.dumps({"version": 1, "tables": tables}))
            with self.assertRaises(DataError):
                build_app(folder, folder / "app", model)
            self.assertFalse((folder / "app").exists())
            self.assertEqual(list(folder.glob(".dta-build-*")), [])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Path(self.temp.name) / "app"
        build_demo(self.app)
        self.server = AppServer(("127.0.0.1", 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.origin = f"http://127.0.0.1:{self.port}"
        _, self.boot = self.request("GET", "/api/bootstrap")

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        self.temp.cleanup()

    def request(self, method, path, value=None, headers=None, raw=False):
        request_headers = {"Origin": self.origin}
        if method == "POST":
            request_headers.update({"Content-Type": "application/json",
                "X-DTA-Token": getattr(self, "boot", {}).get("csrf_token", "")})
        request_headers.update(headers or {})
        content = value if raw else json.dumps(value) if value is not None else None
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request(method, path, body=content, headers=request_headers)
        response = connection.getresponse()
        body = response.read()
        content_type = response.getheader("Content-Type", "")
        status = response.status
        connection.close()
        return status, json.loads(body) if "application/json" in content_type else body

    def preview(self):
        fixture = ROOT / "skills/data-to-app/assets/examples/inventory/next/products.csv"
        return self.request("POST", "/api/import/preview", {"table": "products",
            "filename": "products.csv", "content_base64": base64.b64encode(fixture.read_bytes()).decode()})

    def test_edit_import_resolve_export_and_persistence(self):
        status, result = self.request("GET", "/api/rows?table=products&search=00128")
        self.assertEqual(status, 200)
        self.assertEqual(result["total"], 1)
        row = result["rows"][0]
        status, edited = self.request("POST", "/api/edit", {"table": "products", "row": row["id"],
            "values": {"reorder_level": "20", "notes": "Local purchasing decision"}, "revision": result["revision"]})
        self.assertEqual(status, 200)
        status, preview = self.preview()
        self.assertEqual(status, 200)
        self.assertEqual(preview["counts"]["new"], 1)
        self.assertEqual(preview["counts"]["missing"], 1)
        self.assertEqual(preview["counts"]["conflicts"], 2)
        status, imported = self.request("POST", "/api/import/apply", {"token": preview["token"], "revision": preview["revision"]})
        self.assertEqual(status, 200)
        _, changed = self.request("GET", "/api/rows?table=products&search=00128")
        self.assertEqual(changed["rows"][0]["values"]["reorder_level"], "20")
        self.assertEqual(changed["rows"][0]["values"]["stock"], "9")
        _, review = self.request("GET", "/api/conflicts")
        for conflict in review["conflicts"]:
            self.assertEqual(conflict["key_values"], {"sku": "00128"})
            choice = "local" if conflict["field"] == "reorder_level" else "source"
            status, resolved = self.request("POST", "/api/conflicts/resolve", {
                "id": conflict["id"], "choice": choice, "revision": review["revision"]})
            self.assertEqual(status, 200)
            review["revision"] = resolved["revision"]
        _, review = self.request("GET", "/api/conflicts")
        self.assertEqual(review["conflicts"], [])
        status, exported = self.request("GET", "/api/export?table=products")
        self.assertEqual(status, 200)
        records = list(csv.DictReader(io.StringIO(exported.decode("utf-8-sig"))))
        record = next(item for item in records if item["sku"] == "00128")
        self.assertEqual(record["reorder_level"], "20")
        self.assertEqual(record["notes"], "Supplier changed to Atelier")
        self.assertNotIn("00136", [item["sku"] for item in records])
        self.assertIn("00139", [item["sku"] for item in records])
        self.server.store.close()
        from data_to_app.engine import Store
        self.server.store = Store(self.app / ".data/app.sqlite")
        _, persisted = self.request("GET", "/api/rows?table=products&search=00128")
        self.assertEqual(persisted["rows"][0]["values"]["reorder_level"], "20")

    def test_stale_preview_cannot_apply_after_edit(self):
        _, preview = self.preview()
        _, rows = self.request("GET", "/api/rows?table=products&search=00128")
        self.request("POST", "/api/edit", {"table": "products", "row": rows["rows"][0]["id"],
            "values": {"notes": "Keep this later edit"}, "revision": rows["revision"]})
        status, error = self.request("POST", "/api/import/apply", {"token": preview["token"], "revision": preview["revision"]})
        self.assertEqual(status, 409)
        self.assertEqual(error["error"], "revision_conflict")
        _, rows = self.request("GET", "/api/rows?table=products&search=00128")
        self.assertEqual(rows["rows"][0]["values"]["stock"], "6")
        self.assertEqual(rows["rows"][0]["values"]["notes"], "Keep this later edit")

    def test_exact_row_reload_recovers_from_stale_editor(self):
        _, rows = self.request("GET", "/api/rows?table=products&search=00128")
        row = rows["rows"][0]
        self.request("POST", "/api/edit", {"table": "products", "row": row["id"],
            "values": {"notes": "Changed by another tab"}, "revision": rows["revision"]})
        stale = {"table": "products", "row": row["id"], "values": {"reorder_level": "21"}, "revision": rows["revision"]}
        self.assertEqual(self.request("POST", "/api/edit", stale)[0], 409)
        status, latest = self.request("GET", f'/api/row?table=products&id={row["id"]}')
        self.assertEqual(status, 200)
        self.assertEqual(latest["row"]["values"]["notes"], "Changed by another tab")
        self.assertGreater(latest["revision"], rows["revision"])
        status, saved = self.request("POST", "/api/edit", {**stale, "revision": latest["revision"]})
        self.assertEqual(status, 200)
        self.assertEqual(saved["row"]["values"]["notes"], "Changed by another tab")
        self.assertEqual(saved["row"]["values"]["reorder_level"], "21")

    def test_host_origin_token_and_data_paths_are_bounded(self):
        self.assertEqual(self.request("GET", "/api/bootstrap", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/edit", {}, headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/edit", {}, headers={"X-DTA-Token": ""})[0], 403)
        self.assertEqual(self.request("POST", "/api/edit", {}, headers={"X-DTA-Token": "é"})[0], 403)
        for path in ("/../model.json", "/.data/app.sqlite", "/%2e%2e/inputs/products.csv"):
            self.assertEqual(self.request("GET", path)[0], 404)
        self.assertEqual(self.request("GET", "/api/rows?table=products&limit=1000000")[0], 400)

    def test_bad_or_conflicting_upload_does_not_change_workspace(self):
        status, error = self.request("POST", "/api/import/preview", {"table": "products",
            "filename": "products.csv", "content_base64": "not base64!"})
        self.assertEqual(status, 400)
        self.assertEqual(self.request("POST", "/api/edit", "[]", raw=True)[0], 400)
        bad = b"sku,name,category,stock,reorder_level,notes\n1,a,x,1,1,a\n1,b,x,1,1,b\n"
        self.assertEqual(self.request("POST", "/api/import/preview", {"table": "products",
            "filename": "products.csv", "content_base64": base64.b64encode(bad).decode()})[0], 400)
        _, current = self.request("GET", "/api/bootstrap")
        self.assertEqual(current["revision"], self.boot["revision"])
        self.assertEqual(current["summary"]["active_rows"], 20)

    def test_repeated_identical_snapshot_is_no_op(self):
        _, preview = self.preview()
        _, imported = self.request("POST", "/api/import/apply", {"token": preview["token"], "revision": preview["revision"]})
        _, preview2 = self.preview()
        self.assertTrue(preview2["no_op"])
        status, repeated = self.request("POST", "/api/import/apply", {"token": preview2["token"], "revision": preview2["revision"]})
        self.assertEqual(status, 200)
        self.assertEqual(repeated["revision"], imported["revision"])
        _, history = self.request("GET", "/api/history")
        self.assertEqual(len(history["history"]), 3)


if __name__ == "__main__":
    unittest.main()
