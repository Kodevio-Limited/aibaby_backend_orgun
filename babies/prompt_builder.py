"""Deterministic prompt factory for baby image generation.

Inspired by config-driven prompt architectures (per-tier system prompts +
injected context blocks): every generation type defines the exact ordered
segments that MUST appear in the prompt, and every user-supplied parameter
(gender, age, background, outfit, timeline) is resolved deterministically so
the model always receives the full, precise configuration the client asked for.
"""

import re
from typing import Dict, List


# ─── Descriptive segment vocabulary ──────────────────────────────────────────────

# Composition anchors injected into EVERY generation prompt. They guarantee a
# single-subject, face-first portrait — PhotoMaker is fed two parent reference
# photos and tends to render extra people (or full bodies with hands/feet)
# unless the prompt explicitly rules them out.
SINGLE_BABY_DESCRIPTOR = 'a single baby only, one baby, exactly one baby, one central subject in the frame'
CLOSEUP_DESCRIPTOR = 'close-up head and shoulders portrait, face filling the frame, hands and feet not visible'

GENDER_DESCRIPTORS = {
    'boy': 'a baby boy',
    'girl': 'a baby girl',
    'twins': 'twin babies',
}

BACKGROUND_DESCRIPTORS = {
    'studio': 'studio background',
    'home': 'at home',
    'nature': 'outdoors in nature',
}

KNOWN_AGE_DESCRIPTORS = {
    'newborn': 'a newborn baby, just a few days old, tiny infant',
    '3m': 'a 3 month old baby, infant with baby features',
    '6m': 'a 6 month old baby, infant with chubby baby cheeks',
    '1y': 'a 1 year old baby, toddler with baby features',
}


def age_descriptor(age_stage: str) -> str:
    """Resolve any free-text age stage into a precise prompt descriptor.

    Known stages use curated phrasing; free-text stages are parsed
    deterministically (e.g. '5y' -> 'a 5 year old child', '18m' -> 'a 18 month
    old baby') so the age the client sends is exactly what reaches the model.
    Every phrase anchors the subject as a baby/young child so the model does
    not drift toward an adult.
    """
    stage = (age_stage or '').strip().lower()
    if not stage:
        return ''
    if stage in KNOWN_AGE_DESCRIPTORS:
        return KNOWN_AGE_DESCRIPTORS[stage]
    if stage == 'newborn':
        return KNOWN_AGE_DESCRIPTORS['newborn']

    months = re.match(r'^(\d+)m$', stage)
    if months:
        return f'a {months.group(1)} month old baby, young infant with baby features'

    years = re.match(r'^(\d+)y$', stage)
    if years:
        count = int(years.group(1))
        if count <= 1:
            return f'a {count} year old baby, age exactly {count} year, toddler with baby features'
        return f'a {count} year old child, age exactly {count} years, young child with soft baby-like features, definitely a child, not an adult, not a teenager'

    return f'a {stage} old baby'


def outfit_phrase(outfit: str) -> str:
    outfit = (outfit or '').strip()
    if not outfit:
        return ''
    return f'wearing {outfit}'


def _segments_for(baby_image) -> List[str]:
    """Ordered, guaranteed segments for the current image configuration."""
    segments = [SINGLE_BABY_DESCRIPTOR, CLOSEUP_DESCRIPTOR]

    gender = (getattr(baby_image, 'gender', '') or '').strip().lower()
    if gender in GENDER_DESCRIPTORS:
        segments.append(GENDER_DESCRIPTORS[gender])

    age = age_descriptor(getattr(baby_image, 'age_stage', '') or getattr(baby_image, 'timeline', '') or '')
    if age:
        segments.append(age)

    background = (getattr(baby_image, 'background', '') or '').strip().lower()
    if background in BACKGROUND_DESCRIPTORS:
        segments.append(BACKGROUND_DESCRIPTORS[background])

    outfit = outfit_phrase(getattr(baby_image, 'outfit', ''))
    if outfit:
        segments.append(outfit)

    return segments


# ─── Per-generation-type checkpoints ─────────────────────────────────────────────
# Each entry declares the segments that MUST be present for that generation type,
# in priority order. Segments the image does not carry (e.g. no outfit) are
# simply skipped — the guarantee is about never *dropping* a carried value.

PROMPT_CHECKPOINTS: Dict[str, Dict] = {
    'initial': {
        'required': ['gender', 'age'],
        'allow_blank': ['background', 'outfit'],
    },
    'age_stage': {
        'required': ['gender', 'age', 'background'],
        'allow_blank': ['outfit'],
    },
    'timeline': {
        'required': ['gender', 'age', 'background'],
        'allow_blank': ['outfit'],
    },
    'age_change': {
        'required': ['gender', 'age', 'background'],
        'allow_blank': ['outfit'],
    },
    'outfit_change': {
        'required': ['gender', 'age', 'background', 'outfit'],
        'allow_blank': [],
    },
    'high_res': {
        'required': ['gender', 'age', 'background'],
        'allow_blank': ['outfit'],
    },
}


def _template_context(template) -> Dict:
    if not template:
        return {}
    return {
        'template_name': template.name,
        'template_description': template.description,
        'template_category': template.category,
        'template_theme': template.theme,
        'template_background_type': template.background_type,
        'template_background_url': template.background.url if template.background else None,
    }


def build_context_snapshot(baby_image) -> Dict:
    """Persisted audit record: exactly what the client asked for + what we sent."""
    template = getattr(baby_image, 'generation_template', None)
    return {
        'gender': baby_image.gender,
        'age_stage': baby_image.age_stage,
        'background': baby_image.background,
        'outfit': baby_image.outfit,
        'timeline': baby_image.timeline,
        'generation_type': baby_image.generation_type,
        'parent_id': str(baby_image.parent_image_id) if baby_image.parent_image_id else None,
        'parent_photo_scan_id': str(baby_image.parent_photo_scan_id) if baby_image.parent_photo_scan_id else None,
        'father_photo': baby_image.father_photo.url if baby_image.father_photo else None,
        'mother_photo': baby_image.mother_photo.url if baby_image.mother_photo else None,
        'age_descriptor': age_descriptor(baby_image.age_stage or baby_image.timeline or ''),
        'segments': _segments_for(baby_image),
        **_template_context(template),
    }


def build_prompt_extra(baby_image) -> str:
    """The descriptive configuration string appended to the base prompt."""
    return ', '.join(_segments_for(baby_image))


# ─── User-driven context boost ────────────────────────────────────────────────
# The strongest, most specific part of the generated prompt. It is built ONLY
# from the client's input (age, background, outfit, timeline) plus parent-
# resemblance guidance, so every generation/derivative (change-age,
# change-outfit, timeline) carries the exact context the user asked for straight
# to the model. This prevents e.g. a change-outfit from accidentally ageing the
# baby or dropping the parent identity.

def build_context_boost(baby_image) -> str:
    """A context block appended to the prompt, derived purely from user input.

    Stated as full sentences so age, background and especially the outfit are
    unambiguous to the model, and so the baby always inherits the father and
    mother's identity from the reference photos.
    """
    age = age_descriptor(baby_image.age_stage or baby_image.timeline or '')
    outfit = (getattr(baby_image, 'outfit', '') or '').strip()
    bg = (getattr(baby_image, 'background', '') or '').strip().lower()
    background = BACKGROUND_DESCRIPTORS.get(bg, '')

    sentences = []
    if age:
        sentences.append(f'This is {age}.')
    if background:
        sentences.append(f'The setting is {background}.')
    if outfit:
        sentences.append(f'The baby is wearing {outfit}.')

    template = getattr(baby_image, 'generation_template', None)
    if template:
        if template.theme:
            sentences.append(f'The theme is {template.theme}.')
        if template.description:
            sentences.append(f'Style: {template.description}')
        if template.category:
            sentences.append(f'Category: {template.category}')
        if template.background_type:
            sentences.append(f'Environment: {template.background_type}')

    sentences.append(
        'The baby\'s face must be a realistic, highly detailed blend of the '
        'father and mother from the reference photos.'
    )
    return ' '.join(sentences)


def build_outfit_prompt(outfit) -> str:
    """Dedicated prompt builder for outfit changes.

    The outfit text (with its exact colour) is the authoritative cloth
    instruction, stated as a full sentence so a known colour like "red" is
    unambiguous. Stored on the derivative for audit; the local outfit editor
    extracts the colour from the same string.
    """
    outfit = (outfit or '').strip()
    return f'The baby is wearing {outfit}.' if outfit else ''


# ─── Negative prompt blocks ──────────────────────────────────────────────────────

AGE_DRIFT_NEGATIVE = (
    'adult, grown up, grown-up, teenager, young adult, man, woman, '
    'elderly, aged, mature face, facial hair, adult features, adolescent, '
    'adult teeth, long face, old child, 20 year old, 30 year old, 40 year old'
)

BASE_QUALITY_NEGATIVE = (
    'nsfw, lowres, bad anatomy, bad hands, text, error, missing fingers, '
    'extra digit, fewer digits, cropped, worst quality, low quality, '
    'normal quality, jpeg artifacts, signature, watermark, username, blurry'
)

MULTIPLE_PEOPLE_NEGATIVE = (
    'two people, multiple people, group photo, family photo, more than one person, '
    'siblings, twins, multiple babies, two babies, extra child, another child, '
    'several babies, duplicate baby, duplicated face, split image, split frame, '
    'collage, diptych, double exposure, two portraits in one frame, cropped baby, '
    'half of a baby at the top and half at the bottom, cropped head, cut off face, crowd'
)

FULL_BODY_NEGATIVE = (
    'full body, whole body, full-length, entire body, hands, fingers, '
    'fingers visible, showing hands, arms, feet, legs, shoes, toes, '
    'hands in frame, full body shot, body visible, lower body'
)