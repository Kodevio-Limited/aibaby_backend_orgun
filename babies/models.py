import uuid
from django.db import models
from django.conf import settings


class BabyImage(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ]

    GENERATION_TYPES = [
        ('initial', 'Initial'),
        ('age_stage', 'Age Stage'),
        ('timeline', 'Timeline'),
        ('age_change', 'Age Change'),
        ('outfit_change', 'Outfit Change'),
        ('high_res', 'High Res'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='baby_images')
    parent_image = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='derivatives'
    )

    generation_type = models.CharField(max_length=20, choices=GENERATION_TYPES)

    father_photo = models.ImageField(upload_to='inputs/fathers/', null=True, blank=True)
    mother_photo = models.ImageField(upload_to='inputs/mothers/', null=True, blank=True)

    gender = models.CharField(max_length=10, null=True, blank=True)
    age_stage = models.CharField(max_length=20, null=True, blank=True)
    background = models.CharField(max_length=20, null=True, blank=True)
    outfit = models.CharField(max_length=50, null=True, blank=True)
    timeline = models.CharField(max_length=20, null=True, blank=True)

    generated_image = models.ImageField(upload_to='generated/', null=True, blank=True)
    high_res_image = models.ImageField(upload_to='generated/highres/', null=True, blank=True)

    eyes_similarity = models.FloatField(null=True, blank=True)
    face_shape_similarity = models.FloatField(null=True, blank=True)
    skin_tone_similarity = models.FloatField(null=True, blank=True)

    ai_provider = models.CharField(max_length=50, null=True, blank=True)
    external_job_id = models.CharField(max_length=255, null=True, blank=True)
    generation_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(null=True, blank=True)

    is_favorite = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_favorite']),
            models.Index(fields=['user', 'is_deleted']),
        ]

    def __str__(self):
        return f'{self.generation_type} — {self.id}'
