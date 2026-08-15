from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404

from core.pagination import StandardPagination
from .models import CreditPlan, CreditTransaction
from .services import AdminPaymentService
from .serializers import CreditPlanOutputSerializer, CreditPlanInputSerializer, CreditTransactionAdminOutputSerializer


class AdminCreditPlanListView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = StandardPagination

    def get(self, request):
        service = AdminPaymentService()
        qs = service.list_credit_plans(
            search=request.query_params.get('search'),
            status=request.query_params.get('status'),
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = CreditPlanOutputSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CreditPlanInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = AdminPaymentService()
        plan = service.create_credit_plan(**serializer.validated_data)
        return Response(
            {'data': CreditPlanOutputSerializer(plan, context={'request': request}).data},
            status=201,
        )


class AdminCreditPlanDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        plan = get_object_or_404(CreditPlan, id=pk)
        return Response({'data': CreditPlanOutputSerializer(plan, context={'request': request}).data})

    def patch(self, request, pk):
        plan = get_object_or_404(CreditPlan, id=pk)
        serializer = CreditPlanInputSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        service = AdminPaymentService()
        plan = service.update_credit_plan(pk, **serializer.validated_data)
        return Response({'data': CreditPlanOutputSerializer(plan, context={'request': request}).data})

    def delete(self, request, pk):
        plan = get_object_or_404(CreditPlan, id=pk)
        service = AdminPaymentService()
        service.delete_credit_plan(pk)
        return Response(status=204)


class AdminTransactionListView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = StandardPagination

    def get(self, request):
        service = AdminPaymentService()
        qs = service.list_transactions(
            search=request.query_params.get('search'),
            type=request.query_params.get('type'),
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = CreditTransactionAdminOutputSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminTransactionDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        service = AdminPaymentService()
        try:
            transaction = service.get_transaction(pk)
        except CreditTransaction.DoesNotExist:
            raise NotFound('Transaction not found.')
        return Response({'data': CreditTransactionAdminOutputSerializer(transaction, context={'request': request}).data})
