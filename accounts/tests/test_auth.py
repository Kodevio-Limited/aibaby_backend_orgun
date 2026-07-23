from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('register')
        self.signin_url = reverse('sign-in')

    def test_register_success(self):
        data = {
            'full_name': 'Test User',
            'email': 'test@example.com',
            'password': 'testpass123',
            'confirm_password': 'testpass123',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['code'], 'REGISTERED')
        self.assertIn('message', response.data)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertEqual(user.email, 'test@example.com')
        self.assertFalse(user.is_verified)

    def test_register_password_mismatch(self):
        data = {
            'full_name': 'Test User',
            'email': 'test@example.com',
            'password': 'testpass123',
            'confirm_password': 'differentpass',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.data)
        self.assertIn('code', response.data)

    def test_register_duplicate_email(self):
        User.objects.create_user(full_name='Existing', email='test@example.com', password='pass123')
        data = {
            'full_name': 'Test User',
            'email': 'test@example.com',
            'password': 'testpass123',
            'confirm_password': 'testpass123',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.data)
        self.assertIn('code', response.data)
        self.assertEqual(response.data['detail'], 'Email already registered.')

    def test_sign_in_success(self):
        User.objects.create_user(full_name='Test', email='test@example.com', password='testpass123')
        data = {'email': 'test@example.com', 'password': 'testpass123'}
        response = self.client.post(self.signin_url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 'SIGNED_IN')
        self.assertIn('access', response.data['data'])
        self.assertIn('refresh', response.data['data'])
        self.assertIn('user', response.data['data'])

    def test_sign_in_invalid_credentials(self):
        User.objects.create_user(full_name='Test', email='test@example.com', password='testpass123')
        data = {'email': 'test@example.com', 'password': 'wrongpass'}
        response = self.client.post(self.signin_url, data, format='json')
        self.assertEqual(response.status_code, 401)
        self.assertIn('detail', response.data)
        self.assertIn('code', response.data)
