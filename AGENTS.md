# AI Baby Generator Backend — Agent Guide

## Architecture

- **Stack**: Django 5.x + DRF + Celery + Redis + **one** external image-gen API (Replicate or fal.ai)
- **Apps**: `accounts` (User, SubscriptionPlan, Subscription, OTP) and `babies` (BabyImage)
- **Two Django apps only**: `accounts` and `babies`
- **UUID primary keys** on all user-facing models (prevents ID enumeration). Sequential PKs are never exposed.
- **Custom User model** with `email` as `USERNAME_FIELD`, `REQUIRED_FIELDS = ['full_name']`
- **`is_pro` on User** for cheap permission checks; billing detail lives in `Subscription` table
- **`BabyImage` is a single table** for all generation types (`initial`, `age_stage`, `timeline`, `age_change`, `outfit_change`, `high_res`) — variants are linked via `parent_image` FK. Never hard-delete rows (use `is_deleted=True`).

## Non-negotiable patterns

- **`APIView` only** — never `ModelViewSet`/`GenericViewSet`. Every endpoint uses plain `APIView`.
- **Service layer always** — views call an instantiated service class. Business logic never lives in views.
- **`try/except` in every view** wrapping every service call, returning the standard error format.
- **Paginate all list endpoints** via `core.pagination.StandardPagination` (LimitOffset, default 20, max 100).
- **Serializers** for input validation and output shaping (separate list vs detail serializers when helpful).
- **Instantiated services** (never `@staticmethod`) — constructor takes relevant context (e.g. `user`).
- **Ownership enforced at query level** — every service filters by `self.user`. Object-level permissions are secondary.

## Settings

- `config/settings/base.py` (shared), `development.py` (DEBUG, CORS_ALLOW_ALL), `production.py` (locked down)
- `DJANGO_SETTINGS_MODULE=config.settings.development` for local dev
- `config/settings/production.py` has Sentry, HSTS, secure cookies, rotating file logging
- `core/exceptions.py` — custom exception handler returning `{"detail": ..., "code": ...}` format
- `core/pagination.py` — `StandardPagination` class (always use this, never DRF defaults)

## Response format

- Success: `{"data": {...}, "message": "optional"}`
- Error: `{"detail": "str", "code": "ERROR_CODE"}`
- Lists: `{"data": {"results": [...], "count": N, "next": "...", "previous": "..."}}`

## Async generation flow

1. View creates `BabyImage` row (`status=pending`), dispatches Celery task via `.delay()`
2. Task sets `status=processing` → calls Replicate/fal.ai → polls until done → saves image → runs local similarity scoring → sets `status=done`
3. Client polls `GET /api/baby-images/{id}/status/` every 2-3s

## Generation rules

- **Age-chain**: `change_age`/`change_outfit` must walk the `parent_image` chain back to root (`generation_type='initial'` or `'age_stage'`) to find original father/mother photos — never regenerate from a previously-generated image (prevents quality degradation).
- **Similarity scoring is local** — `face_recognition` (dlib, MIT license) + OpenCV in the Celery worker. No external API. Eyes/face-shape use `face_landmarks()` cropping for targeted comparison.
- **Prompt building**: gender → "baby boy"/"baby girl", age_stage → "newborn baby"/"6 month old baby", background → "studio background"/"at home"/"outdoors in nature", outfit → appended when set.

## Auth

- JWT via `rest_framework_simplejwt` — `Authorization: Bearer <access_token>`
- Password reset requires 3-step flow: forgot-password → verify-otp (returns `reset_token`) → reset-password (requires `reset_token`)

## Endpoints (all under `/api/`)

| # | Method | Path | Notes |
|---|--------|------|-------|
| 1 | POST | `/auth/sign-in/` | |
| 2 | POST | `/auth/register/` | |
| 3 | POST | `/auth/forgot-password/` | sends 6-digit OTP |
| 4 | POST | `/auth/verify-otp/` | returns `reset_token` |
| 5 | POST | `/auth/reset-password/` | requires `reset_token` |
| 6 | POST | `/baby-images/generate/` | multipart, dispatches Celery |
| 7 | POST | `/baby-images/generate-with-options/` | |
| 8 | POST | `/baby-images/{id}/change-age/` | |
| 9 | POST | `/baby-images/{id}/change-outfit/` | |
| 10 | POST | `/baby-images/{id}/generate-high-res/` | |
| 11 | POST | `/baby-images/generate-timeline/` | |
| 12 | GET | `/baby-images/?filter=favorite` | |
| 13 | GET | `/baby-images/?filter=history` | |
| 14 | PATCH | `/profile/` | |
| 15 | PATCH | `/profile/change-password/` | |
| 16 | POST | `/auth/logout/` | blacklists refresh token |
| 17 | PATCH | `/profile/picture/` | multipart |
| 18 | GET | `/baby-images/{id}/status/` | polling endpoint |
| — | GET | `/api/health/` | unauthenticated, required for deploy |

## Env vars

```
REPLICATE_API_TOKEN=
SECRET_KEY=
DATABASE_URL=
REDIS_URL=
SENTRY_DSN=           # production only
ALLOWED_HOSTS=         # production only
CORS_ALLOWED_ORIGINS=  # production only
```

## Key model fields (BabyImage)

- `generation_type`: initial, age_stage, timeline, age_change, outfit_change, high_res
- `parent_image`: FK to self (null for initial generations)
- `father_photo`, `mother_photo`: original uploads (InputField)
- `generated_image`, `high_res_image`: outputs
- `gender`, `age_stage`, `background`, `outfit`, `timeline`: generation params
- `eyes_similarity`, `face_shape_similarity`, `skin_tone_similarity`: similarity scores
- `ai_provider`, `external_job_id`: tracking
- `generation_status`: pending, processing, done, failed
- `is_favorite`, `is_deleted`: library/soft-delete

## Things that differ from defaults

- `AUTH_USER_MODEL = 'accounts.User'` with email as login field
- `USERNAME_FIELD = 'email'` + `REQUIRED_FIELDS = ['full_name']` — username field is not used
- Throttling: 1000/day per user, 100/day per anonymous
- Health check at `/api/health/` is unauthenticated (no auth/permission classes)
- `SECURE_SSL_REDIRECT = True` in production — all HTTP redirected to HTTPS

## Build order (when implementing from scratch)

1. Settings structure, custom User + Subscription models, JWT auth
2. Auth endpoints (1–5)
3. BabyImage model + Celery/Redis wiring
4. GenerationService + status endpoint (get one full generation working first)
5. SimilarityService (add into the existing task)
6. Remaining generation endpoints (7–11)
7. Library + Profile endpoints (12–17)
8. Tests — especially failure paths (no face, provider timeout, malformed upload)

## Source of truth

The 7 docs in `ai-baby-app-docs/` are the authoritative architecture specification. If generated code diverges from them, that is a bug.
