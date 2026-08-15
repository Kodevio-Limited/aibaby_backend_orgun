import uuid
from django.db import models
from django.conf import settings


class GenerationPrompt(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    PROMPT_CATEGORIES = [
        ('General Prompt', 'General Prompt'),
        ('Background Prompt', 'Background Prompt'),
        ('Theme Prompt', 'Theme Prompt'),
        ('Monthly Prompt', 'Monthly Prompt'),
        ('Holiday Prompt', 'Holiday Prompt'),
        ('Birthday Prompt', 'Birthday Prompt'),
        ('System Prompt', 'System Prompt'),
        ('Safety Prompt', 'Safety Prompt'),
        ('Negative Prompt', 'Negative Prompt'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    content = models.TextField(help_text='Main prompt text. Use placeholders like {gender}, {age_stage}, {background}, {outfit}.')
    negative_prompt = models.TextField(blank=True)
    variables = models.TextField(blank=True, help_text='Comma-separated variable names supported by this prompt.')
    category = models.CharField(max_length=50, choices=PROMPT_CATEGORIES, default='General Prompt')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class GenerationTemplate(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, default='Portrait')
    background = models.ImageField(upload_to='templates/backgrounds/', null=True, blank=True)
    theme = models.CharField(max_length=50, blank=True)
    background_type = models.CharField(max_length=50, blank=True)
    ai_prompt = models.TextField(help_text='Template-specific prompt text combined with the active GenerationPrompt during generation.')
    maintain_face_identity = models.BooleanField(default=True)
    keep_original_gender = models.BooleanField(default=True)
    keep_original_age = models.BooleanField(default=True)
    enhance_lighting = models.BooleanField(default=False)
    high_quality_rendering = models.BooleanField(default=True)
    allow_background_blur = models.BooleanField(default=True)
    prompt_weight = models.FloatField(default=1.0)
    negative_prompt = models.TextField(blank=True)
    seed = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.name


class ParentPhotoScan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scanning', 'Scanning'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('flagged', 'Flagged'),
    ]

    SCAN_RESULT_CHOICES = [
        ('Clean', 'Clean'),
        ('No Face Detected', 'No Face Detected'),
        ('Duplicate', 'Duplicate'),
        ('NSFW Detected', 'NSFW Detected'),
        ('Watermark Detected', 'Watermark Detected'),
        ('Pending Analysis', 'Pending Analysis'),
        ('Scanning...', 'Scanning...'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parent_photo_scans')

    father_photo = models.ImageField(upload_to='scans/fathers/')
    mother_photo = models.ImageField(upload_to='scans/mothers/')

    father_scan_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    mother_scan_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    father_scan_details = models.JSONField(default=dict, blank=True)
    mother_scan_details = models.JSONField(default=dict, blank=True)

    overall_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    scan_result = models.CharField(max_length=30, choices=SCAN_RESULT_CHOICES, default='Pending Analysis')
    confidence = models.FloatField(default=0)
    reason = models.TextField(blank=True)
    moderator_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} — {self.overall_status}'


class SafetySettings(models.Model):
    """Singleton settings for photo moderation / safety scans."""

    enable_ai_scanning = models.BooleanField(default=True)
    enable_face_detection = models.BooleanField(default=True)
    enable_nsfw_detection = models.BooleanField(default=False)  # skipped for now
    enable_duplicate_detection = models.BooleanField(default=True)
    enable_watermark_detection = models.BooleanField(default=False)
    enable_identity_matching = models.BooleanField(default=False)
    minimum_confidence = models.FloatField(default=0.75)
    auto_reject = models.BooleanField(default=False)
    manual_review = models.BooleanField(default=True)
    max_upload_size = models.PositiveIntegerField(default=10)
    allowed_image_types = models.CharField(max_length=255, default='png, jpg, webp')
    blocked_words = models.TextField(default='violence, gore, explicit, hate, weapons')
    blocked_prompt_list = models.TextField(default='nude, naked, sexual, gore, violent')
    negative_prompt_settings = models.TextField(default='low quality, blurry, distorted, deformed, bad anatomy')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Safety Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


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

    generation_prompt = models.ForeignKey(
        GenerationPrompt, null=True, blank=True, on_delete=models.SET_NULL, related_name='baby_images'
    )
    generation_template = models.ForeignKey(
        GenerationTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name='baby_images'
    )
    parent_photo_scan = models.ForeignKey(
        ParentPhotoScan, null=True, blank=True, on_delete=models.SET_NULL, related_name='baby_images'
    )
    generation_prompt_text = models.TextField(blank=True, help_text='Final assembled prompt used for generation.')

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
