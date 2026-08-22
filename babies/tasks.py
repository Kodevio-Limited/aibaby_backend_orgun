from celery import shared_task
import uuid
from .models import BabyImage
from .prompt_builder import build_context_boost
from .services.generation_service import GenerationService, REPLICATE_BABY_PROVIDER
from .services.similarity_service import SimilarityService
from .services.scan_service import ScanService
from .services.parent_photo_scan_service import ParentPhotoScanService
from .services.image_processing_service import ImageProcessingService


def _download_and_save(image_url):
    import requests
    from django.core.files.base import ContentFile
    import uuid

    response = requests.get(image_url, timeout=60)
    response.raise_for_status()
    ext = image_url.rsplit('.', 1)[-1].split('?')[0] if '.' in image_url else 'png'
    filename = f'{uuid.uuid4()}.{ext}'
    return ContentFile(response.content, name=filename)


@shared_task
def process_parent_photo_scan(scan_id):
    from .models import ParentPhotoScan
    try:
        scan = ParentPhotoScan.objects.get(id=scan_id)
        ScanService().run_scan(scan)
    except ParentPhotoScan.DoesNotExist:
        pass


def _run_outfit_edit(baby_image):
    """Render an outfit change as a local edit of the SAME parent image.

    The user's exact colour is applied to the garment pixels while the face is
    left untouched, so the baby is pixel-identical and only the outfit changes.
    """
    from django.core.files.base import ContentFile
    from .services.outfit_edit_service import OutfitEditService
    from .prompt_builder import build_outfit_prompt

    # Copy the exact parent image; edit the COPY so the original stays intact.
    with open(baby_image.parent_image.generated_image.path, 'rb') as f:
        content = f.read()
    baby_image.generated_image.save(
        f'{uuid.uuid4()}.png', ContentFile(content), save=False
    )
    edited = OutfitEditService().edit_outfit(
        baby_image.generated_image.path, baby_image.outfit
    )
    if not edited:
        raise Exception(
            'Could not apply the outfit colour. Please use a known colour '
            'name (e.g. red, blue, green, black, white).'
        )

    baby_image.generation_prompt_text = build_outfit_prompt(baby_image.outfit)
    baby_image.ai_provider = 'local:outfit-recolor'
    baby_image.generation_status = 'done'
    baby_image.save()


def _parent_face_url(baby_image, field_name, base_url):
    """Return an absolute URL for a bare-face crop of a parent photo.

    The provider blends reference images, so we hand it ONLY the face (much
    stronger father/mother resemblance) and fall back to the original photo if
    no face can be detected.
    """
    from django.conf import settings
    field = getattr(baby_image, field_name)
    if not field or not field.name:
        return None
    name = ImageProcessingService().create_face_crop(field.path)
    if name:
        media = getattr(settings, 'MEDIA_URL', None) or '/media/'
        return f"{base_url}/{media.strip('/')}/{name}"
    return f"{base_url}{field.url}"


def _run_normal_generation(baby_image):
    from django.conf import settings

    base_url = getattr(settings, 'BASE_URL', '').rstrip('/')
    father_url = _parent_face_url(baby_image, 'father_photo', base_url)
    mother_url = _parent_face_url(baby_image, 'mother_photo', base_url)

    gen_service = GenerationService()
    prediction = gen_service.generate_baby(
        baby_image=baby_image,
        father_photo_url=father_url,
        mother_photo_url=mother_url,
        gender=baby_image.gender,
        prompt_extra=build_context_boost(baby_image),
    )
    baby_image.external_job_id = prediction.id
    baby_image.ai_provider = REPLICATE_BABY_PROVIDER
    baby_image.save(update_fields=['external_job_id', 'ai_provider'])

    result = gen_service.wait_for_prediction(prediction)
    if result.status != 'succeeded':
        raise Exception(f"Generation failed: {result.error}")

    image_url = result.output[0] if isinstance(result.output, list) else result.output
    baby_image.generated_image = _download_and_save(image_url)
    baby_image.save(update_fields=['generated_image'])

    # Guarantee a single face-first portrait: crop out hands/legs/background.
    ImageProcessingService().crop_and_save(baby_image.generated_image.path)

    # Composite template background if one is set
    template = baby_image.generation_template
    if template and template.background:
        try:
            from PIL import Image, ImageFilter, ImageDraw
            bg = Image.open(template.background.path).convert('RGB')
            bg = bg.resize((768, 1024), Image.LANCZOS)
            baby = Image.open(baby_image.generated_image.path).convert('RGBA')
            # Scale baby to 90% and center on background
            bw, bh = baby.size
            scale = 0.9
            nw, nh = int(bw * scale), int(bh * scale)
            baby = baby.resize((nw, nh), Image.LANCZOS)
            paste_x = (768 - nw) // 2
            paste_y = (1024 - nh) // 2
            # Soft vignette mask for the baby edges
            mask = Image.new('L', (nw, nh), 255)
            draw = ImageDraw.Draw(mask)
            margin = 40
            draw.rounded_rectangle(
                [(margin, margin), (nw - margin, nh - margin)],
                radius=60, fill=255
            )
            mask = mask.filter(ImageFilter.GaussianBlur(radius=25))
            bg.paste(baby, (paste_x, paste_y), mask)
            bg.save(baby_image.generated_image.path, quality=95)
        except Exception:
            pass  # compositing failure should not fail the generation

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


@shared_task
def process_baby_generation(baby_image_id):
    baby_image = BabyImage.objects.get(id=baby_image_id)
    baby_image.generation_status = 'processing'
    baby_image.save(update_fields=['generation_status'])

    is_outfit_edit = (
        baby_image.generation_type == 'outfit_change'
        and baby_image.parent_image is not None
        and bool(baby_image.parent_image.generated_image)
    )

    try:
        if is_outfit_edit:
            _run_outfit_edit(baby_image)
        else:
            _run_normal_generation(baby_image)
    except Exception as e:
        from django.conf import settings as _settings
        base_url = getattr(_settings, 'BASE_URL', '')
        hint = ''
        if any(h in base_url for h in ('localhost', '127.0.0.1', '0.0.0.0', '192.168.', '10.')):
            hint = (
                " [Hint: BASE_URL is not publicly reachable by Replicate. "
                "Set BASE_URL to a public origin (or a tunnel) so the provider can download the parent photos.]"
            )
        baby_image.generation_status = 'failed'
        baby_image.error_message = f"{e}{hint}"
        baby_image.save(update_fields=['generation_status', 'error_message'])
