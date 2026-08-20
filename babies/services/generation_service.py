from django.conf import settings
from ..prompt_builder import (
    AGE_DRIFT_NEGATIVE,
    BASE_QUALITY_NEGATIVE,
    FULL_BODY_NEGATIVE,
    MULTIPLE_PEOPLE_NEGATIVE,
)

# Default model: PhotoMaker (supports prompt + multiple reference images).
REPLICATE_BABY_MODEL = getattr(settings, 'REPLICATE_BABY_MODEL', 'tencentarc/photomaker')
REPLICATE_BABY_VERSION = getattr(
    settings,
    'REPLICATE_BABY_VERSION',
    'ddfc2b08d209f9fa8c1eca692712918bd449f695dabb4a958da31802a9570fe4'
)
REPLICATE_BABY_PROVIDER = f'replicate:{REPLICATE_BABY_MODEL}:{REPLICATE_BABY_VERSION}'

# Legacy model that only accepts two images + gender.
REPLICATE_BABY_MODEL_LEGACY = 'smoosh-sh/baby-mystic'
REPLICATE_BABY_VERSION_LEGACY = 'ba5ab694a9df055fa469e55eeab162cc288039da0abd8b19d956980cc3b49f6d'


class GenerationService:
    def __init__(self):
        import replicate
        self.client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)
        self.model = REPLICATE_BABY_MODEL
        self.version = REPLICATE_BABY_VERSION

    def _get_active_prompt(self):
        from ..models import GenerationPrompt
        return GenerationPrompt.objects.filter(status='active').order_by('-created_at').first()

    def build_prompt(self, baby_image=None, gender=None, age_stage=None, background=None, outfit=None, template=None, prompt_extra=''):
        """Assemble the final prompt text from the active admin prompt + user-selected template."""
        active_prompt = self._get_active_prompt()
        base = active_prompt.content if active_prompt else 'a realistic photo of a baby, natural lighting'

        template_text = ''
        if template and template.ai_prompt:
            template_text = template.ai_prompt

        parts = [base]
        if template_text:
            parts.append(template_text)
        if prompt_extra:
            parts.append(prompt_extra)

        prompt = '. '.join(filter(None, parts))

        replacements = {
            '{gender}': gender or '',
            '{age_stage}': age_stage or '',
            '{background}': background or '',
            '{outfit}': outfit or '',
        }
        for key, value in replacements.items():
            prompt = prompt.replace(key, value)

        negative_parts = []
        if active_prompt and active_prompt.negative_prompt:
            negative_parts.append(active_prompt.negative_prompt)
        if template and template.negative_prompt:
            negative_parts.append(template.negative_prompt)
        negative_prompt = ', '.join(filter(None, negative_parts))

        return prompt, negative_prompt

    def _photomaker_style(self, template):
        """Map template theme/background to a PhotoMaker style name when possible."""
        if not template:
            return 'Photographic (Default)'
        theme = (template.theme or '').lower()
        style_map = {
            'cinematic': 'Cinematic',
            'disney': 'Disney Charactor',
            'digital art': 'Digital Art',
            'photographic': 'Photographic (Default)',
            'fantasy': 'Fantasy art',
            'neonpunk': 'Neonpunk',
            'enhance': 'Enhance',
            'comic': 'Comic book',
            'lowpoly': 'Lowpoly',
            'line art': 'Line art',
        }
        for key, value in style_map.items():
            if key in theme:
                return value
        return 'Photographic (Default)'

    def generate_baby(self, baby_image, father_photo_url, mother_photo_url, gender=None, prompt_extra=''):
        template = baby_image.generation_template

        prompt_text, negative_prompt = self.build_prompt(
            baby_image=baby_image,
            gender=gender,
            age_stage=baby_image.age_stage,
            background=baby_image.background,
            outfit=baby_image.outfit,
            template=template,
            prompt_extra=prompt_extra,
        )

        baby_image.generation_prompt_text = prompt_text
        baby_image.save(update_fields=['generation_prompt_text'])

        # PhotoMaker expects the trigger word "img" somewhere in the prompt.
        if ' img' not in prompt_text.lower():
            prompt_text = f'{prompt_text} img'

        base_negative = BASE_QUALITY_NEGATIVE
        age_negative = AGE_DRIFT_NEGATIVE
        composition_negative = ', '.join(filter(None, [MULTIPLE_PEOPLE_NEGATIVE, FULL_BODY_NEGATIVE]))
        merged_negative = ', '.join(
            filter(None, [negative_prompt, age_negative, composition_negative, base_negative])
        )

        input_data = {
            'input_image': father_photo_url,
            'input_image2': mother_photo_url,
            'prompt': prompt_text,
            'negative_prompt': merged_negative,
            'num_steps': 20,
            'num_outputs': 1,
            'style_name': self._photomaker_style(template),
            'disable_safety_checker': True,
        }

        prediction = self._create_prediction_with_retry(input_data)
        return prediction

    def _create_prediction_with_retry(self, input_data, max_attempts=5, base_delay=4):
        """Create a Replicate prediction, retrying on 429 rate limits.

        Free/low-credit Replicate accounts throttle creation to a burst of ~1
        concurrent prediction — timeline bursts fail with 429. We back off and
        retry until the throttle resets instead of failing the generation."""
        import time

        attempt = 0
        while True:
            try:
                return self.client.predictions.create(
                    version=self.version,
                    input=input_data,
                )
            except Exception as e:
                is_429 = getattr(e, 'status', None) == 429 or '429' in str(e) or 'throttled' in str(e).lower()
                attempt += 1
                if not is_429 or attempt >= max_attempts:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                import random
                time.sleep(delay + random.uniform(0, 2))

    def get_prediction_result(self, prediction_id):
        prediction = self.client.predictions.get(prediction_id)
        return prediction

    def wait_for_prediction(self, prediction, timeout=300, poll_interval=1):
        """Poll Replicate until the prediction completes or fails."""
        import time
        terminal_statuses = {'succeeded', 'failed', 'canceled'}
        elapsed = 0
        while prediction.status not in terminal_statuses and elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval
            prediction = self.client.predictions.get(prediction.id)
        return prediction
