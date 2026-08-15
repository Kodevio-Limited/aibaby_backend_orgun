from django.urls import path
from .views import (
    RegisterView, SignInView, ForgotPasswordView,
    VerifyOTPView, ResetPasswordView, LogoutView,
)
from .payment_views import (
    CreditPlanListView, CheckoutView, ConfirmPaymentView,
    MyTransactionsView, BalanceView, PaymentWebhookView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('sign-in/', SignInView.as_view(), name='sign-in'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('subscriptions/plans/', CreditPlanListView.as_view(), name='credit-plan-list'),
    path('subscriptions/checkout/', CheckoutView.as_view(), name='checkout'),
    path('subscriptions/confirm/', ConfirmPaymentView.as_view(), name='confirm-payment'),
    path('subscriptions/my-transactions/', MyTransactionsView.as_view(), name='my-transactions'),
    path('subscriptions/balance/', BalanceView.as_view(), name='balance'),
    path('subscriptions/webhook/', PaymentWebhookView.as_view(), name='payment-webhook'),
]
