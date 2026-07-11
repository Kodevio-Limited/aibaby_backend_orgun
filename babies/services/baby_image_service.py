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

    def get_root_photos(self, baby_image):
        node = baby_image
        while node.parent_image is not None:
            node = node.parent_image
        return node.father_photo, node.mother_photo

    def create_derivative(self, parent_id, generation_type, **extra_fields):
        parent = BabyImage.objects.get(id=parent_id, user=self.user, is_deleted=False)
        father_photo, mother_photo = self.get_root_photos(parent)
        baby_image = BabyImage.objects.create(
            user=self.user,
            parent_image=parent,
            generation_type=generation_type,
            father_photo=father_photo,
            mother_photo=mother_photo,
            gender=parent.gender,
            age_stage=parent.age_stage,
            background=parent.background,
            **extra_fields,
        )
        process_baby_generation.delay(str(baby_image.id))
        return baby_image

    def toggle_favorite(self, baby_image_id):
        baby_image = BabyImage.objects.get(id=baby_image_id, user=self.user, is_deleted=False)
        baby_image.is_favorite = not baby_image.is_favorite
        baby_image.save(update_fields=['is_favorite'])
        return baby_image
