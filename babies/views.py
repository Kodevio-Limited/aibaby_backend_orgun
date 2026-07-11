from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from .serializers import (
    BabyImageGenerateSerializer, BabyImageGenerateWithOptionsSerializer,
    ChangeAgeSerializer, ChangeOutfitSerializer, GenerateTimelineSerializer,
    BabyImageOutputSerializer, BabyImageListSerializer,
)
from .models import BabyImage
from .services.baby_image_service import BabyImageService
from core.pagination import StandardPagination


class GenerateBabyView(APIView):
    def post(self, request):
        serializer = BabyImageGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = BabyImageService(user=request.user)
            baby_image = service.create_generation(
                generation_type='initial',
                **serializer.validated_data,
            )
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
            baby_image = service.create_generation(
                generation_type='age_stage',
                **serializer.validated_data,
            )
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
            baby_image = service.create_generation(
                generation_type='timeline',
                timeline=serializer.validated_data['timeline'],
                father_photo=serializer.validated_data['father_photo'],
                mother_photo=serializer.validated_data['mother_photo'],
            )
        except Exception as e:
            return Response(
                {'detail': 'Could not start timeline generation', 'code': 'TIMELINE_START_FAILED'},
                status=502,
            )

        return Response(
            {'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data},
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
        return paginator.get_paginated_response({'data': serializer.data})


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
