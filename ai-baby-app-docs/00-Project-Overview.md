# Project Overview — AI Baby Generator

## What this application does

Users upload a photo of the father and a photo of the mother. Using AI, the
application generates a realistic image of what their baby could look like,
with control over gender, age stage (newborn → 1 year+), background setting,
and outfit. Generated babies can be "aged forward" along a timeline, have
their outfit changed, and be upscaled to high resolution. The app also
returns a rough similarity breakdown (eyes, face shape, skin tone) between
the generated baby and each parent.

## Core principles for this build

1. **Identity-preserving generation, not generic AI babies.** The generated
   image must actually resemble the two input photos. Plain text-to-image
   prompting is not acceptable — the app must use a reference/identity-
   preserving image model.
2. **One image-generation API key.** All image generation goes through a
   single external provider (Replicate or fal.ai). No self-hosted GPU
   server, no second AI vendor.
3. **Similarity scoring is local and approximate.** Eyes/face-shape/skin-tone
   similarity is computed in Python inside the Celery worker using
   open-source libraries (`face_recognition`, OpenCV). It does not call an
   external API and does not need to be lab-accurate — it's a UX feature,
   not a scientific one.
4. **Async by default.** Every generation is slow (seconds to tens of
   seconds). Nothing runs synchronously in the request/response cycle.
   Django creates a record and dispatches a Celery task; the client polls a
   status endpoint.
5. **Subscription-aware from day one.** Users are either free or `is_pro`.
   Premium tiers (`starter`, `lifetime`) are modeled as a lookup table +
   subscription history table, not hardcoded fields, so pricing/plans can
   change without touching the `User` model again.
6. **Architecture consistency.** Every app in this project follows the same
   settings structure, error format, logging setup, and APIView + service
   layer pattern described in the companion docs in this folder. Any AI
   coding agent (DeepSeek, etc.) working on this codebase should be given
   this entire folder as context, not just one file at a time.

## Screens in this app

- Sign In / Register / Forgot Password / Verify OTP / Reset Password
- Home (generate baby — basic and with age stage/gender/background)
- Create flow (guided version of the same generation)
- Result screen (change age, change outfit, generate high-res, view other
  ages → timeline)
- Timeline screen (regenerate baby at a specific age with similarity scores)
- Library (favorites filter, history filter)
- Profile (edit profile, change password, update profile picture, logout)

## Companion documents in this folder

| File | Purpose |
|---|---|
| `01-Database-Models.md` | Full Django model definitions |
| `02-API-Documentation.md` | All 18 API endpoints, request/response bodies |
| `03-Implementation-Guide.md` | How generation + similarity scoring actually work, step by step |
| `04-Settings-Structure.md` | Standard Django settings layout (base/dev/prod split) |
| `05-Error-Handling-Logging.md` | Standard error format, logging, Sentry, health check |
| `06-APIView-Service-Patterns.md` | Standard view/serializer/service-layer pattern (APIView-based) |

Give an AI coding agent this entire folder before it writes a single line of
code. These documents are the source of truth for architecture — if the
agent's output diverges from them, that's a bug in the output, not an
acceptable variation.
