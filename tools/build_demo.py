"""Materialize a synthetic guided web preview from the actual merge engine."""
from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/data-to-app/scripts"))
from data_to_app.build import load_sources, read_manifest  # noqa: E402
from data_to_app.engine import Store  # noqa: E402
from data_to_app.io import read_table  # noqa: E402


def generate_states():
    example = ROOT / "skills/data-to-app/assets/examples/inventory"
    model = read_manifest(example / "model.json")
    sources = load_sources(example / "initial", model)
    with tempfile.TemporaryDirectory(prefix="dta-preview-") as directory:
        with Store(Path(directory) / "preview.sqlite") as store:
            store.bootstrap(model, sources)
            steps = []

            def capture(ident, title, description, preview=None):
                result = {"id": ident, "title": title, "description": description,
                    "summary": store.summary(), "rows": store.rows("products", include_missing=True, limit=100)["rows"],
                    "conflicts": store.conflicts(), "csv": store.export_csv("products")}
                if preview is not None:
                    result["preview"] = preview
                steps.append(result)

            capture("initial", "Start with your files", "Twelve products and eight order lines become a persistent local workspace. An identical duplicate is collapsed and leading-zero identifiers stay intact.")
            row = store.rows("products", search="00128")["rows"][0]
            store.edit_row("products", row["id"], {"reorder_level": "20"}, store.summary()["revision"])
            capture("local", "Make a local decision", "Change Studio Notebook's reorder level from 12 to 20. The source value and your decision are stored separately.")
            incoming = read_table(example / "next/products.csv")
            preview = store.preview_import("products", incoming)
            store.apply_import("products", incoming, preview["revision"])
            capture("incoming", "Bring in the next snapshot", "The source now says 14. Your local 20 remains visible while the app shows the three-way conflict. Other source fields update; missing records remain available.", preview)
            conflict = store.conflicts()[0]
            store.resolve_conflict(conflict["id"], "local", store.summary()["revision"])
            capture("resolved", "Keep the decision that matters", "Choose to keep 20. The conflict is resolved, the source remains 14, and export contains your effective active records.")
    return {"version": "0.1.0", "kind": "guided-synthetic-preview", "title": "Northstar Inventory",
            "columns": model["tables"][0]["columns"], "steps": steps}


def main():
    output = ROOT / "docs/demo"
    output.mkdir(exist_ok=True)
    target = output / "states.json"
    target.write_text(json.dumps(generate_states(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
