"""Tests sans réseau : vrai SDK OpenAI, transport HTTP simulé."""

import base64
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import OpenAI
from PIL import Image

from my_art import generate_views as app


def sample_png(color="navy"):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


class ImageGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = sample_png()
        self.edited = sample_png("red")
        self.image = self.root / "tableau.png"
        self.image.write_bytes(self.source)
        self.folder = self.root / "result"
        self.folder.mkdir()
        _, self.metadata = app.read_image(self.image)

    def client(self, handler):
        client = OpenAI(api_key="test-placeholder", max_retries=0,
                        http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(client.close)
        return client

    def manifest(self):
        return {"model": "gpt-image-2", "size": "auto", "quality": "low",
                "views": [{"name": name, "prompt": prompt, "status": "pending"}
                          for name, prompt in app.build_prompts("la main gauche").items()]}

    def response(self):
        return httpx.Response(200, json={"created": 1, "data": [
            {"b64_json": base64.b64encode(self.edited).decode("ascii")}]})

    def test_each_edit_uploads_original_and_saves_valid_png(self):
        requests = []

        def handler(request):
            body = request.read()
            self.assertEqual(request.url.path, "/v1/images/edits")
            self.assertIn(self.source, body)
            self.assertNotIn(self.edited, body)
            self.assertIn(b'name="output_format"\r\n\r\npng', body)
            self.assertIn(b'name="model"\r\n\r\ngpt-image-2', body)
            requests.append(body)
            return self.response()

        manifest = self.manifest()
        with redirect_stdout(io.StringIO()):
            success = app.generate(self.client(handler), self.source, self.metadata,
                                   self.folder, manifest)
        self.assertTrue(success)
        self.assertEqual(len(requests), 3)
        self.assertEqual(manifest["status"], "completed_unreviewed")
        for view in manifest["views"]:
            self.assertIn(view["prompt"].encode(), requests[app.VIEWS.index(view["name"])])
            self.assertEqual((self.folder / view["file"]).read_bytes(), self.edited)

    def test_api_failure_stops_and_keeps_previous_image_without_secret(self):
        calls = []

        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return self.response()
            return httpx.Response(429, json={"error": {"message": "secret-that-must-not-leak",
                                                      "type": "insufficient_quota"}})

        errors = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(errors):
            success = app.generate(self.client(handler), self.source, self.metadata,
                                   self.folder, self.manifest())
        self.assertFalse(success)
        self.assertEqual(len(calls), 2)
        self.assertTrue((self.folder / "premier_plan.png").exists())
        persisted = (self.folder / "manifest.json").read_text(encoding="utf-8")
        self.assertNotIn("secret-that-must-not-leak", persisted + errors.getvalue())
        self.assertEqual(json.loads(persisted)["views"][2]["status"], "pending")

    def test_invalid_api_image_is_not_saved(self):
        def handler(request):
            return httpx.Response(200, json={"created": 1, "data": [{"b64_json": "broken!"}]})

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            success = app.generate(self.client(handler), self.source, self.metadata,
                                   self.folder, self.manifest())
        self.assertFalse(success)
        self.assertFalse(list(self.folder.glob("*.png")))

    def test_dry_run_needs_no_key_or_api_and_does_not_overwrite(self):
        output = self.root / "runs"
        with patch.dict(app.os.environ, {"OPENAI_API_KEY": ""}), \
                patch.object(app, "load_dotenv"), patch.object(app, "OpenAI") as sdk, \
                redirect_stdout(io.StringIO()):
            for _ in range(2):
                self.assertEqual(app.main([str(self.image), "--output", str(output),
                                          "--dry-run"]), 0)
            sdk.assert_not_called()
        runs = list(output.iterdir())
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertEqual((run / "original.png").read_bytes(), self.source)
            manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "dry_run")
            self.assertEqual(len(manifest["views"]), 3)

    def test_invalid_input_fails_before_api(self):
        broken = self.root / "invalid.png"
        broken.write_bytes(b"not an image")
        with patch.object(app, "OpenAI") as sdk, redirect_stderr(io.StringIO()):
            self.assertEqual(app.main([str(broken), "--dry-run"]), 1)
            sdk.assert_not_called()


if __name__ == "__main__":
    unittest.main()
