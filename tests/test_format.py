from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from locdata_repacker.format import pack_locdata, read_editable, unpack_locdata, write_editable


class LocdataFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = ROOT / "sample" / "locdata.md"

    def test_source_decodes_expected_entries(self) -> None:
        document = unpack_locdata(self.corpus)
        self.assertEqual(len(document.entries), 3439)
        by_key = {entry.key: entry.text for entry in document.entries}
        self.assertEqual(by_key["#T1_1_NAME"], "Basic Tutorial")
        self.assertIn("Developers", by_key["#CREDITS"])

    def test_unchanged_round_trip_is_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            editable = Path(temp) / "locdata.txt"
            target = Path(temp) / "locdata.md"
            document = unpack_locdata(self.corpus)
            write_editable(document, editable)
            self.assertTrue(editable.with_suffix(".template").is_file())
            self.assertNotIn("template_base64", editable.read_text(encoding="utf-8"))
            pack_locdata(read_editable(editable), target)
            self.assertEqual(target.read_bytes(), self.corpus.read_bytes())

    def test_missing_companion_template_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            editable = Path(temp) / "locdata.txt"
            write_editable(unpack_locdata(self.corpus), editable)
            editable.with_suffix(".template").unlink()
            with self.assertRaisesRegex(Exception, "Companion template not found"):
                read_editable(editable)

    def test_longer_and_shorter_edits_reparse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            editable = Path(temp) / "locdata.txt"
            target = Path(temp) / "locdata.md"
            document = unpack_locdata(self.corpus)
            write_editable(document, editable)
            payload = json.loads(editable.read_text(encoding="utf-8"))
            for item in payload["entries"]:
                if item["key"] == "#T1_1_NAME":
                    item["text"] = "A Much Longer Tutorial Name"
                if item["key"] == "#TIP1":
                    item["text"] = "Grid tip."
            editable.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            pack_locdata(read_editable(editable), target)
            rebuilt = {entry.key: entry.text for entry in unpack_locdata(target).entries}
            self.assertEqual(rebuilt["#T1_1_NAME"], "A Much Longer Tutorial Name")
            self.assertEqual(rebuilt["#TIP1"], "Grid tip.")


if __name__ == "__main__":
    unittest.main()
