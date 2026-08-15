from celery import shared_task
from .models import BabyImage
from .services.generation_service import GenerationService, REPLICATE_BABY_PROVIDER
from .services.similarity_service import SimilarityService
from .services.scan_service import ScanService
from .services.parent_photo_scan_service import ParentPhotoScanService


def _download_and_save(image_url):
    import requests
    from django.core.files.base import ContentFile
    import uuid

    response = requests.get(image_url, timeout=60)
    response.raise_for_status()
    ext = image_url.rsplit('.', 1)[-1].split('?')[0] if '.' in image_url else 'png'
    filename = f'{uuid.uuid4()}.{ext}'
    return ContentFile(response.content, name=filename)


def _build_prompt_extra(baby_image):
    parts = []
    if baby_image.gender:
        parts.append({'boy': 'baby boy', 'girl': 'baby girl', 'twins': 'twin babies'}.get(baby_image.gender, ''))
    if baby_image.age_stage:
        stage_map = {'newborn': 'newborn baby', '3m': '3 month old baby', '6m': '6 month old baby', '1y': '1 year old baby'}
        parts.append(stage_map.get(baby_image.age_stage, ''))
    if baby_image.background:
        bg_map = {'studio': 'studio background', 'home': 'at home', 'nature': 'outdoors in nature'}
        parts.append(bg_map.get(baby_image.background, ''))
    if baby_image.outfit:
        parts.append(f'wearing {baby_image.outfit}')
    return ', '.join(filter(None, parts))


@shared_task
def process_parent_photo_scan(scan_id):
    from .models import ParentPhotoScan
    try:
        scan = ParentPhotoScan.objects.get(id=scan_id)
        ScanService().run_scan(scan)
    except ParentPhotoScan.DoesNotExist:
        pass


@shared_task
def process_baby_generation(baby_image_id):
    baby_image = BabyImage.objects.get(id=baby_image_id)
    baby_image.generation_status = 'processing'
    baby_image.save(update_fields=['generation_status'])

    try:
        from django.conf import settings
        base_url = getattr(settings, 'BASE_URL', '').rstrip('/')
        father_url = f"{base_url}{baby_image.father_photo.url}"
        mother_url = f"{base_url}{baby_image.mother_photo.url}"

        gen_service = GenerationService()
        prediction = gen_service.generate_baby(
            baby_image=baby_image,
            father_photo_url=father_url,
            mother_photo_url=mother_url,
            gender=baby_image.gender,
            prompt_extra=_build_prompt_extra(baby_image),
        )
        baby_image.external_job_id = prediction.id
        baby_image.ai_provider = REPLICATE_BABY_PROVIDER
        baby_image.save(update_fields=['external_job_id', 'ai_provider'])

        result = gen_service.wait_for_prediction(prediction)
        if result.status != 'succeeded':
            raise Exception(f"Generation failed: {result.error}")

        image_url = result.output[0] if isinstance(result.output, list) else result.output
        baby_image.generated_image = _download_and_save(image_url)

        similarity_service = SimilarityService()
        baby_image.eyes_similarity = similarity_service.compare_faces(
            baby_image.generated_image.path, baby_image.father_photo.path
        )
        baby_image.face_shape_similarity = similarity_service.compare_faces(
            baby_image.generated_image.path, baby_image.mother_photo.path
        )
        baby_image.skin_tone_similarity = similarity_service.compare_skin_tone(
            baby_image.generated_image.path, baby_image.father_photo.path
        )

        baby_image.generation_status = 'done'
        baby_image.save()

    except Exception as e:
        baby_image.generation_status = 'failed'
        baby_image.error_message = str(e)
        baby_image.save(update_fields=['generation_status', 'error_message'])
