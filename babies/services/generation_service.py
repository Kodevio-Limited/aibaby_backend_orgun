from django.conf import settings

REPLICATE_BABY_MODEL = 'smoosh-sh/baby-mystic'
REPLICATE_BABY_VERSION = 'ba5ab694a9df055fa469e55eeab162cc288039da0abd8b19d956980cc3b49f6d'
REPLICATE_BABY_PROVIDER = 'replicate:smoosh-sh/baby-mystic'


class GenerationService:
    def __init__(self):
        import replicate
        self.client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)

    def _get_active_prompt(self):
        from ..models import GenerationPrompt
        return GenerationPrompt.objects.filter(status='active').order_by('-created_at').first()

    def build_prompt(self, baby_image=None, gender=None, age_stage=None, background=None, outfit=None, template=None, prompt_extra=''):
        """Assemble the final prompt text from the active admin prompt + user-selected template.

        NOTE: the current Replicate model (smoosh-sh/baby-mystic) does not accept a prompt
        string input. The assembled text is stored on BabyImage.generation_prompt_text for
        auditing and will be passed to any future model that supports a prompt parameter.
        """
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

        # Replace placeholders with generation parameters if present.
        replacements = {
            '{gender}': gender or '',
            '{age_stage}': age_stage or '',
            '{background}': background or '',
            '{outfit}': outfit or '',
        }
        for key, value in replacements.items():
            prompt = prompt.replace(key, value)

        # Build negative prompt similarly.
        negative_parts = []
        if active_prompt and active_prompt.negative_prompt:
            negative_parts.append(active_prompt.negative_prompt)
        if template and template.negative_prompt:
            negative_parts.append(template.negative_prompt)
        negative_prompt = ', '.join(filter(None, negative_parts))

        return prompt, negative_prompt

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

        input_data = {
            'image': father_photo_url,
            'image2': mother_photo_url,
        }
        if gender in ('boy', 'girl'):
            input_data['gender'] = gender

        if template:
            if template.seed is not None:
                input_data['seed'] = template.seed
            if template.high_quality_rendering:
                input_data['steps'] = 50
            elif template.enhance_lighting:
                input_data['steps'] = 35

        # The current model does not support prompt/negative_prompt inputs, so we do not
        # include them in the request. They are stored on the BabyImage record for audit.
        # input_data['prompt'] = prompt_text
        # input_data['negative_prompt'] = negative_prompt

        prediction = self.client.predictions.create(
            version=REPLICATE_BABY_VERSION,
            input=input_data,
        )
        return prediction

    def get_prediction_result(self, prediction_id):
        prediction = self.client.predictions.get(prediction_id)
        return prediction
