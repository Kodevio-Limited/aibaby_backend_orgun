import os
import tempfile

from PIL import Image
from django.test import TestCase
from unittest.mock import patch

from babies.services.image_processing_service import (
    ImageProcessingService,
    OUTPUT_SIZE,
)


def _make_jpeg(path, size=(400, 400)):
    img = Image.new('RGB', size, color='blue')
    img.save(path, format='JPEG')


class ImageProcessingServiceTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.image_path = os.path.join(self.tmpdir, 'generated.jpg')
        _make_jpeg(self.image_path)

    def test_crop_to_face_returns_none_when_no_face(self):
        service = ImageProcessingService()
        self.assertIsNone(service.crop_to_face(self.image_path))

    def test_crop_and_save_no_face_keeps_original(self):
        service = ImageProcessingService()
        self.assertFalse(service.crop_and_save(self.image_path))
        self.assertGreater(os.path.getsize(self.image_path), 0)

    def test_crop_normalises_to_fixed_portrait_output(self):
        service = ImageProcessingService()
        with patch.object(service, '_detect_faces', return_value=[(100, 200, 180, 80)]):
            cropped = service.crop_to_face(self.image_path)
        self.assertIsNotNone(cropped)
        self.assertEqual(cropped.size, OUTPUT_SIZE)

    def test_crop_and_save_writes_fixed_size_file(self):
        service = ImageProcessingService()
        with patch.object(service, '_detect_faces', return_value=[(100, 200, 180, 80)]):
            self.assertTrue(service.crop_and_save(self.image_path))
        with Image.open(self.image_path) as img:
            self.assertEqual(img.size, OUTPUT_SIZE)

    def test_best_face_picks_largest_most_central(self):
        # Two faces: a small off-centre one and a larger central one.
        faces = [
            (10, 60, 40, 20),     # small, top-left
            (100, 300, 220, 150),  # large, central
        ]
        best = ImageProcessingService._best_face(faces, 400, 400)
        self.assertEqual(best, faces[1])

    def test_portrait_crop_keeps_face_in_upper_half(self):
        # A face that sits low in the image; the crop anchors it to the upper half.
        crop = ImageProcessingService._portrait_crop((250, 300, 350, 150), 400, 400)
        self.assertIsNotNone(crop)
        left, top, right, bottom = crop
        # 3:4 portrait aspect ratio.
        self.assertAlmostEqual((right - left) / (bottom - top), 3 / 4, places=2)