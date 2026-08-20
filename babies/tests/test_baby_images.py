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


class DerivativeContextTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Test User', email='deriv@example.com', password='testpass123', is_pro=True
        )
        self.client.force_authenticate(user=self.user)

    def _make_base_image(self):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-with-options'), {
            'parent_photo_scan_id': str(scan.id),
            'gender': 'girl',
            'age_stage': '5y',
            'background': 'nature',
            'outfit': 'a yellow dress',
        }, format='json')
        return response.data['data']['id']

    @patch('babies.tasks.process_baby_generation.delay')
    def test_generation_context_snapshot_has_photos_and_scan(self, mock_delay):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-with-options'), {
            'parent_photo_scan_id': str(scan.id),
            'gender': 'boy',
            'age_stage': '6m',
            'background': 'studio',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        snapshot = response.data['data']['request_context']
        self.assertEqual(snapshot['parent_photo_scan_id'], str(scan.id))
        self.assertTrue(snapshot['father_photo'])
        self.assertTrue(snapshot['mother_photo'])
        self.assertIn('6 month old baby', snapshot['age_descriptor'])

    @patch('babies.tasks.process_baby_generation.delay')
    def test_change_outfit_preserves_full_context(self, mock_delay):
        base_id = self._make_base_image()
        response = self.client.post(reverse('change-outfit', args=[base_id]), {'outfit': 'a red dress'}, format='json')
        self.assertEqual(response.status_code, 201)
        data = response.data['data']
        self.assertEqual(data['gender'], 'girl')
        self.assertEqual(data['age_stage'], '5y')
        self.assertEqual(data['background'], 'nature')
        self.assertEqual(data['outfit'], 'a red dress')

    @patch('babies.tasks.process_baby_generation.delay')
    def test_change_age_preserves_outfit(self, mock_delay):
        base_id = self._make_base_image()
        response = self.client.post(reverse('change-age', args=[base_id]), {'age_stage': '3y'}, format='json')
        self.assertEqual(response.status_code, 201)
        data = response.data['data']
        self.assertEqual(data['age_stage'], '3y')
        self.assertEqual(data['outfit'], 'a yellow dress')
        self.assertEqual(data['gender'], 'girl')
        self.assertEqual(data['background'], 'nature')

    @patch('babies.tasks.process_baby_generation.delay')
    def test_change_outfit_then_change_age_walks_chain(self, mock_delay):
        base_id = self._make_base_image()
        outfit_response = self.client.post(reverse('change-outfit', args=[base_id]), {'outfit': 'blue jeans'}, format='json')
        outfit_id = outfit_response.data['data']['id']

        age_response = self.client.post(reverse('change-age', args=[outfit_id]), {'age_stage': '7y'}, format='json')
        self.assertEqual(age_response.status_code, 201)
        data = age_response.data['data']
        self.assertEqual(data['age_stage'], '7y')
        self.assertEqual(data['outfit'], 'blue jeans')

    @patch('babies.tasks.process_baby_generation.delay')
    def test_change_age_context_snapshot_holds_request_age(self, mock_delay):
        base_id = self._make_base_image()
        response = self.client.post(reverse('change-age', args=[base_id]), {'age_stage': '4y'}, format='json')
        self.assertEqual(response.status_code, 201)
        snapshot = response.data['data']['request_context']
        self.assertEqual(snapshot['age_stage'], '4y')
        self.assertIn('4 year old child', snapshot['age_descriptor'])

    @patch('babies.tasks.process_baby_generation.delay')
    def test_generation_prompt_text_contains_request_age(self, mock_delay):
        base_id = self._make_base_image()
        response = self.client.post(reverse('change-age', args=[base_id]), {'age_stage': '4y'}, format='json')
        self.assertEqual(response.status_code, 201)
        baby_id = response.data['data']['id']

        from babies.models import BabyImage
        from babies.services.generation_service import GenerationService
        from babies.prompt_builder import build_prompt_extra
        baby_image = BabyImage.objects.get(id=baby_id)
        with patch('replicate.Client'):
            prompt, _ = GenerationService().build_prompt(
                baby_image=baby_image,
                gender=baby_image.gender,
                age_stage=baby_image.age_stage,
                background=baby_image.background,
                outfit=baby_image.outfit,
                template=baby_image.generation_template,
                prompt_extra=build_prompt_extra(baby_image),
            )
        self.assertIn('4 year old child', prompt)

    @patch('babies.tasks.process_baby_generation.delay')
    def test_generation_prompt_text_contains_request_outfit(self, mock_delay):
        base_id = self._make_base_image()
        response = self.client.post(reverse('change-outfit', args=[base_id]), {'outfit': 'a green hoodie'}, format='json')
        self.assertEqual(response.status_code, 201)
        baby_id = response.data['data']['id']

        from babies.models import BabyImage
        from babies.services.generation_service import GenerationService
        from babies.prompt_builder import build_prompt_extra
        baby_image = BabyImage.objects.get(id=baby_id)
        with patch('replicate.Client'):
            prompt, _ = GenerationService().build_prompt(
                baby_image=baby_image,
                gender=baby_image.gender,
                age_stage=baby_image.age_stage,
                background=baby_image.background,
                outfit=baby_image.outfit,
                template=baby_image.generation_template,
                prompt_extra=build_prompt_extra(baby_image),
            )
        self.assertIn('wearing a green hoodie', prompt)
        self.assertIn('5 year old child', prompt)


class ProPlanGatingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Free User', email='free@example.com', password='testpass123', is_pro=False
        )
        self.client.force_authenticate(user=self.user)

    @patch('babies.tasks.process_baby_generation.delay')
    def test_free_user_can_generate_newborn(self, mock_delay):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-with-options'), {
            'parent_photo_scan_id': str(scan.id),
            'gender': 'boy',
            'age_stage': '6m',
            'background': 'studio',
        }, format='json')
        self.assertEqual(response.status_code, 201)

    @patch('babies.tasks.process_baby_generation.delay')
    def test_free_user_blocked_from_1y(self, mock_delay):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-with-options'), {
            'parent_photo_scan_id': str(scan.id),
            'gender': 'boy',
            'age_stage': '1y',
            'background': 'studio',
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'PRO_PLAN_REQUIRED')

    @patch('babies.tasks.process_baby_generation.delay')
    def test_free_user_blocked_from_2y_change_age(self, mock_delay):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-with-options'), {
            'parent_photo_scan_id': str(scan.id),
            'gender': 'girl',
            'age_stage': '6m',
            'background': 'home',
        }, format='json')
        base_id = response.data['data']['id']

        change_response = self.client.post(reverse('change-age', args=[base_id]), {'age_stage': '2y'}, format='json')
        self.assertEqual(change_response.status_code, 403)
        self.assertEqual(change_response.data['code'], 'PRO_PLAN_REQUIRED')

    @patch('babies.tasks.process_baby_generation.delay')
    def test_timeline_gates_each_stage(self, mock_delay):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-timeline'), {
            'parent_photo_scan_id': str(scan.id),
            'timeline': ['3m', '1y'],
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'PRO_PLAN_REQUIRED')


class TimelineGenerationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Pro User', email='timeline@example.com', password='testpass123', is_pro=True
        )
        self.client.force_authenticate(user=self.user)

    @patch('babies.tasks.process_baby_generation.delay')
    def test_timeline_creates_one_image_per_stage(self, mock_delay):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-timeline'), {
            'parent_photo_scan_id': str(scan.id),
            'timeline': ['3m', '6m', '1y'],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        images = response.data['data']
        self.assertEqual(len(images), 3)
        self.assertEqual([i['age_stage'] for i in images], ['3m', '6m', '1y'])
        self.assertEqual([i['timeline'] for i in images], ['3m', '6m', '1y'])
        self.assertEqual(mock_delay.call_count, 3)

    @patch('babies.tasks.process_baby_generation.delay')
    def test_timeline_accepts_single_stage_string(self, mock_delay):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-timeline'), {
            'parent_photo_scan_id': str(scan.id),
            'timeline': '1y',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        images = response.data['data']
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['timeline'], '1y')

    def test_timeline_rejects_invalid_type(self):
        scan = _create_approved_scan(self.user)
        response = self.client.post(reverse('generate-timeline'), {
            'parent_photo_scan_id': str(scan.id),
            'timeline': {'stage': '1y'},
        }, format='json')
        self.assertEqual(response.status_code, 400)


class ParentPhotoScanTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Test User', email='scan@example.com', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_upload_scan(self):
        data = {'father_photo': _create_test_image(), 'mother_photo': _create_test_image()}
        response = self.client.post(reverse('parent-photo-scan-upload'), data, format='multipart')
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data['data'])
        self.assertEqual(response.data['data']['overall_status'], 'approved')

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
