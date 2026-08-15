import io
from PIL import Image
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from unittest.mock import patch

from babies.models import ParentPhotoScan

User = get_user_model()


def _create_test_image():
    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile('test.jpg', buf.read(), content_type='image/jpeg')


def _create_approved_scan(user):
    father = _create_test_image()
    mother = _create_test_image()
    scan = ParentPhotoScan.objects.create(
        user=user,
        father_photo=father,
        mother_photo=mother,
        overall_status='approved',
        father_scan_status='approved',
        mother_scan_status='approved',
        scan_result='Clean',
        confidence=1.0,
    )
    return scan


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
        scan = _create_approved_scan(self.user)
        data = {'parent_photo_scan_id': str(scan.id)}
        response = self.client.post(reverse('generate-baby'), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data']['generation_status'], 'pending')
        mock_delay.assert_called_once()

    @patch('babies.tasks.process_baby_generation.delay')
    def test_generate_with_options(self, mock_delay):
        scan = _create_approved_scan(self.user)
        data = {
            'parent_photo_scan_id': str(scan.id),
            'gender': 'boy',
            'age_stage': 'newborn',
            'background': 'studio',
        }
        response = self.client.post(reverse('generate-with-options'), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data']['generation_status'], 'pending')
        mock_delay.assert_called_once()

    def test_generate_without_scan(self):
        response = self.client.post(reverse('generate-baby'), {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_generate_with_unapproved_scan(self):
        scan = ParentPhotoScan.objects.create(
            user=self.user,
            father_photo=_create_test_image(),
            mother_photo=_create_test_image(),
            overall_status='rejected',
        )
        data = {'parent_photo_scan_id': str(scan.id)}
        response = self.client.post(reverse('generate-baby'), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'PHOTOS_NOT_APPROVED')

    @patch('babies.tasks.process_baby_generation.delay')
    def test_baby_image_status(self, mock_delay):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-baby'), {'parent_photo_scan_id': str(scan.id)}, format='json')
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
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-baby'), {'parent_photo_scan_id': str(scan.id)}, format='json')
        baby_id = response.data['data']['id']

        fav_response = self.client.post(reverse('toggle-favorite', args=[baby_id]))
        self.assertEqual(fav_response.status_code, 200)
        self.assertTrue(fav_response.data['data']['is_favorite'])

        unfav_response = self.client.post(reverse('toggle-favorite', args=[baby_id]))
        self.assertEqual(unfav_response.status_code, 200)
        self.assertFalse(unfav_response.data['data']['is_favorite'])


class ParentPhotoScanTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Test User', email='scan@example.com', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    @patch('babies.services.parent_photo_scan_service._dispatch_scan_task')
    def test_upload_scan(self, mock_task):
        data = {'father_photo': _create_test_image(), 'mother_photo': _create_test_image()}
        response = self.client.post(reverse('parent-photo-scan-upload'), data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data['data'])
        mock_task.assert_called_once()

    def test_upload_scan_without_images(self):
        response = self.client.post(reverse('parent-photo-scan-upload'), {}, format='multipart')
        self.assertEqual(response.status_code, 400)

    def test_get_scan_status(self):
        scan = _create_approved_scan(self.user)
        response = self.client.get(reverse('parent-photo-scan-status', args=[scan.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['id'], str(scan.id))


class ActiveTemplateListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Test User', email='templates@example.com', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_active_templates(self):
        response = self.client.get(reverse('active-templates'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
