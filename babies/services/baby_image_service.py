from ..models import BabyImage, GenerationTemplate
from ..prompt_builder import build_context_snapshot
from ..tasks import process_baby_generation


def _dispatch_generation(baby_image_id):
    """Dispatch the generation task, failing fast to a synchronous run when the
    broker (Redis) is unavailable — e.g. local dev without a worker."""
    try:
        process_baby_generation.delay(baby_image_id)
    except Exception:
        process_baby_generation(baby_image_id)


class ProPlanRequiredError(Exception):
    """Raised when the user attempts an age stage that requires a pro plan."""


def _age_months(age_stage):
    """Parse a free-text age stage into months (newborn=0)."""
    stage = (age_stage or '').strip().lower()
    if not stage or stage == 'newborn':
        return 0
    if stage.endswith('m'):
        try:
            return int(stage[:-1])
        except ValueError:
            return 0
    if stage.endswith('y'):
        try:
            return int(stage[:-1]) * 12
        except ValueError:
            return 0
    return 0


PRO_AGE_THRESHOLD_MONTHS = 12  # 1y and older requires a pro plan


def ensure_age_access(user, age_stage):
    """Free ages: newborn/3m/6m. 1y and beyond (2y, 5y, ...) require is_pro."""
    if _age_months(age_stage) >= PRO_AGE_THRESHOLD_MONTHS and not getattr(user, 'is_pro', False):
        raise ProPlanRequiredError('This age stage requires a pro plan.')


class BabyImageService:
    def __init__(self, user):
        self.user = user

    def create_generation(self, parent_photo_scan_id, template_id, **extra_fields):
        from ..services.parent_photo_scan_service import ParentPhotoScanService
        scan_service = ParentPhotoScanService(user=self.user)
        scan = scan_service.get_clean_scan(parent_photo_scan_id)

        template = None
        if template_id:
            template = GenerationTemplate.objects.get(id=template_id, status='active')

        generation_type = extra_fields.pop('generation_type', 'initial')
        age_stage = extra_fields.get('age_stage') or extra_fields.get('timeline')
        ensure_age_access(self.user, age_stage)
        baby_image = BabyImage.objects.create(
            user=self.user,
            generation_type=generation_type,
            father_photo=scan.father_photo,
            mother_photo=scan.mother_photo,
            parent_photo_scan=scan,
            generation_template=template,
            **extra_fields,
        )
        baby_image.request_context = build_context_snapshot(baby_image)
        baby_image.save(update_fields=['request_context'])
        _dispatch_generation(str(baby_image.id))
        baby_image.refresh_from_db()
        return baby_image

    def get_status(self, baby_image_id):
        return BabyImage.objects.get(id=baby_image_id, user=self.user, is_deleted=False)

    def list_for_user(self, filter_type=None):
        qs = BabyImage.objects.filter(user=self.user, is_deleted=False)
        if filter_type == 'favorite':
            qs = qs.filter(is_favorite=True)
        return qs

    def get_root_photos(self, baby_image):
        node = baby_image
        while node.parent_image is not None:
            node = node.parent_image
        return node.father_photo, node.mother_photo

    def create_derivative(self, parent_id, generation_type, **extra_fields):
        parent = BabyImage.objects.get(id=parent_id, user=self.user, is_deleted=False)
        father_photo, mother_photo = self.get_root_photos(parent)
        age_stage = extra_fields.get('age_stage', parent.age_stage)
        ensure_age_access(self.user, age_stage)
        baby_image = BabyImage.objects.create(
            user=self.user,
            parent_image=parent,
            generation_type=generation_type,
            father_photo=father_photo,
            mother_photo=mother_photo,
            gender=extra_fields.pop('gender', parent.gender),
            age_stage=extra_fields.pop('age_stage', parent.age_stage),
            background=extra_fields.pop('background', parent.background),
            outfit=extra_fields.pop('outfit', parent.outfit),
            timeline=extra_fields.pop('timeline', parent.timeline),
            generation_template=parent.generation_template,
            **extra_fields,
        )
        baby_image.request_context = build_context_snapshot(baby_image)
        baby_image.save(update_fields=['request_context'])
        _dispatch_generation(str(baby_image.id))
        baby_image.refresh_from_db()
        return baby_image

    def toggle_favorite(self, baby_image_id):
        baby_image = BabyImage.objects.get(id=baby_image_id, user=self.user, is_deleted=False)
        baby_image.is_favorite = not baby_image.is_favorite
        baby_image.save(update_fields=['is_favorite'])
        return baby_image
