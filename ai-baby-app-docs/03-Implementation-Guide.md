# Implementation Guide

## Stack

Django + DRF + Celery + Redis + **one** external API key (image generation).
No self-hosted GPU, no second AI vendor for similarity scoring.

```
Client → Django (APIView) → creates BabyImage row (status=pending) → dispatches Celery task
                                                                              │
                                                                              ▼
                                                    Celery task calls image-gen API (Replicate/fal.ai)
                                                                              │
                                                                              ▼
                                                    Downloads result, saves to BabyImage.generated_image
                                                                              │
                                                                              ▼
                                        Task runs local similarity scoring (face_recognition + OpenCV)
                                                                              │
                                                                              ▼
                                                        Saves scores, sets status=done
Client polls GET /baby-images/{id}/status/ until done/failed
```

## 1. Image generation (single API key)

Use **Replicate** (or fal.ai — pick one, don't integrate both). Both are
pure HTTPS APIs: you call them with an API token, they run the model on
their GPUs, you get a URL back. No infrastructure to run yourself.

Recommended models to test against each other for best likeness-to-parents
results:
- Identity-preserving models (e.g. InstantID-style) — good at blending a
  face identity into a new image.
- Reference-image editing models that accept multiple reference photos
  directly (e.g. Flux Kontext-style, or character-consistency models) —
  simpler to integrate since you pass both parent photos as references with
  a text prompt, no manual embedding math required.

Start with whichever is simplest to wire up, generate ~20 test pairs, and
judge likeness yourself before locking in the final model choice.

```python
# babies/services/generation_service.py
import replicate
from django.conf import settings

class GenerationService:
    def __init__(self):
        self.client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)

    def generate_baby(self, father_photo_url, mother_photo_url, prompt_extra=""):
        prompt = f"a realistic photo of a baby, natural lighting {prompt_extra}".strip()
        prediction = self.client.predictions.create(
            model="<chosen-model-slug>",
            input={
                "image": father_photo_url,       # exact input keys depend on chosen model
                "image2": mother_photo_url,
                "prompt": prompt,
            }
        )
        return prediction  # has .id and .status — save prediction.id to external_job_id

    def get_prediction_result(self, prediction_id):
        prediction = self.client.predictions.get(prediction_id)
        return prediction  # .status is 'starting' | 'processing' | 'succeeded' | 'failed'
```

Build the prompt from the request fields: `age_stage` → "newborn baby" /
"6 month old baby" / etc, `background` → "studio background" / "at home" /
"outdoors in nature", `outfit` → append when set, `gender` → "baby boy" /
"baby girl" / for twins, generate two predictions.

## 2. Celery task (the core of the app)

```python
# babies/tasks.py
from celery import shared_task
from .models import BabyImage
from .services.generation_service import GenerationService
from .services.similarity_service import SimilarityService

@shared_task
def process_baby_generation(baby_image_id):
    baby_image = BabyImage.objects.get(id=baby_image_id)
    baby_image.generation_status = 'processing'
    baby_image.save(update_fields=['generation_status'])

    try:
        gen_service = GenerationService()
        prediction = gen_service.generate_baby(
            father_photo_url=baby_image.father_photo.url,
            mother_photo_url=baby_image.mother_photo.url,
            prompt_extra=_build_prompt_extra(baby_image),
        )
        baby_image.external_job_id = prediction.id
        baby_image.ai_provider = "replicate:<model-slug>"
        baby_image.save(update_fields=['external_job_id', 'ai_provider'])

        # poll until done — Replicate predictions are usually done in 5-30s
        result = gen_service.client.predictions.wait(prediction)
        if result.status != 'succeeded':
            raise Exception(f"Generation failed: {result.error}")

        image_url = result.output[0] if isinstance(result.output, list) else result.output
        baby_image.generated_image = _download_and_save(image_url)

        # local similarity scoring — no external call, approximate on purpose
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
```

## 3. Local similarity scoring (no external key)

```python
# babies/services/similarity_service.py
import face_recognition
import cv2
import numpy as np

class SimilarityService:
    def compare_faces(self, image_a_path, image_b_path):
        try:
            img_a = face_recognition.load_image_file(image_a_path)
            img_b = face_recognition.load_image_file(image_b_path)
            enc_a = face_recognition.face_encodings(img_a)
            enc_b = face_recognition.face_encodings(img_b)
            if not enc_a or not enc_b:
                return None  # no face detected — don't block the generation
            distance = face_recognition.face_distance([enc_b[0]], enc_a[0])[0]
            return round((1 - distance) * 100, 1)  # rough, not clinical
        except Exception:
            return None

    def compare_skin_tone(self, image_a_path, image_b_path):
        try:
            img_a = cv2.cvtColor(cv2.imread(image_a_path), cv2.COLOR_BGR2LAB)
            img_b = cv2.cvtColor(cv2.imread(image_b_path), cv2.COLOR_BGR2LAB)
            avg_a = img_a.reshape(-1, 3).mean(axis=0)
            avg_b = img_b.reshape(-1, 3).mean(axis=0)
            delta_e = np.linalg.norm(avg_a - avg_b)
            return round(max(0, 100 - delta_e), 1)
        except Exception:
            return None
```

`face_recognition` (dlib-based) is MIT licensed — no commercial-use
restriction, unlike InsightFace's encoder. This is why it was chosen over
the alternative discussed earlier.

For **eyes** and **face shape** specifically: `face_recognition.face_landmarks()`
returns named regions (`left_eye`, `right_eye`, `chin`, `nose_bridge`, etc).
Crop those regions from both images before passing to `compare_faces` to get
a more targeted (still approximate) score instead of comparing whole faces.

## 4. Age-chain regeneration rule

`change_age` and `change_outfit` must use the **original father/mother
photos**, not the most recently generated image, to avoid quality
degradation across repeated AI generations ("regeneration drift"). Walk the
`parent_image` chain back to the row where `generation_type='initial'` or
`'age_stage'` to find the original photos:

```python
def get_root_photos(baby_image):
    node = baby_image
    while node.parent_image is not None:
        node = node.parent_image
    return node.father_photo, node.mother_photo
```

## 5. Environment variables needed

```
REPLICATE_API_TOKEN=            # the single image-gen API key
SECRET_KEY=
DATABASE_URL=
REDIS_URL=
```

No second API key for similarity — it's fully local.

## 6. Order of build (for the AI agent)

1. Settings structure, custom User + Subscription models, JWT auth
2. Auth endpoints (1–5)
3. BabyImage model + Celery/Redis wiring
4. GenerationService (Replicate) + status endpoint (18) — get one working
   end-to-end generation before adding anything else
5. SimilarityService — add scoring into the same task
6. Remaining generation endpoints (7–11), reusing the same task with
   different `generation_type`
7. Library endpoints (12–13), Profile endpoints (14–17)
8. Tests, especially failure paths: no face detected, provider timeout,
   malformed image upload
