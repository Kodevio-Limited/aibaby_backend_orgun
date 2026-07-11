# Database Models

Two apps: `accounts` and `babies`. UUID primary keys are used on
user-facing models so IDs can't be guessed or enumerated.

## accounts/models.py

```python
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)

    is_pro = models.BooleanField(default=False)      # fast feature-gating check
    is_verified = models.BooleanField(default=False)  # email verified via OTP flow

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return self.email


class SubscriptionPlan(models.Model):
    """
    Lookup table for plan tiers. Add a new tier by adding a row, not a
    migration. Keeps User clean of pricing/billing detail.
    """
    PLAN_TYPES = [
        ('starter', 'Starter'),
        ('lifetime', 'Lifetime'),
    ]

    name = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_days = models.PositiveIntegerField(null=True, blank=True)   # null = lifetime
    generation_limit = models.PositiveIntegerField(null=True, blank=True)  # null = unlimited
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.get_name_display()


class Subscription(models.Model):
    """
    A user's subscription history. User.is_pro is derived from whether an
    'active' row exists here — keep them in sync via a signal or a
    scheduled Celery task that expires rows past expires_at.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    payment_reference = models.CharField(max_length=255, null=True, blank=True)  # payment gateway id
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']


class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
```

## babies/models.py

```python
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

    gender = models.CharField(max_length=10, null=True, blank=True)       # boy, girl, twins
    age_stage = models.CharField(max_length=20, null=True, blank=True)    # newborn, 3m, 6m, 1y ...
    background = models.CharField(max_length=20, null=True, blank=True)   # studio, home, nature
    outfit = models.CharField(max_length=50, null=True, blank=True)
    timeline = models.CharField(max_length=20, null=True, blank=True)

    generated_image = models.ImageField(upload_to='generated/', null=True, blank=True)
    high_res_image = models.ImageField(upload_to='generated/highres/', null=True, blank=True)

    eyes_similarity = models.FloatField(null=True, blank=True)
    face_shape_similarity = models.FloatField(null=True, blank=True)
    skin_tone_similarity = models.FloatField(null=True, blank=True)

    ai_provider = models.CharField(max_length=50, null=True, blank=True)   # e.g. "replicate:instant-id"
    external_job_id = models.CharField(max_length=255, null=True, blank=True)  # provider's prediction id
    generation_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(null=True, blank=True)

    is_favorite = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # soft delete — never hard-delete a generation record

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
```

## Design notes

- **Why one `BabyImage` model instead of six tables:** every "action"
  (change age, change outfit, upscale, timeline) is just a new row with
  `parent_image` pointing at the row it came from. History and favorites
  are both a single filtered query on this one table — no joins needed.
- **Why UUID primary keys:** these IDs get exposed directly in API URLs
  (`/baby-images/{id}/status/`). Sequential integer IDs would let one user
  guess and probe other users' image IDs.
- **Why `ai_provider` + `external_job_id`:** if you ever add a second
  provider or need to re-poll a stuck generation, you need to know which
  provider generated which row and what its job ID was there.
- **Why `is_pro` stays on `User` but plan detail lives in `Subscription`:**
  every permission check in the app does `request.user.is_pro` — cheap,
  no join. Billing history, renewal dates, and payment references belong in
  their own table so they can grow (refunds, plan changes, Stripe webhook
  data) without ever touching `User` again.
