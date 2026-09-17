import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from my_art.config import Settings
from my_art.corpus import Catalog, DirectContextProvider
from my_art.discovery import catalog_snapshot
from my_art.paths import ROOT
from my_art.visuals import MockImageProvider, VisualRequest


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / "artworks/landscape"
        self.folder.mkdir(parents=True)
        self.metadata = self.folder / "metadata.json"
        self.metadata.write_text(json.dumps({
            "id": "landscape", "title": "Paysage", "artist": "Artiste de test", "image": None,
        }), encoding="utf-8")
        self.catalog = Catalog(self.root)

    def image(self, name):
        path = self.folder / name
        Image.new("RGB", (48, 32), "blue").save(path)
        return path

    def test_late_additions_and_removal_are_detected_without_rewriting_metadata(self):
        original_metadata = self.metadata.read_bytes()
        self.assertIsNone(self.catalog.get("landscape").image)
        image = self.image("landscape.jpg")
        self.image("firstplan.png")
        self.image("secondplan.png")
        artwork = self.catalog.get("landscape")
        self.assertEqual(artwork.image, "landscape.jpg")
        self.assertTrue(self.catalog.image_bytes(artwork))
        provider = MockImageProvider(self.catalog)
        for focus in ("foreground", "midground"):
            self.assertEqual(provider.generate(VisualRequest("landscape", focus, "Test"))["status"], "ready")
        image.unlink()
        self.assertIsNone(self.catalog.get("landscape").image)
        self.assertEqual(self.metadata.read_bytes(), original_metadata)

    def test_new_folder_without_metadata_has_no_invented_artist(self):
        folder = self.root / "artworks/new-work"
        folder.mkdir()
        Image.new("RGB", (48, 32), "blue").save(folder / "original.PNG")
        artwork = next(a for a in self.catalog.list() if a.id == "new-work")
        self.assertEqual(artwork.title, "New Work")
        self.assertEqual(artwork.artist, "Artiste non renseigné")
        self.assertEqual(artwork.image, "original.PNG")
        self.assertFalse((folder / "metadata.json").exists())
        with self.assertRaises(ValueError):
            self.catalog.get("missing")

    def test_explicit_metadata_takes_priority_even_when_file_is_missing(self):
        metadata = json.loads(self.metadata.read_text(encoding="utf-8"))
        metadata.update(image="chosen.jpg", views={"foreground": {
            "file": "custom.png", "label": "Vue relue", "description": "Description relue.",
        }})
        self.metadata.write_text(json.dumps(metadata), encoding="utf-8")
        self.image("original.jpg")
        self.image("firstplan.png")
        artwork = self.catalog.get("landscape")
        self.assertEqual(artwork.image, "chosen.jpg")
        self.assertEqual(artwork.views["foreground"].file, "custom.png")
        with self.assertRaises(ValueError):
            self.catalog.image_bytes(artwork)

    def test_ambiguous_images_and_views_are_not_selected_arbitrarily(self):
        self.image("a.jpg")
        self.image("b.jpg")
        self.image("firstplan.png")
        self.image("foreground.png")
        self.assertIsNone(self.catalog.get("landscape").image)
        self.assertNotIn("foreground", self.catalog.get("landscape").views)
        original = self.image("original.jpg")
        self.assertEqual(self.catalog.get("landscape").image, original.name)
        self.image("landscape.webp")
        self.assertEqual(self.catalog.get("landscape").image, "landscape.webp")

    def test_single_unlabelled_image_is_detected_and_invalid_metadata_still_rejected(self):
        self.image("photo.jpeg")
        self.assertEqual(self.catalog.get("landscape").image, "photo.jpeg")
        self.metadata.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.catalog.get("landscape")

    def test_document_additions_and_deletions_change_snapshot_and_context(self):
        before = catalog_snapshot(self.root)
        documents = self.root / "documents/landscape"
        documents.mkdir(parents=True)
        document = documents / "notice.txt"
        document.write_text("Texte de référence pour le paysage.", encoding="utf-8")
        after = catalog_snapshot(self.root)
        self.assertNotEqual(before, after)
        self.assertEqual(len(DirectContextProvider(self.root).retrieve("landscape").sources), 1)
        document.unlink()
        self.assertNotEqual(after, catalog_snapshot(self.root))
        self.assertFalse(DirectContextProvider(self.root).retrieve("landscape").sources)

    def test_watch_requests_refresh_only_on_changes(self):
        from my_art.ui import watch_catalog

        before = catalog_snapshot(self.root)
        with patch("my_art.ui.st.rerun") as rerun:
            watch_catalog.__wrapped__(self.root, before)
            rerun.assert_not_called()
            self.image("original.jpg")
            watch_catalog.__wrapped__(self.root, before)
            rerun.assert_called_once_with()

    def test_ui_refresh_detects_added_images_without_api_before_profile_validation(self):
        from streamlit.testing.v1 import AppTest

        with patch("my_art.ui.Settings.from_env", return_value=Settings(self.root)), \
                patch("my_art.bedrock.BedrockModel.complete") as complete:
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.selectbox(key="profile_contrast").disabled)
            self.image("landscape.jpg")
            self.image("firstplan.png")
            self.image("secondplan.png")
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertFalse(app.checkbox[0].disabled)
            self.assertTrue(app.checkbox[0].value)
            self.assertEqual(set(Catalog(self.root).get("landscape").views), {"foreground", "midground"})
            self.assertFalse(any(w.label == "Vue à demander" for w in app.selectbox))
            complete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
