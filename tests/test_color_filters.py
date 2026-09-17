import math
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from PIL import Image

from my_art.color_filters import OPTIONS, SIMULATION, color_aid_image, filter_markup
from my_art.paths import ROOT


class ColorFilterTests(unittest.TestCase):
    def test_daltonize_keeps_geometry_alpha_and_zero_strength_original_colors(self):
        source = Image.new("RGBA", (2, 1))
        source.putdata([(220, 40, 80, 127), (40, 180, 80, 255)])
        buffer = BytesIO()
        source.save(buffer, format="PNG")
        for kind in SIMULATION:
            transformed = Image.open(BytesIO(color_aid_image(buffer.getvalue(), kind, 1)))
            self.assertEqual(transformed.size, source.size)
            self.assertEqual(transformed.mode, "RGBA")
            self.assertEqual(transformed.getchannel("A").tobytes(), source.getchannel("A").tobytes())
            self.assertNotEqual(transformed.convert("RGB").tobytes(), source.convert("RGB").tobytes())
            unchanged = Image.open(BytesIO(color_aid_image(buffer.getvalue(), kind, 0)))
            self.assertEqual(unchanged.convert("RGB").tobytes(), source.convert("RGB").tobytes())

    def test_filters_keep_alpha_and_target_only_paintings(self):
        for kind in SIMULATION:
            markup = filter_markup(kind)
            self.assertIn("filter: none", markup)
            self.assertIn('class*="st-key-artwork_image_"', markup)
        self.assertIn("filter: none", filter_markup("normal"))

    def test_invalid_inputs_are_rejected(self):
        for strength in (-1, 2, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                color_aid_image(b"not-an-image", "protanopia", strength)
        with self.assertRaises(ValueError):
            filter_markup("<script>invalid</script>")

    def test_switching_all_filters_is_local_and_reversible(self):
        from streamlit.testing.v1 import AppTest
        original = ROOT / "data/artworks/het-steen/het_steen.jpg"
        before = original.read_bytes()
        with patch("my_art.bedrock.BedrockModel.complete") as model, \
                patch("my_art.view_cache.SimulatedImageGenerator.generate") as generator:
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
            for label, mode in OPTIONS.items():
                next(w for w in app.selectbox if w.label == "Contraste des images").set_value(label).run()
                self.assertFalse(app.exception)
                self.assertTrue(any(filter_markup(mode) in element.value for element in app.markdown))
                if mode in SIMULATION:
                    app.slider(key="color_filter_strength").set_value(0).run()
                    self.assertTrue(any(filter_markup(mode, 0) in element.value for element in app.markdown))
                    app.slider(key="color_filter_strength").set_value(60).run()
            next(w for w in app.selectbox if w.label == "Contraste des images").set_value("Normal").run()
            self.assertFalse(app.exception)
            self.assertTrue(any("filter: none" in element.value for element in app.markdown))
            model.assert_not_called()
            generator.assert_not_called()
        self.assertEqual(before, original.read_bytes())


if __name__ == "__main__":
    unittest.main()
