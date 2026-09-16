import copy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from my_art.bedrock import Completion
from my_art.config import ROOT, Settings
from my_art.corpus import Catalog, DirectContextProvider
from my_art.importer import import_artwork
from my_art.service import MuseumService
from my_art.visuals import MockImageProvider, VisualRequest


class PreparedViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "data"
        self.source = ROOT / "art_gallery" / "het steen"
        import_artwork(self.source, self.root)
        self.catalog = Catalog(self.root)
        self.provider = MockImageProvider(self.catalog)

    def test_import_preserves_sources_and_refuses_conflicting_reimport(self):
        self.assertEqual(import_artwork(self.source, self.root), "het-steen")
        for source in self.source.glob("*.txt"):
            target = self.root / "documents/het-steen" / source.name
            self.assertEqual(target.read_bytes(), source.read_bytes())
        target.write_text("Modification administrateur", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "déjà présent"):
            import_artwork(self.source, self.root)
        self.assertEqual(target.read_text(encoding="utf-8"), "Modification administrateur")

    def test_exact_images_and_unavailable_view_fallback(self):
        for focus, filename in (("foreground", "firstplan.png"), ("midground", "secondplan.png")):
            result = self.provider.generate(VisualRequest("het-steen", focus, "Une zone expliquée"))
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["file"], filename)
            self.assertEqual(result["sha256"], sha256((self.source / filename).read_bytes()).hexdigest())
            self.assertEqual(result["external_api_calls"], 0)
        missing = self.provider.generate(VisualRequest("het-steen", "detail", "Le chien seul"))
        self.assertEqual(missing["status"], "unavailable")
        self.assertIsNone(missing["file"])
        (self.root / "artworks/het-steen/firstplan.png").write_bytes(b"invalid image")
        self.assertEqual(self.provider.generate(VisualRequest("het-steen", "foreground", "Plan"))["status"], "unavailable")

    def test_orchestrator_routes_validated_steps_to_prepared_images(self):
        model = Mock()
        provider = Mock(wraps=self.provider)
        service = MuseumService(Settings(self.root), DirectContextProvider(self.root), model, provider)
        prepared = service.prepare("het-steen", mode="visit")
        source = prepared.context.sources[0]
        steps = [{"title": focus, "text": "Explication de test", "basis": "document",
                  "evidence": [{"source_id": source.id, "quote": source.text}],
                  "visual_focus": focus, "visual_target": "Zone du tableau"}
                 for focus in ("overview", "foreground", "midground")]
        model.complete.return_value = Completion({"status": "answered", "steps": steps}, {})
        result = service.run(prepared)
        self.assertEqual([call["file"] for call in result["visual_calls"]], ["firstplan.png", "secondplan.png"])
        self.assertEqual(provider.generate.call_count, 2)
        bad = copy.deepcopy(steps)
        bad[0]["evidence"][0]["quote"] = "Citation absente du corpus"
        model.complete.return_value = Completion({"status": "answered", "steps": bad}, {})
        provider.reset_mock()
        with self.assertRaises(ValueError):
            service.run(prepared)
        provider.generate.assert_not_called()

    def test_ui_can_simulate_both_views_without_bedrock(self):
        from streamlit.testing.v1 import AppTest

        with patch("my_art.config.Settings.from_env", return_value=Settings(self.root)), \
                patch("my_art.bedrock.BedrockModel.complete") as bedrock, \
                patch("my_art.cli.save_result", return_value=Path("test-result.json")):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            for focus in ("foreground", "midground"):
                app.selectbox(key="visual_choice_het-steen").set_value(focus)
                next(b for b in app.button if b.label == "Simuler la génération de cette vue").click().run()
                self.assertEqual(len(app.exception), 0)
                result = app.session_state["mock_visual"]["result"]
                self.assertEqual(result["request"]["focus"], focus)
                self.assertEqual(result["status"], "ready")
            bedrock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
