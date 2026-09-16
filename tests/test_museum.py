import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import boto3
from botocore.stub import Stubber
from botocore.exceptions import ProxyConnectionError, NoCredentialsError, SSLError
from PIL import Image
from pypdf import PdfWriter

from my_art.bedrock import BedrockModel, Completion, ModelError
from my_art.demo import init_demo
from my_art.config import Settings
from my_art.paths import ROOT
from my_art.corpus import Catalog, DirectContextProvider
from my_art.service import MuseumService
from my_art.schemas import VISIT_SCHEMA


class MuseumTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "data"
        init_demo(self.root)
        self.settings = Settings(self.root)
        self.provider = DirectContextProvider(self.root)
        self.model = Mock()
        self.service = MuseumService(self.settings, self.provider, self.model)

    def prepared(self):
        return self.service.prepare("demo-port", "Que voit-on au premier plan ?", include_image=False)

    def payload(self, prepared):
        source = next(s for s in prepared.context.sources if "barque rouge" in s.text)
        return {"status": "answered", "steps": [{
            "title": "La barque", "text": "La notice décrit une barque rouge au premier plan.",
            "basis": "document", "evidence": [{"source_id": source.id, "quote": source.text}],
            "visual_focus": "foreground", "visual_target": "La barque rouge décrite dans la notice.",
        }]}

    def test_isolation_and_provenance_change_when_document_changes(self):
        before = self.provider.retrieve("demo-port")
        self.assertNotIn("banc jaune", " ".join(s.text for s in before.sources))
        file = self.root / "documents/demo-port/notice.md"
        file.write_text(file.read_text(encoding="utf-8") + "\n\nUne nouvelle source de test.", encoding="utf-8")
        after = self.provider.retrieve("demo-port")
        self.assertNotEqual(before.version, after.version)
        self.assertEqual(before.sources[0].id, after.sources[0].id)

    def test_reject_path_traversal(self):
        for bad_id in ("../demo-port", "..\\demo-port", "C:/secrets"):
            with self.assertRaises(ValueError):
                self.provider.retrieve(bad_id)
        metadata = self.root / "artworks/demo-port/metadata.json"
        data = json.loads(metadata.read_text(encoding="utf-8"))
        data["image"] = "../../../outside.png"
        metadata.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            catalog = Catalog(self.root)
            catalog.image_bytes(catalog.get("demo-port"))

    def test_large_context_is_not_silently_truncated(self):
        with self.assertRaisesRegex(ValueError, "Corpus trop long"):
            DirectContextProvider(self.root, max_chars=100).retrieve("demo-port")
        self.model.complete.assert_not_called()

    def test_no_document_means_no_model_call(self):
        directory = self.root / "documents/demo-port"
        (directory / "notice.md").unlink()
        result = self.service.run(self.prepared())
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["visit"]["status"], "insufficient_sources")
        self.model.complete.assert_not_called()

    def test_valid_response_preserves_sources_and_records_one_call(self):
        prepared = self.prepared()
        self.model.complete.return_value = Completion(self.payload(prepared), {"inputTokens": 100}, "request-test")
        result = self.service.run(prepared)
        self.model.complete.assert_called_once_with(prepared.prompt, None)
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["context"]["version"], prepared.context.version)
        self.assertFalse(result["capabilities"]["image_generation"])

    def test_schema_exposes_local_limits_and_keeps_title_property(self):
        steps = VISIT_SCHEMA["properties"]["steps"]
        self.assertEqual(steps["maxItems"], 4)
        fields = steps["items"]["properties"]
        self.assertEqual(fields["title"]["maxLength"], 150)
        self.assertEqual(fields["evidence"]["items"]["properties"]["quote"]["maxLength"], 1200)
        self.assertFalse(steps["items"]["additionalProperties"])
        self.assertNotIn('"$ref"', json.dumps(VISIT_SCHEMA))

    def test_visual_labels_are_normalized_without_relaxing_citations(self):
        prepared = self.prepared()
        payload = self.payload(prepared)
        payload["steps"][0]["visual_target"] = ""
        self.assertEqual(self.service._validate(payload, prepared).steps[0].visual_target, "Premier plan")
        payload["steps"][0]["visual_focus"] = "none"
        payload["steps"][0]["visual_target"] = "Aucune vue nécessaire"
        self.assertEqual(self.service._validate(payload, prepared).steps[0].visual_target, "")
        payload["steps"][0]["evidence"] = []
        with self.assertRaises(ValueError):
            self.service._validate(payload, prepared)

    def test_schema_error_reports_field_without_generated_content(self):
        prepared = self.prepared()
        payload = self.payload(prepared)
        payload["steps"][0]["basis"] = "PRIVATE_GENERATED_VALUE"
        with self.assertRaisesRegex(ValueError, r"steps.0.basis: literal_error") as error:
            self.service._validate(payload, prepared)
        self.assertNotIn("PRIVATE_GENERATED_VALUE", str(error.exception))

    def test_rejects_invented_citations_and_visual_observations_without_image(self):
        prepared = self.prepared()
        payload = self.payload(prepared)
        cases = []
        bad = copy.deepcopy(payload)
        bad["steps"][0]["evidence"][0]["source_id"] = "unknown"
        cases.append(bad)
        bad = copy.deepcopy(payload)
        bad["steps"][0]["evidence"][0]["quote"] = "Une citation inventée qui ne figure dans aucun document."
        cases.append(bad)
        bad = copy.deepcopy(payload)
        bad["steps"][0]["evidence"] = []
        cases.append(bad)
        bad = copy.deepcopy(payload)
        bad["steps"][0]["basis"] = "observation"
        cases.append(bad)
        for bad in cases:
            with self.subTest(payload=bad), self.assertRaises(ValueError):
                self.service._validate(bad, prepared)

    def test_image_preparation_and_micro_text_only(self):
        path = self.root / "artworks/demo-port"
        Image.new("RGB", (1800, 900), "blue").save(path / "original.png")
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        metadata["image"] = "original.png"
        (path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        prepared = self.service.prepare("demo-port", "Décris la composition")
        with Image.open(io.BytesIO(prepared.image)) as image:
            self.assertEqual(image.size, (1600, 800))
            self.assertEqual(image.format, "JPEG")
        micro = MuseumService(Settings(self.root, model_id="eu.amazon.nova-micro-v1:0"), self.provider, self.model)
        with self.assertRaisesRegex(ValueError, "Micro"):
            micro.prepare("demo-port", "Que dit la notice ?")
        self.assertIsNone(micro.prepare("demo-port", "Que dit la notice ?", include_image=False).image)

    def test_scanned_or_blank_pdf_is_rejected(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        with (self.root / "documents/demo-port/scanned.pdf").open("wb") as file:
            writer.write(file)
        with self.assertRaisesRegex(ValueError, "PDF"):
            self.provider.retrieve("demo-port")

    def test_demo_install_never_overwrites_existing_data(self):
        with self.assertRaises(ValueError):
            init_demo(self.root)
        self.assertTrue((self.root / "documents/demo-port/notice.md").is_file())

    def test_bedrock_adapter_real_sdk_contract_without_network(self):
        client = boto3.client("bedrock-runtime", region_name="eu-west-3",
                              aws_access_key_id="fake", aws_secret_access_key="fake")
        self.addCleanup(client.close)
        stubber = Stubber(client)
        prepared = self.prepared()
        payload = self.payload(prepared)
        stubber.add_response("converse", {
            "output": {"message": {"role": "assistant", "content": [{"toolUse": {
                "toolUseId": "test-tool", "name": "present_visit", "input": payload}}]}},
            "stopReason": "tool_use", "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
            "metrics": {"latencyMs": 10},
        })
        with stubber:
            adapter = BedrockModel(self.settings, client)
            with patch.object(client, "converse", wraps=client.converse) as invoke:
                completion = adapter.complete(prepared.prompt, b"image-test-bytes")
                kwargs = invoke.call_args.kwargs
                self.assertEqual(kwargs["modelId"], "eu.amazon.nova-pro-v1:0")
                self.assertEqual(kwargs["messages"][0]["content"][1]["image"]["source"]["bytes"], b"image-test-bytes")
                self.assertEqual(kwargs["toolConfig"]["toolChoice"], {"tool": {"name": "present_visit"}})
                self.assertEqual(completion.payload, payload)
                invoke.assert_called_once()
        stubber.assert_no_pending_responses()

    def test_bedrock_errors_are_sanitized_and_not_retried(self):
        client = boto3.client("bedrock-runtime", region_name="eu-west-3",
                              aws_access_key_id="fake", aws_secret_access_key="fake")
        self.addCleanup(client.close)
        with Stubber(client) as stubber:
            stubber.add_client_error("converse", service_error_code="AccessDeniedException",
                                     service_message="SECRET_SHOULD_NOT_APPEAR")
            with self.assertRaises(ModelError) as error:
                BedrockModel(self.settings, client).complete("question", None)
            self.assertNotIn("SECRET", str(error.exception))
            stubber.assert_no_pending_responses()

    def test_truncated_model_output_is_rejected(self):
        client = Mock()
        client.converse.return_value = {"stopReason": "max_tokens", "output": {"message": {"content": []}}}
        with self.assertRaises(ModelError):
            BedrockModel(self.settings, client).complete("question", None)

    def test_local_errors_are_actionable_without_exposing_raw_details(self):
        for error in (ProxyConnectionError(proxy_url="SECRET"), NoCredentialsError(),
                      SSLError(endpoint_url="SECRET", error="SECRET")):
            client = Mock()
            client.converse.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(ModelError) as caught:
                BedrockModel(self.settings, client).complete("test", None)
            self.assertIn(type(error).__name__, str(caught.exception))
            self.assertNotIn("SECRET", str(caught.exception))

    def test_bearer_key_skips_ec2_lookup_and_signs_without_network(self):
        class StopBeforeSend(Exception):
            pass

        with patch.dict(os.environ, {"AWS_BEARER_TOKEN_BEDROCK": "test-local-token"}, clear=True):
            # Une session neuve évite les caches globaux entre tests.
            session = boto3.Session()
            def stop(request, **kwargs):
                self.assertIn("bedrock-runtime", request.url)
                self.assertEqual(request.headers["Authorization"], b"Bearer test-local-token")
                raise StopBeforeSend()
            with patch("my_art.bedrock.boto3.client", side_effect=session.client), \
                    patch("botocore.httpsession.URLLib3Session.send", side_effect=stop) as send:
                with self.assertRaises(StopBeforeSend):
                    BedrockModel(self.settings).complete("test", None)
                send.assert_called_once()


class AppTests(unittest.TestCase):
    def test_local_preview_and_guided_visit_with_fake_model(self):
        from streamlit.testing.v1 import AppTest

        settings = Settings(ROOT / "examples/museum")
        fake = Mock()
        service = MuseumService(settings, DirectContextProvider(settings.data_dir), fake)
        with patch("my_art.config.Settings.from_env", return_value=settings), \
                patch("my_art.ui.make_service", return_value=service), \
                patch("my_art.ui.save_result", return_value=Path("test-result.json")):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            self.assertEqual(len(app.exception), 0)
            app.radio[0].set_value("Suivre une visite guidée")
            app.button[0].click().run()
            self.assertEqual(len(app.exception), 0)
            fake.complete.assert_not_called()
            self.assertIn("Aucun appel API", app.success[0].value)
            prepared = service.prepare("demo-jardin", mode="visit")
            source = prepared.context.sources[0]
            fake.complete.return_value = Completion({"status": "answered", "steps": [{
                "title": "Une démonstration", "text": "Cette œuvre est fictive.", "basis": "document",
                "evidence": [{"source_id": source.id, "quote": source.text}],
                "visual_focus": "none", "visual_target": "",
            }]}, {})
            app.button[1].click().run()
            self.assertEqual(len(app.exception), 0)
            fake.complete.assert_called_once()
            self.assertTrue(any("Cette œuvre est fictive" in text.value for text in app.text))


if __name__ == "__main__":
    unittest.main()
