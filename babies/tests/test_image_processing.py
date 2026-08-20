import os
import tempfile

import numpy as np
from PIL import Image
from django.test import TestCase
from unittest.mock import patch

from babies.services.image_processing_service import ImageProcessingService


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

    def test_crop_to_face_uses_detected_box(self):
        service = ImageProcessingService()
        with patch.object(service, '_dlib_face_box', return_value=(100, 200, 180, 80)):
            with patch('face_recognition.load_image_file') as mock_load:
                mock_load.return_value = np.zeros((300, 300, 3), dtype=np.uint8)
                cropped = service.crop_to_face(self.image_path)
        self.assertIsNotNone(cropped)
        self.assertLess(cropped.width * cropped.height, 400 * 400)

    def test_crop_and_save_writes_cropped_file(self):
        service = ImageProcessingService()
        with patch.object(service, '_dlib_face_box', return_value=(100, 200, 180, 80)):
            with patch('face_recognition.load_image_file') as mock_load:
                mock_load.return_value = np.zeros((300, 300, 3), dtype=np.uint8)
                self.assertTrue(service.crop_and_save(self.image_path))
        with Image.open(self.image_path) as img:
            self.assertLess(img.width * img.height, 400 * 400)