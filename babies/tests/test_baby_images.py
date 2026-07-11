import io
import tempfile
from PIL import Image
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from unittest.mock import patch

User = get_user_model()


def _create_test_image():
    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile('test.jpg', buf.read(), content_type='image/jpeg')


class BabyImageAuthTests(TestCase):
    def test_unauthenticated_access(self):
        client = APIClient()
        response = client.get(reverse('baby-image-list'))
        self.assertEqual(response.status_code, 401)


class BabyImageGenerateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Test User', email='test@example.com', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('babies.tasks.process_baby_generation.delay')
    def test_generate_baby(self, mock_delay):
        father = _create_test_image()
        mother = _create_test_image()
        data = {'father_photo': father, 'mother_photo': mother}
        response = self.client.post(reverse('generate-baby'), data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data']['generation_status'], 'pending')
        mock_delay.assert_called_once()

    @patch('babies.tasks.process_baby_generation.delay')
    def test_generate_with_options(self, mock_delay):
        father = _create_test_image()
        mother = _create_test_image()
        data = {
            'father_photo': father,
            'mother_photo': mother,
            'gender': 'boy',
            'age_stage': 'newborn',
            'background': 'studio',
        }
        response = self.client.post(reverse('generate-with-options'), data, format='multipart')
        self.assertEqual(response.status_code, 201)
        mock_delay.assert_called_once()

    def test_generate_without_images(self):
        response = self.client.post(reverse('generate-baby'), {}, format='multipart')
        self.assertEqual(response.status_code, 400)

    @patch('babies.tasks.process_baby_generation.delay')
    def test_baby_image_status(self, mock_delay):
        father = _create_test_image()
        mother = _create_test_image()
        data = {'father_photo': father, 'mother_photo': mother}
        response = self.client.post(reverse('generate-baby'), data, format='multipart')
        baby_id = response.data['data']['id']

        status_response = self.client.get(reverse('baby-status', args=[baby_id]))
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data['data']['id'], baby_id)

    def test_status_of_nonexistent_image(self):
        response = self.client.get(
            reverse('baby-status', args=['00000000-0000-0000-0000-000000000000'])
        )
        self.assertEqual(response.status_code, 404)

    @patch('babies.tasks.process_baby_generation.delay')
    def test_toggle_favorite(self, mock_delay):
        father = _create_test_image()
        mother = _create_test_image()
        data = {'father_photo': father, 'mother_photo': mother}
        response = self.client.post(reverse('generate-baby'), data, format='multipart')
        baby_id = response.data['data']['id']

        fav_response = self.client.post(reverse('toggle-favorite', args=[baby_id]))
        self.assertEqual(fav_response.status_code, 200)
        self.assertTrue(fav_response.data['data']['is_favorite'])

        unfav_response = self.client.post(reverse('toggle-favorite', args=[baby_id]))
        self.assertEqual(unfav_response.status_code, 200)
        self.assertFalse(unfav_response.data['data']['is_favorite'])
