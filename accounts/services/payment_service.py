import decimal
from django.conf import settings
from django.db import transaction
from ..models import CreditPlan, Payment, CreditTransaction, User


class PaymentService:
    def __init__(self, user):
        self.user = user

    def list_active_credit_plans(self):
        return CreditPlan.objects.filter(is_active=True)

    def get_credit_plan(self, plan_id):
        return CreditPlan.objects.get(id=plan_id, is_active=True)

    def _get_stripe_client(self):
        if not getattr(settings, 'STRIPE_SECRET_KEY', None):
            return None
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe

    def create_checkout(self, plan_id, provider='stripe'):
        plan = self.get_credit_plan(plan_id)

        with transaction.atomic():
            payment = Payment.objects.create(
                user=self.user,
                amount=plan.price,
                currency='USD',
                provider=provider,
                status='pending',
                metadata={'plan_id': str(plan.id), 'credits': plan.credits},
            )

        stripe = self._get_stripe_client() if provider == 'stripe' else None
        if stripe:
            intent = stripe.PaymentIntent.create(
                amount=int(plan.price * 100),  # cents
                currency='usd',
                metadata={'payment_id': str(payment.id), 'plan_id': str(plan.id)},
                automatic_payment_methods={'enabled': True},
            )
            payment.provider_payment_id = intent.id
            payment.provider_client_secret = intent.client_secret
            payment.save(update_fields=['provider_payment_id', 'provider_client_secret'])
            return payment, {'client_secret': intent.client_secret}

        # Test/manual provider: return a reference the frontend can "confirm".
        return payment, {'payment_id': str(payment.id)}

    def confirm_payment(self, payment_id):
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment_id, user=self.user)
            if payment.status == 'succeeded':
                return payment
            if payment.status in ('failed', 'refunded'):
                raise ValueError('Payment cannot be confirmed.')

            plan_id = payment.metadata.get('plan_id')
            plan = CreditPlan.objects.get(id=plan_id) if plan_id else None
            credits = plan.credits if plan else 0

            payment.status = 'succeeded'
            payment.save(update_fields=['status', 'updated_at'])

            if credits > 0:
                self.user.add_credits(
                    credits,
                    transaction_type='purchase',
                    description=f'Credit purchase — {plan.name if plan else "manual"}',
                    payment=payment,
                )

        return payment

    def list_my_transactions(self):
        return CreditTransaction.objects.filter(user=self.user)

    def get_balance(self):
        return self.user.credits_balance


class AdminPaymentService:
    def list_credit_plans(self, search=None, status=None):
        qs = CreditPlan.objects.all()
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_credit_plan(self, plan_id):
        return CreditPlan.objects.get(id=plan_id)

    def create_credit_plan(self, **data):
        return CreditPlan.objects.create(**data)

    def update_credit_plan(self, plan_id, **data):
        plan = self.get_credit_plan(plan_id)
        for key, value in data.items():
            setattr(plan, key, value)
        plan.save()
        return plan

    def delete_credit_plan(self, plan_id):
        plan = self.get_credit_plan(plan_id)
        plan.delete()

    def list_transactions(self, search=None, type=None):
        qs = CreditTransaction.objects.all().select_related('user', 'payment')
        if type:
            qs = qs.filter(type=type)
        if search:
            qs = qs.filter(user__email__icontains=search) | qs.filter(description__icontains=search)
        return qs

    def get_transaction(self, transaction_id):
        return CreditTransaction.objects.select_related('user', 'payment').get(id=transaction_id)
