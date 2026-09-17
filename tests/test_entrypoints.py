"""Vérifier les commandes et l'indépendance des installations facultatives."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from my_art.paths import ROOT


# Simuler une installation sans les dépendances de l'autre parcours.
BLOCK_IMPORTS = """
import importlib.abc
import runpy
import sys

class BlockOptionalDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in blocked:
            raise ImportError('Dépendance facultative chargée : ' + fullname)

sys.meta_path.insert(0, BlockOptionalDependencies())
runpy.run_module(module, run_name='__main__')
"""


class EntrypointTests(unittest.TestCase):
    def run_module(self, module, arguments, cwd, root, blocked):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)
        env["PYTHONIOENCODING"] = "utf-8"
        env["OPENAI_API_KEY"] = ""
        env.pop("OPENAI_IMAGE_MODEL", None)
        script = f"module = {module!r}\nblocked = {blocked!r}\n" + BLOCK_IMPORTS
        result = subprocess.run(
            [sys.executable, "-c", script, *arguments], cwd=cwd, env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_image_module_uses_repository_env_and_output_from_another_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repository = base / "repository"
            package = repository / "my_art"
            package.mkdir(parents=True)
            for filename in ("__init__.py", "paths.py", "generate_views.py"):
                shutil.copyfile(ROOT / "my_art" / filename, package / filename)
            (repository / ".env").write_text("OPENAI_IMAGE_MODEL=offline-test-model\n", encoding="utf-8")
            working = base / "elsewhere"
            working.mkdir()
            original = working / "original.png"
            Image.new("RGB", (32, 24), "blue").save(original)

            self.run_module("my_art.generate_views", [str(original), "--dry-run"],
                            working, repository, ["boto3", "streamlit", "pypdf"])

            manifests = list((repository / "output/imagegen").glob("*/manifest.json"))
            self.assertEqual(len(manifests), 1)
            manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
            self.assertEqual(manifest["model"], "offline-test-model")
            self.assertEqual(manifest["status"], "dry_run")
            self.assertEqual(len(manifest["views"]), 4)
            self.assertEqual((manifests[0].parent / "original.png").read_bytes(), original.read_bytes())
            self.assertFalse((working / "output").exists())

    def test_museum_help_does_not_require_openai(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_module("my_art", ["--help"], temporary, ROOT, ["openai"])
        self.assertIn("import-artwork", result.stdout)
        self.assertIn("init-demo", result.stdout)


if __name__ == "__main__":
    unittest.main()
