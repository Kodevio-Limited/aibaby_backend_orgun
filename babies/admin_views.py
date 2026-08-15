from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404

from core.pagination import StandardPagination
from .models import GenerationPrompt, GenerationTemplate, ParentPhotoScan, SafetySettings
from .serializers import (
    GenerationPromptOutputSerializer, GenerationPromptInputSerializer,
    GenerationTemplateOutputSerializer, GenerationTemplateInputSerializer,
    ParentPhotoScanAdminOutputSerializer, SafetySettingsSerializer,
)
from .services.parent_photo_scan_service import ParentPhotoScanService


class AdminGenerationPromptListView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = StandardPagination

    def get(self, request):
        qs = GenerationPrompt.objects.all()
        search = request.query_params.get('search')
        category = request.query_params.get('category')
        if search:
            qs = qs.filter(title__icontains=search) | qs.filter(content__icontains=search)
        if category:
            qs = qs.filter(category=category)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = GenerationPromptOutputSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = GenerationPromptInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prompt = serializer.save()
        return Response(
            {'data': GenerationPromptOutputSerializer(prompt, context={'request': request}).data},
            status=201,
        )


class AdminGenerationPromptDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        prompt = get_object_or_404(GenerationPrompt, id=pk)
        return Response({'data': GenerationPromptOutputSerializer(prompt, context={'request': request}).data})

    def patch(self, request, pk):
        prompt = get_object_or_404(GenerationPrompt, id=pk)
        serializer = GenerationPromptInputSerializer(prompt, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        prompt = serializer.save()
        return Response({'data': GenerationPromptOutputSerializer(prompt, context={'request': request}).data})

    def delete(self, request, pk):
        prompt = get_object_or_404(GenerationPrompt, id=pk)
        prompt.delete()
        return Response(status=204)


class AdminGenerationPromptDuplicateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        prompt = get_object_or_404(GenerationPrompt, id=pk)
        prompt.pk = None
        prompt.title = f'{prompt.title} (Copy)'
        prompt.status = 'draft'
        prompt.save()
        return Response(
            {'data': GenerationPromptOutputSerializer(prompt, context={'request': request}).data},
            status=201,
        )


class AdminGenerationTemplateListView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = StandardPagination

    def get(self, request):
        qs = GenerationTemplate.objects.all()
        search = request.query_params.get('search')
        category = request.query_params.get('category')
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(description__icontains=search)
        if category:
            qs = qs.filter(category=category)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = GenerationTemplateOutputSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = GenerationTemplateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(
            {'data': GenerationTemplateOutputSerializer(template, context={'request': request}).data},
            status=201,
        )


class AdminGenerationTemplateDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        template = get_object_or_404(GenerationTemplate, id=pk)
        return Response({'data': GenerationTemplateOutputSerializer(template, context={'request': request}).data})

    def patch(self, request, pk):
        template = get_object_or_404(GenerationTemplate, id=pk)
        serializer = GenerationTemplateInputSerializer(template, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response({'data': GenerationTemplateOutputSerializer(template, context={'request': request}).data})

    def delete(self, request, pk):
        template = get_object_or_404(GenerationTemplate, id=pk)
        template.delete()
        return Response(status=204)


class AdminGenerationTemplateDuplicateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        template = get_object_or_404(GenerationTemplate, id=pk)
        template.pk = None
        template.name = f'{template.name} (Copy)'
        template.status = 'draft'
        template.save()
        return Response(
            {'data': GenerationTemplateOutputSerializer(template, context={'request': request}).data},
            status=201,
        )


class AdminParentPhotoScanListView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = StandardPagination

    def get(self, request):
        service = ParentPhotoScanService(user=request.user)
        qs = service.admin_list(
            search=request.query_params.get('search'),
            status=request.query_params.get('status'),
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ParentPhotoScanAdminOutputSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminParentPhotoScanDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        service = ParentPhotoScanService(user=request.user)
        try:
            scan = service.admin_get(pk)
        except ParentPhotoScan.DoesNotExist:
            raise NotFound('Scan not found.')
        return Response({'data': ParentPhotoScanAdminOutputSerializer(scan, context={'request': request}).data})

    def patch(self, request, pk):
        service = ParentPhotoScanService(user=request.user)
        scan = service.admin_update(
            pk,
            status=request.data.get('status'),
            moderator_notes=request.data.get('moderator_notes'),
        )
        return Response({'data': ParentPhotoScanAdminOutputSerializer(scan, context={'request': request}).data})

    def delete(self, request, pk):
        service = ParentPhotoScanService(user=request.user)
        try:
            service.admin_delete(pk)
        except ParentPhotoScan.DoesNotExist:
            raise NotFound('Scan not found.')
        return Response(status=204)


class AdminParentPhotoScanResetView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        service = ParentPhotoScanService(user=request.user)
        try:
            scan = service.reset_scan(pk)
        except ParentPhotoScan.DoesNotExist:
            raise NotFound('Scan not found.')
        return Response({'data': ParentPhotoScanAdminOutputSerializer(scan, context={'request': request}).data})


class AdminParentPhotoScanRescanView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        service = ParentPhotoScanService(user=request.user)
        try:
            scan = service.rescan(pk)
        except ParentPhotoScan.DoesNotExist:
            raise NotFound('Scan not found.')
        return Response({'data': ParentPhotoScanAdminOutputSerializer(scan, context={'request': request}).data})


class AdminModerationStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total = ParentPhotoScan.objects.count()
        approved = ParentPhotoScan.objects.filter(overall_status='approved').count()
        rejected = ParentPhotoScan.objects.filter(overall_status='rejected').count()
        flagged = ParentPhotoScan.objects.filter(overall_status='flagged').count()
        pending = ParentPhotoScan.objects.filter(overall_status__in=['pending', 'scanning']).count()
        return Response({
            'data': {
                'scanned_today': total,
                'approved': approved,
                'rejected': rejected,
                'flagged': flagged,
                'pending': pending,
            }
        })


class AdminSafetySettingsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        settings = SafetySettings.load()
        return Response({'data': SafetySettingsSerializer(settings).data})

    def put(self, request):
        settings = SafetySettings.load()
        serializer = SafetySettingsSerializer(settings, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'data': serializer.data})
