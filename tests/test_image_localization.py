"""Static image contract plus catalog checks for the permission regression."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImageLocalizationTest(unittest.TestCase):
    def test_dockerfile_prepares_translations_before_copy(self):
        dockerfile = (ROOT / "ollaya" / "Dockerfile").read_text(encoding="utf-8")
        create = "RUN install -d -o root -g root -m 0755 /usr/local/lib/i18n"
        copy = "COPY --chown=root:root --chmod=0644 i18n/en.json"
        smoke = "gosu ollaya:ollaya python3 -c"
        self.assertIn(create, dockerfile)
        self.assertIn(copy, dockerfile)
        self.assertIn(smoke, dockerfile)
        self.assertLess(dockerfile.index(create), dockerfile.index(copy))
        self.assertLess(dockerfile.index(copy), dockerfile.index(smoke))
        self.assertIn("/usr/local/lib/i18n/fr.json", dockerfile)

    def test_catalogs_are_utf8_json_and_translation_keys_match(self):
        folder = ROOT / "ollaya" / "i18n"
        en = json.loads((folder / "en.json").read_text(encoding="utf-8"))
        fr = json.loads((folder / "fr.json").read_text(encoding="utf-8"))
        self.assertTrue(en)
        self.assertEqual(en.keys(), fr.keys())
        self.assertTrue(all(isinstance(value, str) for value in en.values()))
        self.assertTrue(all(isinstance(value, str) for value in fr.values()))


if __name__ == "__main__":
    unittest.main()
