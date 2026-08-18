from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError
from .serializers import (
    BabyImageGenerateSerializer, BabyImageGenerateWithOptionsSerializer,
    ChangeAgeSerializer, ChangeOutfitSerializer, GenerateTimelineSerializer,
    BabyImageOutputSerializer, BabyImageListSerializer,
    ParentPhotoScanUploadSerializer, ParentPhotoScanOutputSerializer,
)
from .models import BabyImage
from .services.baby_image_service import BabyImageService, ProPlanRequiredError
from .services.parent_photo_scan_service import ParentPhotoScanService
from core.pagination import StandardPagination


class ParentPhotoScanUploadView(APIView):
    def post(self, request):
        serializer = ParentPhotoScanUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = ParentPhotoScanService(user=request.user)
            scan = service.create_scan(
                father_photo=serializer.validated_data['father_photo'],
                mother_photo=serializer.validated_data['mother_photo'],
            )
        except Exception as e:
            return Response(
                {'detail': 'Could not start photo scan', 'code': 'SCAN_START_FAILED'},
                status=502,
            )

        return Response(
            {'data': ParentPhotoScanOutputSerializer(scan, context={'request': request}).data},
            status=201,
        )


class ParentPhotoScanStatusView(APIView):
    def get(self, request, pk):
        try:
            service = ParentPhotoScanService(user=request.user)
            scan = service.get_scan(pk)
        except ParentPhotoScan.DoesNotExist:
            raise NotFound('Scan not found.')

        return Response({'data': ParentPhotoScanOutputSerializer(scan, context={'request': request}).data})


class GenerateBabyView(APIView):
    def post(self, request):
        serializer = BabyImageGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = BabyImageService(user=request.user)
            baby_image = service.create_generation(
                generation_type='initial',
                parent_photo_scan_id=serializer.validated_data['parent_photo_scan_id'],
                template_id=serializer.validated_data.get('template_id'),
            )
        except ValueError as e:
            return Response(
                {'detail': str(e), 'code': 'PHOTOS_NOT_APPROVED'},
                status=400,
            )
        except ProPlanRequiredError as e:
            return Response({'detail': str(e), 'code': 'PRO_PLAN_REQUIRED'}, status=403)
        except Exception as e:
            return Response(
                {'detail': 'Could not start generation', 'code': 'GENERATION_START_FAILED'},
                status=502,
            )

        return Response(
            {'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data},
            status=201,
        )


class GenerateBabyWithOptionsView(APIView):
    def post(self, request):
        serializer = BabyImageGenerateWithOptionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = BabyImageService(user=request.user)
            data = serializer.validated_data
            baby_image = service.create_generation(
                generation_type='age_stage',
                parent_photo_scan_id=data['parent_photo_scan_id'],
                template_id=data.get('template_id'),
                gender=data['gender'],
                age_stage=data['age_stage'],
                background=data['background'],
                outfit=data.get('outfit', ''),
            )
        except ValueError as e:
            return Response(
                {'detail': str(e), 'code': 'PHOTOS_NOT_APPROVED'},
                status=400,
            )
        except ProPlanRequiredError as e:
            return Response({'detail': str(e), 'code': 'PRO_PLAN_REQUIRED'}, status=403)
        except Exception as e:
            return Response(
                {'detail': 'Could not start generation', 'code': 'GENERATION_START_FAILED'},
                status=502,
            )

        return Response(
            {'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data},
            status=201,
        )


class ChangeAgeView(APIView):
    def post(self, request, pk):
        serializer = ChangeAgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = BabyImageService(user=request.user)
            baby_image = service.create_derivative(
                parent_id=pk,
                generation_type='age_change',
                age_stage=serializer.validated_data['age_stage'],
            )
        except BabyImage.DoesNotExist:
            raise NotFound('Baby image not found.')
        except ProPlanRequiredError as e:
            return Response({'detail': str(e), 'code': 'PRO_PLAN_REQUIRED'}, status=403)
        except Exception as e:
            return Response(
                {'detail': 'Could not change age', 'code': 'AGE_CHANGE_FAILED'},
                status=502,
            )

        return Response(
            {'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data},
            status=201,
        )


class ChangeOutfitView(APIView):
    def post(self, request, pk):
        serializer = ChangeOutfitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = BabyImageService(user=request.user)
            baby_image = service.create_derivative(
                parent_id=pk,
                generation_type='outfit_change',
                outfit=serializer.validated_data['outfit'],
            )
        except BabyImage.DoesNotExist:
            raise NotFound('Baby image not found.')
        except Exception as e:
            return Response(
                {'detail': 'Could not change outfit', 'code': 'OUTFIT_CHANGE_FAILED'},
                status=502,
            )

        return Response(
            {'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data},
            status=201,
        )


class GenerateHighResView(APIView):
    def post(self, request, pk):
        try:
            service = BabyImageService(user=request.user)
            baby_image = service.create_derivative(
                parent_id=pk,
                generation_type='high_res',
            )
        except BabyImage.DoesNotExist:
            raise NotFound('Baby image not found.')
        except Exception as e:
            return Response(
                {'detail': 'Could not generate high-res', 'code': 'HIGH_RES_FAILED'},
                status=502,
            )

        return Response(
            {'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data},
            status=201,
        )


class GenerateTimelineView(APIView):
    def post(self, request):
        serializer = GenerateTimelineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = BabyImageService(user=request.user)
            data = serializer.validated_data
            baby_images = []
            for stage in data['timeline']:
                baby_image = service.create_generation(
                    generation_type='timeline',
                    parent_photo_scan_id=data['parent_photo_scan_id'],
                    template_id=data.get('template_id'),
                    timeline=stage,
                    age_stage=stage,
                )
                baby_images.append(baby_image)
        except ValueError as e:
            return Response(
                {'detail': str(e), 'code': 'PHOTOS_NOT_APPROVED'},
                status=400,
            )
        except ProPlanRequiredError as e:
            return Response({'detail': str(e), 'code': 'PRO_PLAN_REQUIRED'}, status=403)
        except Exception as e:
            return Response(
                {'detail': 'Could not start timeline generation', 'code': 'TIMELINE_START_FAILED'},
                status=502,
            )

        return Response(
            {'data': BabyImageOutputSerializer(baby_images, many=True, context={'request': request}).data},
            status=201,
        )


class BabyImageStatusView(APIView):
    def get(self, request, pk):
        try:
            service = BabyImageService(user=request.user)
            baby_image = service.get_status(pk)
        except BabyImage.DoesNotExist:
            raise NotFound('Generation not found.')

        return Response({'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data})


class BabyImageListView(APIView):
    pagination_class = StandardPagination

    def get(self, request):
        service = BabyImageService(user=request.user)
        qs = service.list_for_user(filter_type=request.query_params.get('filter'))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = BabyImageListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class ToggleFavoriteView(APIView):
    def post(self, request, pk):
        try:
            service = BabyImageService(user=request.user)
            baby_image = service.toggle_favorite(pk)
        except BabyImage.DoesNotExist:
            raise NotFound('Baby image not found.')

        return Response({
            'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data
        })


class ActiveTemplateListView(APIView):
    """Public-ish endpoint for users to pick an active generation template."""

    def get(self, request):
        from .models import GenerationTemplate
        from .serializers import GenerationTemplateListSerializer
        qs = GenerationTemplate.objects.filter(status='active')
        serializer = GenerationTemplateListSerializer(qs, many=True, context={'request': request})
        return Response({'data': serializer.data})
