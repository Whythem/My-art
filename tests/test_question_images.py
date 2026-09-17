import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from my_art.bedrock import BedrockModel, Completion, SYSTEM
from my_art.config import Settings
from my_art.corpus import DirectContextProvider
from my_art.paths import ROOT
from my_art.service import MuseumService


class QuestionImageTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(ROOT / "data")
        self.model = Mock()
        self.service = MuseumService(self.settings, DirectContextProvider(self.settings.data_dir), self.model)

    def prepare(self):
        return self.service.prepare("het-steen", "Que représente le château ?")

    def answer(self, prepared):
        return {"status": "answered", "steps": [{
            "title": "Le château", "text": "Explication du château à partir des documents.",
            "basis": "document", "evidence": [{"source_id": prepared.context.sources[0].id}],
            "visual_focus": "foreground", "visual_target": "Le château visible au premier plan",
        }]}

    def test_all_images_are_sent_to_bedrock_without_visit_system_or_order(self):
        prepared = self.prepare()
        request = json.loads(prepared.prompt)
        self.assertNotIn("visit_structure", request)
        self.assertNotIn(SYSTEM, prepared.prompt)
        self.assertEqual(request["attached_images"], ["overview", "foreground", "midground"])
        self.assertEqual([i.focus for i in prepared.images], ["foreground", "midground"])
        for image in prepared.images:
            expected = self.service.catalog.image_bytes(prepared.artwork.model_copy(
                update={"image": prepared.artwork.views[image.focus].file}))
            self.assertEqual(image.data, expected)
        client = Mock()
        client.converse.return_value = {"stopReason": "tool_use", "output": {"message": {"content": [
            {"toolUse": {"name": "present_visit", "input": self.answer(prepared)}}]}}}
        self.service.model = BedrockModel(self.settings, client)
        result = self.service.run(prepared)
        kwargs = client.converse.call_args.kwargs
        self.assertNotIn("system", kwargs)
        content = kwargs["messages"][0]["content"]
        self.assertEqual([b["image"]["source"]["bytes"] for b in content if "image" in b],
                         [prepared.image] + [i.data for i in prepared.images])
        for focus in request["attached_images"]:
            self.assertTrue(any(b.get("text", "").startswith(f"Image : {focus}") for b in content))
        self.assertEqual(result["visit"]["steps"][0]["visual"]["file"], "firstplan.png")
        self.assertEqual(len(result["visual_calls"]), 1)
        visit = self.service.prepare("het-steen", mode="visit")
        self.service.model.complete(visit.prompt, visit.image)
        self.assertEqual(client.converse.call_args.kwargs["system"], [{"text": SYSTEM}])

    def test_text_only_request_has_no_attached_views(self):
        prepared = self.service.prepare("het-steen", "Que représente le château ?", include_image=False)
        self.assertIsNone(prepared.image)
        self.assertEqual(prepared.images, ())
        self.assertEqual(prepared.preview()["attached_images"], [])

    def test_question_can_observe_a_view_without_original_or_documents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "artworks/test"
            folder.mkdir(parents=True)
            Image.new("RGB", (20, 20), "blue").save(folder / "firstplan.png")
            service = MuseumService(Settings(root), DirectContextProvider(root), self.model)
            prepared = service.prepare("test", "Quelle couleur voit-on ?")
            self.assertIsNone(prepared.image)
            self.assertEqual(len(prepared.images), 1)
            self.model.complete.return_value = Completion({"status": "answered", "steps": [{
                "title": "Couleur", "text": "L’image est bleue.", "basis": "observation", "evidence": [],
                "visual_focus": "foreground", "visual_target": "La surface bleue",
            }]}, {})
            self.assertEqual(service.run(prepared)["calls"], 1)

    def test_question_ui_shows_selected_view_and_no_master_prompt(self):
        from streamlit.testing.v1 import AppTest
        prepared = self.prepare()
        self.model.complete.return_value = Completion(self.answer(prepared), {})
        with patch("my_art.ui.Settings.from_env", return_value=self.settings), \
                patch("my_art.ui.make_service", return_value=self.service), \
                patch("my_art.ui.save_result", return_value=Path("test-result.json")):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            next(w for w in app.selectbox if w.label == "Œuvre").set_value("het-steen").run()
            next(r for r in app.radio if r.label == "Que souhaitez-vous faire ?").set_value("Poser une question")
            app.text_area[0].set_value("Que représente le château ?")
            next(b for b in app.button if b.label == "Demander l'explication — appel Bedrock").click().run()
            self.assertFalse(app.exception)
            self.assertNotIn(SYSTEM.strip(), [t.value for t in app.text])
            self.assertEqual(len(app.get("image")), 2)  # Logo et premier plan choisi.
            self.assertIn("Le château", [h.value for h in app.subheader])
            self.assertEqual(self.model.complete.call_args.kwargs["mode"], "ask")
            self.assertEqual(len(self.model.complete.call_args.kwargs["images"]), 2)


if __name__ == "__main__":
    unittest.main()
