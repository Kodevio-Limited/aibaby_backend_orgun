import os
import tempfile

import numpy as np
from PIL import Image
from django.test import TestCase

from babies.services.outfit_edit_service import OutfitEditService


class OutfitEditServiceTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.image_path = os.path.join(self.tmpdir, 'babies.png')
        self.service = OutfitEditService()
        self._build_garment_image()

    def _build_garment_image(self):
        """300x400 image: white studio background, grey garment band in the
        lower half (where the outfit sits below the chin/face)."""
        img = np.zeros((400, 300, 3), dtype=np.uint8)
        img[:] = (245, 245, 245)          # white background
        img[200:390, 20:280] = (120, 120, 120)  # grey garment band
        Image.fromarray(img, 'RGB').save(self.image_path)

    def _rgb_at(self, y, x):
        with Image.open(self.image_path) as img:
            rgba = img.convert('RGB')
            return rgba.getpixel((x, y))

    def test_parse_color_specific(self):
        self.assertEqual(self.service._parse_color('a red dress'), (220, 35, 45))
        self.assertEqual(self.service._parse_color('blue hoodie'), (35, 75, 215))
        # "navy blue" must beat plain "blue".
        self.assertEqual(self.service._parse_color('navy blue suit'), (40, 50, 130))
        self.assertIsNone(self.service._parse_color('a fancy suit'))

    def test_edit_outfit_recolors_garment_not_background(self):
        result = self.service.edit_outfit(self.image_path, 'a red dress')
        self.assertTrue(result)

        garment_px = self._rgb_at(250, 150)          # inside the garment band
        background_px = self._rgb_at(50, 150)        # top background

        r, g, b = garment_px
        self.assertGreater(r, g + 60)
        self.assertGreater(r, b + 60)

        # Background stays near-white (untouched).
        self.assertGreater(background_px[0], 200)
        self.assertGreater(background_px[1], 200)
        self.assertGreater(background_px[2], 200)

    def test_edit_outfit_returns_false_for_unknown_colour(self):
        self.assertFalse(self.service.edit_outfit(self.image_path, 'a sparkly suit'))
        # Image unchanged when no recognised colour.
        before = self._rgb_at(250, 150)
        self.assertEqual(before, (120, 120, 120))