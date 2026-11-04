"""Keep the public walkthrough tied to actual source/local/incoming behavior."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preview_builder", ROOT / "tools/build_demo.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PreviewTests(unittest.TestCase):
    def test_demo_is_deterministic_and_source_backed(self):
        data = builder.generate_states()
        self.assertEqual(data, builder.generate_states())
        initial, local, incoming, resolved = data["steps"]
        def find(step, sku):
            return next(row for row in step["rows"] if row["values"]["sku"] == sku)
        self.assertEqual(find(initial, "00128")["values"]["reorder_level"], "12")
        self.assertEqual(find(local, "00128")["values"]["reorder_level"], "20")
        conflict = incoming["conflicts"][0]
        self.assertEqual((conflict["base"], conflict["local"], conflict["incoming"]), ("12", "20", "14"))
        self.assertTrue(find(incoming, "00136")["missing"])
        self.assertEqual(find(resolved, "00128")["source"]["reorder_level"], "14")
        self.assertEqual(find(resolved, "00128")["values"]["reorder_level"], "20")
        self.assertEqual(resolved["conflicts"], [])
        self.assertEqual(resolved["summary"]["imports"], 3)


if __name__ == "__main__":
    unittest.main()
