from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from my_art.bedrock import Completion, SYSTEM
from my_art.config import Settings
from my_art.corpus import Catalog, DirectContextProvider, with_uploads
from my_art.paths import ROOT
from my_art.service import MuseumService


def response(prepared):
    source = prepared.context.sources[0]
    return {"status": "answered", "steps": [
        {"title": focus, "text": f"Explication {focus}", "basis": "document",
         "evidence": [{"source_id": source.id}],
         "visual_focus": focus, "visual_target": focus}
        for focus in ("overview", "foreground", "midground")
    ]}


class AccessibleVisitTests(unittest.TestCase):
    def test_every_delivered_artwork_and_level(self):
        settings = Settings(ROOT / "data")
        for artwork in Catalog(settings.data_dir).list():
            for level in ("simple", "detaille"):
                with self.subTest(artwork=artwork.id, level=level):
                    model = Mock()
                    service = MuseumService(settings, DirectContextProvider(settings.data_dir), model)
                    prepared = service.prepare(artwork.id, mode="visit", level=level)
                    self.assertTrue(prepared.context.sources)
                    self.assertIsNotNone(prepared.image)
                    model.complete.return_value = Completion(response(prepared), {})
                    result = service.run(prepared)
                    self.assertEqual(len(result["visit"]["steps"]), 3)
                    self.assertEqual(result["visit"]["steps"][0]["evidence"][0]["quote"],
                                     prepared.context.sources[0].text)
                    self.assertEqual([v["status"] for v in result["visual_calls"]], ["ready", "ready"])
                    model.complete.assert_called_once()
                    malformed = response(prepared)
                    malformed["steps"].reverse()
                    with self.assertRaisesRegex(ValueError, "trois parties"):
                        service._validate(malformed, prepared)
                    malformed["steps"].pop()
                    with self.assertRaises(ValueError):
                        service._validate(malformed, prepared)

    def test_document_layouts_are_combined_and_isolated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artworks/painting").mkdir(parents=True)
            for layout in ("documents/painting", "artworks/documents/painting", "artworks/painting/documents"):
                folder = root / layout
                folder.mkdir(parents=True)
                (folder / "notice.txt").write_text(f"Source du dossier {layout}.", encoding="utf-8")
            other = root / "artworks/documents/other"
            other.mkdir()
            (other / "notice.txt").write_text("AUTRE TABLEAU", encoding="utf-8")
            self.assertEqual([a.id for a in Catalog(root).list()], ["painting"])
            context = DirectContextProvider(root).retrieve("painting")
            self.assertEqual(len(context.sources), 3)
            self.assertEqual(len({s.id for s in context.sources}), 3)
            self.assertNotIn("AUTRE TABLEAU", str(context.as_dict()))

    def test_uploads_provenance_limits_and_no_persistence(self):
        settings = Settings(ROOT / "data")
        service = MuseumService(settings, DirectContextProvider(settings.data_dir), Mock())
        artwork = service.catalog.list()[0]
        original = service.prepare(artwork.id, mode="visit", include_image=False)
        files = [("notice.txt", "Une source personnelle additionnelle.".encode())]
        enriched = service.prepare(artwork.id, mode="visit", include_image=False, documents=files)
        self.assertNotEqual(original.context.version, enriched.context.version)
        self.assertTrue(enriched.context.sources[-1].id.startswith("u-"))
        self.assertEqual(original.context, service.prepare(artwork.id, mode="visit", include_image=False).context)
        for bad in ([('a.pdf', b'text')], [('a.txt', b'\xff')], [('a.txt', b'')],
                    [('a.txt', b'a' * 1_000_001)], files * 11):
            with self.subTest(bad=bad[0][0]), self.assertRaises(ValueError):
                with_uploads(original.context, artwork.id, bad)
        with self.assertRaises(ValueError):
            with_uploads(original.context, artwork.id, files, max_chars=10)

    def test_ui_displays_complete_visit_below_request_and_preserves_contrast(self):
        from streamlit.testing.v1 import AppTest
        settings = Settings(ROOT / "data")
        model = Mock()
        service = MuseumService(settings, DirectContextProvider(settings.data_dir), model)
        with patch("my_art.ui.Settings.from_env", return_value=settings), \
                patch("my_art.ui.make_service", return_value=service), \
                patch("my_art.ui.save_result", return_value=Path("test-result.json")):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            app.checkbox(key="disability_daltonisme").set_value(True).run()
            self.assertEqual(app.selectbox(key="profile_contrast").value, "Élevé (high contrast)")
            artwork_id = sorted(service.catalog.list(), key=lambda art: (art.demo, art.title))[0].id
            prepared = service.prepare(artwork_id, mode="visit")
            model.complete.return_value = Completion(response(prepared), {})
            next(b for b in app.button if b.label == "Valider mon profil").click().run()
            self.assertFalse(app.exception)
            for index, focus in enumerate(("overview", "foreground", "midground")):
                self.assertFalse(app.exception)
                texts = [t.value for t in app.text]
                self.assertIn(f"Explication {focus}", texts)
                self.assertEqual(sum(t.startswith("Explication ") for t in texts), 3)
                elements = list(app.main)
                submit_index = next(i for i, e in enumerate(elements)
                                    if e.type == "button" and e.label == "Demander l'explication — appel Bedrock")
                description_index = next(i for i, e in enumerate(elements)
                                         if e.type == "text" and e.value == f"Explication {focus}")
                self.assertLess(submit_index, description_index)
                # Logo, original, premier plan et second plan affichés ensemble.
                self.assertEqual(len(app.get("image")), 4)
                self.assertFalse(any(r.label == "Étape de la visite" for r in app.radio))
            next(w for w in app.selectbox if w.label == "Contraste des images").set_value("Élevé (high contrast)").run()
            self.assertTrue(any("contrast(1.6)" in m.value for m in app.markdown))
            model.complete.assert_called_once()
            self.assertIn(SYSTEM.strip(), [t.value for t in app.text])


if __name__ == "__main__":
    unittest.main()
