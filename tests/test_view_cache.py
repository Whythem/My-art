import json
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from my_art.config import Settings
from my_art.corpus import Catalog, DirectContextProvider
from my_art.importer import import_artwork
from my_art.paths import ROOT
from my_art.service import MuseumService
from my_art.view_cache import CACHE_DIR, SimulatedImageGenerator, ensure_artwork_views


class ViewCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / "artworks/new-painting"
        self.folder.mkdir(parents=True)
        Image.new("RGB", (48, 32), "blue").save(self.folder / "original.jpg")
        self.catalog = Catalog(self.root)
        self.generator = Mock(wraps=SimulatedImageGenerator())

    def ensure(self):
        return ensure_artwork_views(self.catalog, "new-painting", self.generator)

    def test_new_work_generates_once_and_restart_reuses_disk(self):
        events = self.ensure()
        self.assertEqual(self.generator.generate.call_count, 2)
        self.assertEqual([e["status"] for e in events], ["generated", "generated"])
        self.assertTrue(all(e["external_api_calls"] == 0 for e in events))
        self.assertEqual(set(self.catalog.get("new-painting").views), {"foreground", "midground"})
        for record_path in (self.folder / CACHE_DIR).glob("*.json"):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertTrue(record["placeholder"])
            self.assertTrue(record["simulated"])
            self.assertTrue(record["source_sha256"])
        before = {p.name: p.stat().st_mtime_ns for p in (self.folder / CACHE_DIR).iterdir()}
        another_generator = Mock(wraps=SimulatedImageGenerator())
        reused = ensure_artwork_views(Catalog(self.root), "new-painting", another_generator)
        another_generator.generate.assert_not_called()
        self.assertTrue(all(e["status"] == "cache_hit" for e in reused))
        self.assertEqual(before, {p.name: p.stat().st_mtime_ns for p in (self.folder / CACHE_DIR).iterdir()})

    def test_replacing_original_invalidates_cache_but_documents_do_not(self):
        first = self.ensure()
        (self.folder / "documents").mkdir()
        (self.folder / "documents/note.txt").write_text("Nouveau contexte documentaire.", encoding="utf-8")
        self.ensure()
        self.assertEqual(self.generator.generate.call_count, 2)
        Image.new("RGB", (48, 32), "red").save(self.folder / "original.jpg")
        self.assertFalse(self.catalog.get("new-painting").views)
        second = self.ensure()
        self.assertEqual(self.generator.generate.call_count, 4)
        self.assertNotEqual([e["file"] for e in first], [e["file"] for e in second])

    def test_changed_generator_version_invalidates_cache(self):
        self.ensure()
        with patch("my_art.view_cache.GENERATOR_VERSION", "mock-v2"):
            self.assertTrue(all(e["status"] == "generated" for e in self.ensure()))
        self.assertEqual(self.generator.generate.call_count, 4)

    def test_manual_plan_preserved_and_only_missing_plan_generated(self):
        manual = self.folder / "firstplan.png"
        Image.new("RGB", (48, 32), "green").save(manual)
        original = manual.read_bytes()
        events = self.ensure()
        self.assertEqual([e["status"] for e in events], ["provided", "generated"])
        self.generator.generate.assert_called_once()
        self.assertEqual(manual.read_bytes(), original)
        self.assertEqual(self.catalog.get("new-painting").views["foreground"].file, "firstplan.png")

    def test_corrupt_cache_regenerates_only_affected_plan(self):
        events = self.ensure()
        (self.folder / events[0]["file"]).write_bytes(b"broken")
        result = self.ensure()
        self.assertEqual(self.generator.generate.call_count, 3)
        self.assertEqual({e["focus"]: e["status"] for e in result},
                         {"foreground": "generated", "midground": "cache_hit"})

    def test_failed_generation_is_not_cached_and_next_attempt_recovers(self):
        self.generator.generate.side_effect = RuntimeError("Simulation interrompue")
        with self.assertRaises(RuntimeError):
            self.ensure()
        self.assertFalse(list((self.folder / CACHE_DIR).glob("*.json")))
        self.generator.generate.side_effect = None
        self.assertTrue(all(e["status"] == "generated" for e in self.ensure()))

    def test_simultaneous_requests_do_not_duplicate_generation(self):
        started, release = Event(), Event()
        errors = []
        def generate(original, focus, prompt):
            started.set()
            if not release.wait(5):
                raise RuntimeError("Test timeout")
            return original
        self.generator.generate.side_effect = generate
        def run():
            try:
                self.ensure()
            except Exception as exc:
                errors.append(exc)
        worker = Thread(target=run)
        worker.start()
        try:
            self.assertTrue(started.wait(5))
            other = Mock(wraps=SimulatedImageGenerator())
            pending = ensure_artwork_views(Catalog(self.root), "new-painting", other)
            self.assertTrue(all(e["status"] == "pending" for e in pending))
            other.generate.assert_not_called()
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertFalse(errors)
        self.assertEqual(self.generator.generate.call_count, 2)

    def test_import_prepares_plans_without_changing_original_or_metadata(self):
        metadata = {"id": "new-painting", "title": "Test", "artist": "Test", "image": "original.jpg"}
        (self.folder / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (self.folder / "notice.txt").write_text("Description de test de l’œuvre.", encoding="utf-8")
        target = self.root / "imported"
        with patch.object(SimulatedImageGenerator, "generate", wraps=SimulatedImageGenerator().generate) as generate:
            import_artwork(self.folder, target)
            import_artwork(self.folder, target)
            self.assertEqual(generate.call_count, 2)
        self.assertEqual(Catalog(target).get("new-painting").image, "original.jpg")
        self.assertEqual((target / "artworks/new-painting/metadata.json").read_bytes(),
                         (self.folder / "metadata.json").read_bytes())

    def test_ui_detects_new_artwork_and_service_reuses_cached_plans(self):
        from streamlit.testing.v1 import AppTest
        settings = Settings(self.root)
        with patch("my_art.ui.Settings.from_env", return_value=settings), \
                patch.object(SimulatedImageGenerator, "generate", wraps=SimulatedImageGenerator().generate) as generate:
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertEqual(generate.call_count, 2)
            app.run()
            self.assertFalse(app.exception)
            service = MuseumService(settings, DirectContextProvider(self.root), Mock())
            prepared = service.prepare("new-painting", "Que voit-on ?")
            self.assertEqual(len(prepared.images), 2)
            self.assertEqual(generate.call_count, 2)
            self.assertTrue(all(e["status"] == "cache_hit" for e in prepared.visual_preparation))


if __name__ == "__main__":
    unittest.main()
