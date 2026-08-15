from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from decimal import Decimal

from accounts.models import CreditPlan, Payment, CreditTransaction

User = get_user_model()


class PaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            full_name='Test User', email='payment@example.com', password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.plan = CreditPlan.objects.create(
            name='Test Plan', price=Decimal('9.99'), credits=100, is_active=True
        )

    def test_list_credit_plans(self):
        response = self.client.get(reverse('credit-plan-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)

    def test_checkout_test_provider(self):
        response = self.client.post(reverse('checkout'), {
            'plan_id': str(self.plan.id),
            'provider': 'test',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('payment_id', response.data['data'])

    def test_confirm_payment(self):
        payment, _ = PaymentService(self.user).create_checkout(self.plan.id, provider='test')
        response = self.client.post(reverse('confirm-payment'), {
            'payment_id': str(payment.id),
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.credits_balance, 100)

    def test_get_balance(self):
        response = self.client.get(reverse('balance'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['credits_balance'], 0)

    def test_my_transactions(self):
        payment, _ = PaymentService(self.user).create_checkout(self.plan.id, provider='test')
        PaymentService(self.user).confirm_payment(payment.id)
        response = self.client.get(reverse('my-transactions'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['count'], 1)


class AdminPaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            full_name='Admin', email='adminpay@example.com', password='adminpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.plan = CreditPlan.objects.create(
            name='Admin Plan', price=Decimal('19.99'), credits=200, is_active=True
        )

    def test_admin_list_credit_plans(self):
        response = self.client.get(reverse('admin-credit-plan-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)

    def test_admin_create_credit_plan(self):
        response = self.client.post(reverse('admin-credit-plan-list'), {
            'name': 'New Plan',
            'price': '5.00',
            'credits': 50,
            'is_active': True,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CreditPlan.objects.count(), 2)

    def test_admin_list_transactions(self):
        response = self.client.get(reverse('admin-transaction-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)


class PaymentService:
    def __init__(self, user):
        self.user = user

    def create_checkout(self, plan_id, provider='test'):
        from accounts.services import PaymentService as RealPaymentService
        return RealPaymentService(user=self.user).create_checkout(plan_id, provider)

    def confirm_payment(self, payment_id):
        from accounts.services import PaymentService as RealPaymentService
        return RealPaymentService(user=self.user).confirm_payment(payment_id)
