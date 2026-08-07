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

from locdata_repacker.format import (
    LocdataEntry,
    LocdataFile,
    LocdataFormatError,
    detect_encoding,
    normalize_encoding,
    pack_locdata,
    read_editable,
    unpack_locdata,
    write_editable,
)


RUSSIAN_STRINGS = (
    "Ратуша",
    "Гильдия воинов",
    "Атака",
    "Защита",
    "Здоровье",
    "Крестьянин собирает золото в казну королевства.",
    "Постройте гильдию, чтобы нанимать героев.",
    "Вражеские войска приближаются с севера!",
    "Ты уверен, что хочешь выйти из игры?",
    "Продолжить",
)


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


class CodePageTests(unittest.TestCase):
    """The Russian release stores text in Windows-1251, not Windows-1252."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = ROOT / "sample" / "locdata.md"

    def _russian_build(self, directory: Path) -> Path:
        """Rebuild the sample container with Cyrillic text in Windows-1251."""
        western = unpack_locdata(self.corpus)
        entries = tuple(
            LocdataEntry(entry.key, RUSSIAN_STRINGS[index % len(RUSSIAN_STRINGS)] if entry.text else "")
            for index, entry in enumerate(western.entries)
        )
        target = directory / "locdata-ru.md"
        pack_locdata(LocdataFile(entries, western.template, "locdata.md", "cp1251"), target)
        return target

    def test_western_sample_is_detected_as_cp1252(self) -> None:
        self.assertEqual(detect_encoding(self.corpus.read_bytes()), "cp1252")
        self.assertEqual(unpack_locdata(self.corpus).encoding, "cp1252")

    def test_russian_build_is_detected_as_cp1251(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            russian = self._russian_build(Path(temp))
            self.assertEqual(detect_encoding(russian.read_bytes()), "cp1251")
            document = unpack_locdata(russian)
            self.assertEqual(document.encoding, "cp1251")
            self.assertEqual(document.entries[0].text, "Ратуша")

    def test_cp1252_on_a_russian_build_produces_the_old_mojibake(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            russian = self._russian_build(Path(temp))
            document = unpack_locdata(russian, "cp1252")
            self.assertEqual(document.encoding, "cp1252")
            self.assertEqual(document.entries[0].text, "Ðàòóøà")

    def test_russian_round_trip_is_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            russian = self._russian_build(root)
            editable, rebuilt = root / "locdata.txt", root / "rebuilt.md"
            write_editable(unpack_locdata(russian), editable)
            pack_locdata(read_editable(editable), rebuilt)
            self.assertEqual(rebuilt.read_bytes(), russian.read_bytes())

    def test_mojibake_round_trip_is_also_byte_exact(self) -> None:
        """A misdetection must never corrupt an unedited file."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            russian = self._russian_build(root)
            rebuilt = root / "rebuilt.md"
            pack_locdata(unpack_locdata(russian, "cp1252"), rebuilt)
            self.assertEqual(rebuilt.read_bytes(), russian.read_bytes())

    def test_edited_cyrillic_survives_a_repack(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            russian = self._russian_build(root)
            editable, rebuilt = root / "locdata.txt", root / "rebuilt.md"
            write_editable(unpack_locdata(russian), editable)
            payload = json.loads(editable.read_text(encoding="utf-8"))
            self.assertEqual(payload["encoding"], "cp1251")
            payload["entries"][0]["text"] = "Совершенно новое название"
            editable.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            pack_locdata(read_editable(editable), rebuilt)
            self.assertEqual(unpack_locdata(rebuilt).entries[0].text, "Совершенно новое название")

    def test_editable_records_the_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            editable = Path(temp) / "locdata.txt"
            write_editable(unpack_locdata(self.corpus), editable)
            self.assertEqual(json.loads(editable.read_text(encoding="utf-8"))["encoding"], "cp1252")

    def test_editable_without_encoding_still_repacks_as_cp1252(self) -> None:
        """Text files written before code-page support carry no marker."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            editable, rebuilt = root / "locdata.txt", root / "rebuilt.md"
            write_editable(unpack_locdata(self.corpus), editable)
            payload = json.loads(editable.read_text(encoding="utf-8"))
            del payload["encoding"]
            editable.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            document = read_editable(editable)
            self.assertEqual(document.encoding, "cp1252")
            pack_locdata(document, rebuilt)
            self.assertEqual(rebuilt.read_bytes(), self.corpus.read_bytes())

    def test_cyrillic_rejected_in_a_western_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            editable = Path(temp) / "locdata.txt"
            write_editable(unpack_locdata(self.corpus), editable)
            payload = json.loads(editable.read_text(encoding="utf-8"))
            payload["entries"][0]["text"] = "Ратуша"
            editable.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(LocdataFormatError, "Windows-1252"):
                read_editable(editable)

    def test_unknown_encoding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            editable = Path(temp) / "locdata.txt"
            write_editable(unpack_locdata(self.corpus), editable)
            payload = json.loads(editable.read_text(encoding="utf-8"))
            payload["encoding"] = "utf-8"
            editable.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(LocdataFormatError, "Declared encoding"):
                read_editable(editable)

    def test_encoding_aliases(self) -> None:
        for value in ("cp1251", "CP-1251", "windows_1251", "Cyrillic", "russian"):
            self.assertEqual(normalize_encoding(value), "cp1251")
        for value in ("cp1252", "Windows-1252", "western"):
            self.assertEqual(normalize_encoding(value), "cp1252")


if __name__ == "__main__":
    unittest.main()
