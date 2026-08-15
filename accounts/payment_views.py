from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.conf import settings

from core.pagination import StandardPagination
from .models import CreditPlan, Payment, CreditTransaction
from .services import PaymentService, AdminPaymentService
from .serializers import (
    CreditPlanOutputSerializer, CheckoutSerializer, CheckoutOutputSerializer,
    ConfirmPaymentSerializer, PaymentOutputSerializer, CreditTransactionOutputSerializer,
)


class CreditPlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        service = PaymentService(user=request.user)
        plans = service.list_active_credit_plans()
        serializer = CreditPlanOutputSerializer(plans, many=True, context={'request': request})
        return Response({'data': serializer.data})


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = PaymentService(user=request.user)
            payment, provider_data = service.create_checkout(
                plan_id=serializer.validated_data['plan_id'],
                provider=serializer.validated_data.get('provider', 'stripe'),
            )
        except CreditPlan.DoesNotExist:
            raise NotFound('Plan not found.')
        except Exception as e:
            return Response(
                {'detail': 'Could not start checkout', 'code': 'CHECKOUT_FAILED'},
                status=502,
            )

        return Response({
            'data': {
                'payment_id': payment.id,
                'client_secret': provider_data.get('client_secret', ''),
                'provider': payment.provider,
                'amount': payment.amount,
                'currency': payment.currency,
            }
        }, status=201)


class ConfirmPaymentView(APIView):
    """Test/manual confirmation. Production flows usually confirm via webhooks."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConfirmPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = PaymentService(user=request.user)
            payment = service.confirm_payment(serializer.validated_data['payment_id'])
        except Payment.DoesNotExist:
            raise NotFound('Payment not found.')
        except ValueError as e:
            return Response({'detail': str(e), 'code': 'PAYMENT_CONFIRM_FAILED'}, status=400)
        except Exception as e:
            return Response(
                {'detail': 'Could not confirm payment', 'code': 'PAYMENT_CONFIRM_FAILED'},
                status=502,
            )

        return Response({'data': PaymentOutputSerializer(payment, context={'request': request}).data})


class MyTransactionsView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request):
        service = PaymentService(user=request.user)
        qs = service.list_my_transactions()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = CreditTransactionOutputSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class BalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        service = PaymentService(user=request.user)
        return Response({'data': {'credits_balance': service.get_balance()}})


class PaymentWebhookView(APIView):
    """Generic webhook. Supports Stripe when STRIPE_SECRET_KEY/STRIPE_WEBHOOK_SECRET are set."""

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        provider = request.query_params.get('provider', 'stripe')

        if provider == 'stripe':
            return self._handle_stripe_webhook(request)

        return Response({'detail': 'Unsupported provider.', 'code': 'UNSUPPORTED_PROVIDER'}, status=400)

    def _handle_stripe_webhook(self, request):
        import stripe
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

        payload = request.body
        sig_header = request.headers.get('Stripe-Signature', '')

        try:
            if endpoint_secret:
                event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
            else:
                event = stripe.Event.construct_from(
                    request.data if hasattr(request, 'data') else {}, stripe.api_key
                )
        except ValueError:
            return Response(status=400)
        except stripe.error.SignatureVerificationError:
            return Response(status=400)

        if event['type'] == 'payment_intent.succeeded':
            intent = event['data']['object']
            payment_id = intent.get('metadata', {}).get('payment_id')
            if payment_id:
                try:
                    payment = Payment.objects.get(id=payment_id)
                    service = PaymentService(user=payment.user)
                    service.confirm_payment(payment.id)
                except Payment.DoesNotExist:
                    pass

        return Response({'data': {'received': True}})
