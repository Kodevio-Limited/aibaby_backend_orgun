from django.urls import path
from .admin_payment_views import (
    AdminCreditPlanListView, AdminCreditPlanDetailView,
    AdminTransactionListView, AdminTransactionDetailView,
)

urlpatterns = [
    path('credit-plans/', AdminCreditPlanListView.as_view(), name='admin-credit-plan-list'),
    path('credit-plans/<uuid:pk>/', AdminCreditPlanDetailView.as_view(), name='admin-credit-plan-detail'),
    path('transactions/', AdminTransactionListView.as_view(), name='admin-transaction-list'),
    path('transactions/<uuid:pk>/', AdminTransactionDetailView.as_view(), name='admin-transaction-detail'),
]
