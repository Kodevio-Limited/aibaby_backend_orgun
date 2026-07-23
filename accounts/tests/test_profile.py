from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Test User', email='test@example.com', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_get_profile(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 'PROFILE_LOADED')
        self.assertEqual(response.data['data']['email'], 'test@example.com')

    def test_update_profile(self):
        data = {'full_name': 'Updated Name'}
        response = self.client.patch(reverse('profile'), data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 'PROFILE_UPDATED')
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, 'Updated Name')

    def test_change_password_success(self):
        data = {
            'current_password': 'testpass123',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123',
        }
        response = self.client.post(reverse('change-password'), data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 'PASSWORD_CHANGED')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))

    def test_change_password_wrong_current(self):
        data = {
            'current_password': 'wrongpass',
            'new_password': 'newpass123',
            'confirm_password': 'newpass123',
        }
        response = self.client.post(reverse('change-password'), data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.data)
        self.assertIn('code', response.data)
