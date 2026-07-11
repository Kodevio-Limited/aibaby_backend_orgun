# APIView & Service-Layer Patterns

**This replaces a `ViewSet`-based version of this doc.** Your stated
standard is to always use `APIView`, not `ModelViewSet` — this version
matches that. Use this pattern for every endpoint in this project
(including the ones outside the AI baby app).

## Standard rules

- Always use `APIView` classes, never `ModelViewSet`/`GenericViewSet`.
- Always use DRF serializers for input validation and output shaping.
- Always paginate list endpoints with the shared `StandardPagination`
  class (see `04-Settings-Structure.md`).
- Views call a **service class**, instantiated (not `@staticmethod`), that
  holds the actual business logic. Views stay thin: validate → call
  service → return response.
- Every service call from a view is wrapped in `try/except`, with errors
  surfaced through the standard error format.

## Standard serializer

```python
class BabyImageCreateSerializer(serializers.Serializer):
    father_photo = serializers.ImageField()
    mother_photo = serializers.ImageField()

    def validate_father_photo(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Image must be under 10MB')
        return value


class BabyImageOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = BabyImage
        fields = [
            'id', 'generation_status', 'generated_image',
            'eyes_similarity', 'face_shape_similarity', 'skin_tone_similarity',
            'error_message', 'created_at',
        ]
```

Use a separate serializer for list views vs detail views when detail has
heavier fields — same principle as before, just applied to APIView instead
of ViewSet.

## Service class (instantiated, not static)

```python
# babies/services/baby_image_service.py
from ..models import BabyImage
from ..tasks import process_baby_generation

class BabyImageService:
    def __init__(self, user):
        self.user = user

    def create_generation(self, father_photo, mother_photo, **extra_fields):
        baby_image = BabyImage.objects.create(
            user=self.user,
            generation_type=extra_fields.pop('generation_type', 'initial'),
            father_photo=father_photo,
            mother_photo=mother_photo,
            **extra_fields,
        )
        process_baby_generation.delay(str(baby_image.id))
        return baby_image

    def get_status(self, baby_image_id):
        return BabyImage.objects.get(id=baby_image_id, user=self.user, is_deleted=False)

    def list_for_user(self, filter_type=None):
        qs = BabyImage.objects.filter(user=self.user, is_deleted=False)
        if filter_type == 'favorite':
            qs = qs.filter(is_favorite=True)
        return qs
```

## APIView using the service, with try/except

```python
# babies/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from .serializers import BabyImageCreateSerializer, BabyImageOutputSerializer
from .services.baby_image_service import BabyImageService
from core.pagination import StandardPagination


class GenerateBabyView(APIView):
    def post(self, request):
        serializer = BabyImageCreateSerializer(data=request.data)
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


class BabyImageStatusView(APIView):
    def get(self, request, pk):
        try:
            service = BabyImageService(user=request.user)
            baby_image = service.get_status(pk)
        except BabyImage.DoesNotExist:
            raise NotFound('Generation not found')

        return Response({'data': BabyImageOutputSerializer(baby_image, context={'request': request}).data})


class BabyImageListView(APIView):
    pagination_class = StandardPagination

    def get(self, request):
        service = BabyImageService(user=request.user)
        qs = service.list_for_user(filter_type=request.query_params.get('filter'))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = BabyImageOutputSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response({'data': serializer.data})
```

## The N+1 Query Trap (still applies with APIView)

```python
# BAD — triggers a query per row
for baby_image in BabyImage.objects.filter(user=user):
    print(baby_image.user.email)

# GOOD
BabyImage.objects.filter(user=user).select_related('user')
```

Check this in every service method that returns a queryset touching a
related model.

## Permissions

```python
class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
```

Since every service method already filters by `user=self.user`, ownership
is enforced at the query level (a user literally cannot fetch another
user's `BabyImage` — it won't exist in their queryset). Object-level
permission classes are a second layer of defense, not the only one.

## Do Not

- Use `ModelViewSet`/`GenericViewSet` anywhere in this project — `APIView`
  only, per project standard.
- Put business logic directly in the view — it belongs in the service
  class.
- Make a service method `@staticmethod` — always instantiate with the
  relevant context (usually `user`) so it can't accidentally be called
  without scoping to the right user.
- Call a service method from a view without wrapping it in `try/except`.
- Return an unpaginated queryset from a list endpoint.
- Forget `select_related`/`prefetch_related` when a serializer touches
  related fields.
