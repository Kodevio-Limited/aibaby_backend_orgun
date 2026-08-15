import io
from PIL import Image
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from babies.models import GenerationPrompt, GenerationTemplate, ParentPhotoScan, SafetySettings

User = get_user_model()


def _create_test_image():
    img = Image.new('RGB', (100, 100), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile('test.jpg', buf.read(), content_type='image/jpeg')


class AdminPromptTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            full_name='Admin', email='admin@example.com', password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_prompts(self):
        response = self.client.get(reverse('admin-prompt-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data['data'])

    def test_create_prompt(self):
        data = {
            'title': 'Test Prompt',
            'content': 'Generate a {gender} baby portrait.',
            'category': 'General Prompt',
            'status': 'active',
        }
        response = self.client.post(reverse('admin-prompt-list'), data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data']['title'], 'Test Prompt')


class AdminTemplateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            full_name='Admin', email='admin2@example.com', password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_list_templates(self):
        response = self.client.get(reverse('admin-template-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data['data'])

    def test_create_template(self):
        data = {
            'name': 'Test Template',
            'category': 'Portrait',
            'ai_prompt': 'Place in a studio.',
            'status': 'active',
        }
        response = self.client.post(reverse('admin-template-list'), data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data']['name'], 'Test Template')


class AdminModerationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            full_name='Admin', email='admin3@example.com', password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.regular_user = User.objects.create_user(
            full_name='User', email='user@example.com', password='userpass123'
        )
        self.scan = ParentPhotoScan.objects.create(
            user=self.regular_user,
            father_photo=_create_test_image(),
            mother_photo=_create_test_image(),
            overall_status='approved',
        )

    def test_list_moderation(self):
        response = self.client.get(reverse('admin-moderation-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data['data'])

    def test_get_moderation_detail(self):
        response = self.client.get(reverse('admin-moderation-detail', args=[self.scan.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['id'], str(self.scan.id))

    def test_moderation_stats(self):
        response = self.client.get(reverse('admin-moderation-stats'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('approved', response.data['data'])

    def test_safety_settings(self):
        response = self.client.get(reverse('admin-moderation-settings'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('enable_face_detection', response.data['data'])

    def test_reset_moderation(self):
        response = self.client.post(reverse('admin-moderation-reset', args=[self.scan.id]))
        self.assertEqual(response.status_code, 200)
        self.scan.refresh_from_db()
        self.assertEqual(self.scan.overall_status, 'pending')


class NonAdminAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='User', email='regular@example.com', password='userpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_non_admin_cannot_access_admin_prompts(self):
        response = self.client.get(reverse('admin-prompt-list'))
        self.assertEqual(response.status_code, 403)
