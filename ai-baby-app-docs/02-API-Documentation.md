# API Documentation

All endpoints are prefixed with `/api/`. All authenticated endpoints require
`Authorization: Bearer <access_token>`. All responses follow the format in
`05-Error-Handling-Logging.md`.

---

## Auth

### 1. POST `/api/auth/sign-in/`
**Body:** `{ "email": "", "password": "" }`
**Response:** `{ "data": { "access": "", "refresh": "", "user": {...} } }`

### 2. POST `/api/auth/register/`
**Body:** `{ "full_name": "", "email": "", "password": "", "confirm_password": "" }`
**Response:** `{ "data": { "user": {...} }, "message": "Registered. Please verify your email." }`

### 3. POST `/api/auth/forgot-password/`
**Body:** `{ "email": "" }`
**Response:** `{ "message": "OTP sent to email." }`
Sends a 6-digit OTP to the user's email (expires in ~10 minutes).

### 4. POST `/api/auth/verify-otp/`
**Body:** `{ "email": "", "otp": "" }`
**Response:** `{ "data": { "reset_token": "" }, "message": "OTP verified." }`
Returns a short-lived `reset_token` used in the next call — do not allow
password reset with just an email, always require this verified token.

### 5. POST `/api/auth/reset-password/`
**Body:** `{ "reset_token": "", "password": "", "confirm_password": "" }`
**Response:** `{ "message": "Password updated." }`

> Note: the original spec had this endpoint take only `password` +
> `confirm_password`. Adding `reset_token` here is a required correction —
> without it, anyone who knows a user's email could reset their password
> without ever proving they own that inbox. The OTP step becomes pointless
> otherwise.

---

## Baby Generation

### 6. POST `/api/baby-images/parent-photo-scans/`
**Body (multipart):** `father_photo`, `mother_photo`
**Response:** `{ "data": { "id": "uuid", "overall_status": "pending" } }`
Creates a `ParentPhotoScan` row and dispatches a Celery task to verify the
photos. Client polls endpoint #7.

### 7. GET `/api/baby-images/parent-photo-scans/{id}/`
**Response:** `{ "data": { "id": "uuid", "overall_status": "approved|rejected", "scan_result": "Clean|No Face Detected|Duplicate|...", ... } }`

### 8. GET `/api/baby-images/templates/active/`
**Response:** `{ "data": [ { "id": "uuid", "name": "...", "background": "..." } ] }`
Lists active `GenerationTemplate` records the user can choose from.

### 9. POST `/api/baby-images/generate/`
**Body (JSON):** `parent_photo_scan_id`, optional `template_id`
**Response:** `{ "data": { "id": "uuid", "status": "pending" } }`
Creates a `BabyImage` row (`generation_type=initial`), dispatches Celery task.
Requires the scan to have `overall_status=approved`.

### 10. POST `/api/baby-images/generate-with-options/`
**Body (JSON):** `parent_photo_scan_id`, optional `template_id`, `gender`, `age_stage`, `background`
**Response:** `{ "data": { "id": "uuid", "status": "pending" } }`
Same as above, `generation_type=age_stage`.

### 11. POST `/api/baby-images/{id}/change-age/`
**Body:** `{ "age_stage": "" }`
**Response:** `{ "data": { "id": "new-uuid", "status": "pending" } }`
Uses `{id}` as `parent_image`. Regenerates using the *original* father/mother
photos stored on the root of the chain (see Implementation Guide) at the
new age stage.

### 12. POST `/api/baby-images/{id}/change-outfit/`
**Body:** `{ "outfit": "" }`
**Response:** `{ "data": { "id": "new-uuid", "status": "pending" } }`

### 13. POST `/api/baby-images/{id}/generate-high-res/`
**Body:** `{}` (uses `{id}`'s generated image as input)
**Response:** `{ "data": { "id": "new-uuid", "status": "pending" } }`

---

## Timeline

### 14. POST `/api/baby-images/generate-timeline/`
**Body (JSON):** `parent_photo_scan_id`, optional `template_id`, `timeline`
**Response (once done, via status endpoint):** same as status endpoint #18.

---

## Library

### 12. GET `/api/baby-images/?filter=favorite`
**Response:** `{ "data": { "results": [...], "count": N, "next": "", "previous": "" } }`

### 13. GET `/api/baby-images/?filter=history`
**Response:** same shape as above, all non-deleted images for the user,
newest first.

---

## Profile

### 15. PATCH `/api/profile/`
**Body:** `{ "full_name": "", "email": "" }`

### 16. PATCH `/api/profile/change-password/`
**Body:** `{ "current_password": "", "new_password": "", "confirm_password": "" }`

### 17. POST `/api/auth/logout/`
**Body:** `{ "refresh": "" }`
Blacklists the refresh token.

### 18. PATCH `/api/profile/picture/`
**Body (multipart):** `profile_picture`

---

## Status Polling (required for async generation)

### 19. GET `/api/baby-images/{id}/status/`
**Response (pending/processing):**
```json
{ "data": { "id": "uuid", "status": "processing" } }
```
**Response (done):**
```json
{
  "data": {
    "id": "uuid",
    "status": "done",
    "generated_image": "https://.../image.jpg",
    "eyes_similarity": 72.4,
    "face_shape_similarity": 65.1,
    "skin_tone_similarity": 88.0
  }
}
```
**Response (failed):**
```json
{ "data": { "id": "uuid", "status": "failed", "error_message": "No face detected in father_photo" } }
```

Frontend should poll this every 2–3 seconds after any generation call until
`status` is `done` or `failed`.

---

## Subscriptions / Credits

### 20. GET `/api/subscriptions/plans/`
**Response:** `{ "data": [ { "id": "uuid", "name": "...", "price": 9.99, "credits": 100, ... } ] }`
Lists active `CreditPlan` records.

### 21. POST `/api/subscriptions/checkout/`
**Body:** `{ "plan_id": "uuid", "provider": "stripe|test" }`
**Response:** `{ "data": { "payment_id": "uuid", "client_secret": "...", "provider": "stripe", "amount": 9.99, "currency": "USD" } }`
Creates a pending `Payment`. When Stripe is configured it returns a `client_secret`; otherwise it returns a test `payment_id`.

### 22. POST `/api/subscriptions/confirm/`
**Body:** `{ "payment_id": "uuid" }`
**Response:** `{ "data": { ...Payment object... } }`
Marks the payment as succeeded and credits the user's balance. Mainly used for test/manual confirmation; production confirmation normally happens via the webhook.

### 23. GET `/api/subscriptions/my-transactions/`
**Response:** paginated list of `CreditTransaction` records.

### 24. GET `/api/subscriptions/balance/`
**Response:** `{ "data": { "credits_balance": 100 } }`

### 25. POST `/api/subscriptions/webhook/`
Payment-provider webhook. Supports Stripe `payment_intent.succeeded` when `STRIPE_WEBHOOK_SECRET` is configured.

---

## Admin endpoints (require Django staff user)

| # | Method | Path | Notes |
|---|--------|------|-------|
| A1 | GET/POST | `/api/admin/prompts/` | list / create prompts |
| A2 | GET/PATCH/DELETE | `/api/admin/prompts/{id}/` | detail / update / delete |
| A3 | POST | `/api/admin/prompts/{id}/duplicate/` | duplicate prompt |
| A4 | GET/POST | `/api/admin/templates/` | list / create templates (multipart) |
| A5 | GET/PATCH/DELETE | `/api/admin/templates/{id}/` | detail / update / delete |
| A6 | POST | `/api/admin/templates/{id}/duplicate/` | duplicate template |
| A7 | GET | `/api/admin/moderation/` | list parent-photo scans |
| A8 | GET/PATCH/DELETE | `/api/admin/moderation/{id}/` | detail / update / delete |
| A9 | POST | `/api/admin/moderation/{id}/reset/` | delete photos, clear scan result |
| A10 | POST | `/api/admin/moderation/{id}/rescan/` | re-queue scan task |
| A11 | GET | `/api/admin/moderation/stats/` | scan stats |
| A12 | GET/PUT | `/api/admin/moderation/settings/` | safety settings singleton |
| A13 | GET/POST | `/api/admin/billing/credit-plans/` | list / create credit plans |
| A14 | GET/PATCH/DELETE | `/api/admin/billing/credit-plans/{id}/` | detail / update / delete |
| A15 | GET | `/api/admin/billing/transactions/` | list credit transactions |

---

## Endpoints intentionally not built yet (flagged for future, not missing)

- `GET /api/baby-images/{id}/` (single detail) — likely needed by the
  frontend for a "share/view" screen; trivial to add, same serializer as
  the status endpoint.
