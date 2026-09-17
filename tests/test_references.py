import copy
import unittest
from unittest.mock import Mock

from my_art.config import Settings
from my_art.corpus import DirectContextProvider
from my_art.paths import ROOT
from my_art.schemas import MODEL_VISIT_SCHEMA
from my_art.service import MuseumService


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        settings = Settings(ROOT / "data")
        self.service = MuseumService(settings, DirectContextProvider(settings.data_dir), Mock())
        self.prepared = self.service.prepare("het-steen", "Qui est le peintre ?", include_image=False)

    def payload(self, source_id):
        return {"status": "answered", "steps": [{
            "title": "Le peintre", "text": "Le peintre est Rubens.", "basis": "document",
            "evidence": [{"source_id": source_id}], "visual_focus": "overview", "visual_target": "",
        }]}

    def test_every_het_steen_passage_can_be_quoted_by_reference_without_translation(self):
        for source in self.prepared.context.sources:
            with self.subTest(source=source.id):
                payload = self.payload(source.id)
                original = copy.deepcopy(payload)
                visit = self.service._validate(payload, self.prepared)
                self.assertEqual(visit.steps[0].evidence[0].quote, source.text)
                self.assertEqual(payload, original)

    def test_unknown_and_other_artwork_references_are_rejected(self):
        other = self.service.prepare("landscape-viewed-from-a-window", "Qui est le peintre ?", include_image=False)
        for source_id in ("invented", other.context.sources[0].id):
            with self.subTest(source=source_id), self.assertRaisesRegex(ValueError, "référence absente"):
                self.service._validate(self.payload(source_id), self.prepared)

    def test_fabricated_legacy_quote_is_not_replaced_by_a_real_source(self):
        payload = self.payload(self.prepared.context.sources[0].id)
        payload["steps"][0]["evidence"][0]["quote"] = "Cette phrase ne figure pas dans le corpus."
        with self.assertRaisesRegex(ValueError, "citation non retrouvée"):
            self.service._validate(payload, self.prepared)

    def test_model_contract_selects_references_without_generating_quotes(self):
        evidence = MODEL_VISIT_SCHEMA["properties"]["steps"]["items"]["properties"]["evidence"]["items"]
        self.assertEqual(evidence["required"], ["source_id"])
        self.assertNotIn("quote", evidence["properties"])
        self.assertFalse(evidence["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
