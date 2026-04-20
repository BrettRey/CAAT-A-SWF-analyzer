from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swf_anonymizer.anonymizer import anonymize_text
from swf_anonymizer.keymap import KeyMap, hash_alias
from swf_anonymizer.stable_ids import StableFacultyIds


class AnonymizerTests(unittest.TestCase):
    def test_reuses_faculty_token_for_teacher_name_and_id(self) -> None:
        text = "\n".join(
            [
                "Teacher Name: Doe, Jane",
                "ID: N12345678",
                "Supervisor's signature: Smith, John",
                "Email: jane.doe@example.com",
                "Phone: 416-555-1212",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap = KeyMap(Path(temp_dir_name) / "keymap.json")
            result = anonymize_text(text, keymap)

        self.assertIn("[FAC001]", result.text)
        self.assertIn("[PERSON001]", result.text)
        self.assertIn("[EMAIL001]", result.text)
        self.assertIn("[PHONE001]", result.text)
        self.assertEqual(keymap.aliases["Doe, Jane"], "FAC001")
        self.assertEqual(keymap.aliases["N12345678"], "FAC001")
        self.assertEqual(keymap.alias_hashes[hash_alias("Doe, Jane", keymap.salt)], "FAC001")
        self.assertEqual(result.primary_token, "FAC001")

    def test_persists_existing_token_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap_path = Path(temp_dir_name) / "keymap.json"
            keymap = KeyMap(keymap_path)
            first = anonymize_text("Teacher Name: Doe, Jane\nID: N12345678", keymap)
            keymap.save()
            second = anonymize_text("Teacher Name: Doe, Jane\nID: N12345678", keymap)

        self.assertEqual(first.primary_token, second.primary_token)
        self.assertEqual(second.primary_token, "FAC001")

    def test_saved_keymap_does_not_store_raw_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap_path = Path(temp_dir_name) / "keymap.json"
            keymap = KeyMap(keymap_path)
            anonymize_text("Teacher Name: Doe, Jane\nID: N12345678", keymap)
            keymap.save()
            payload = keymap_path.read_text(encoding="utf-8")

        self.assertNotIn("Doe, Jane", payload)
        self.assertNotIn("N12345678", payload)
        self.assertIn("alias_hashes", payload)
        self.assertIn("salt", payload)

    def test_stable_faculty_id_persists_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            root = Path(temp_dir_name)
            keymap = KeyMap(root / "keymap.json")
            stable_ids = StableFacultyIds.load(root / "stable_ids.json")

            first = anonymize_text("Teacher Name: Doe, Jane\nID: N12345678", keymap, stable_ids=stable_ids)
            stable_ids.save()

            reloaded = StableFacultyIds.load(root / "stable_ids.json")
            second = anonymize_text("Teacher Name: Doe, Jane\nID: N12345678", keymap, stable_ids=reloaded)

        self.assertRegex(first.stable_faculty_id or "", r"^FID[0-9A-F]{12}$")
        self.assertEqual(first.stable_faculty_id, second.stable_faculty_id)

    def test_legacy_unsalted_keymap_is_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap_path = Path(temp_dir_name) / "keymap.json"
            keymap_path.write_text(
                '{\n'
                f'  "alias_hashes": {{"{hash_alias("Doe, Jane")}": "FAC001"}},\n'
                '  "counters": {"FAC": 1}\n'
                '}\n',
                encoding="utf-8",
            )
            keymap = KeyMap.load(keymap_path)

            result = anonymize_text("Teacher Name: Doe, Jane", keymap)

        self.assertEqual(result.primary_token, "FAC001")
        self.assertIn(hash_alias("Doe, Jane", keymap.salt), keymap.alias_hashes)

    def test_anonymizes_unicode_name(self) -> None:
        text = "Teacher Name: García, José\nID: N12345678"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap = KeyMap(Path(temp_dir_name) / "keymap.json")
            result = anonymize_text(text, keymap)

        self.assertNotIn("García, José", result.text)
        self.assertIn("[FAC001]", result.text)

    def test_anonymizes_multiword_surname_without_partial_leak(self) -> None:
        text = "Teacher Name: van der Meer, Jan\nID: N12345678"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap = KeyMap(Path(temp_dir_name) / "keymap.json")
            result = anonymize_text(text, keymap)

        self.assertNotIn("van der", result.text)
        self.assertNotIn("Meer, Jan", result.text)
        self.assertIn("[FAC001]", result.text)

    def test_faculty_signature_can_seed_primary_token(self) -> None:
        text = "Faculty member's signature: O’Neil, Shauna"

        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap = KeyMap(Path(temp_dir_name) / "keymap.json")
            result = anonymize_text(text, keymap)

        self.assertEqual(result.primary_token, "FAC001")
        self.assertIn("[FAC001]", result.text)

    def test_does_not_anonymize_generic_comma_phrases_without_labels(self) -> None:
        text = "\n".join(
            [
                "Campus/Building: Lakeshore, Humber",
                "Program Group: Liberal Arts, Humber Polytechnic",
                "Some text about workload, weekly total",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap = KeyMap(Path(temp_dir_name) / "keymap.json")
            result = anonymize_text(text, keymap)

        self.assertIsNone(result.primary_token)
        self.assertIn("Lakeshore, Humber", result.text)
        self.assertIn("Liberal Arts, Humber Polytechnic", result.text)
        self.assertIn("workload, weekly total", result.text)
        self.assertNotIn("[FAC", result.text)
        self.assertNotIn("[PERSON", result.text)

    def test_generic_comma_phrases_survive_when_teacher_name_is_present(self) -> None:
        text = "\n".join(
            [
                "Teacher Name: Doe, Jane",
                "Campus/Building: Lakeshore, Humber",
                "Program Group: Liberal Arts, Humber Polytechnic",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir_name:
            keymap = KeyMap(Path(temp_dir_name) / "keymap.json")
            result = anonymize_text(text, keymap)

        self.assertIn("[FAC001]", result.text)
        self.assertIn("Lakeshore, Humber", result.text)
        self.assertIn("Liberal Arts, Humber Polytechnic", result.text)


if __name__ == "__main__":
    unittest.main()
