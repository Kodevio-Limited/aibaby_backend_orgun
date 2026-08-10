from django.conf import settings

REPLICATE_BABY_MODEL = 'smoosh-sh/baby-mystic'
REPLICATE_BABY_VERSION = 'ba5ab694a9df055fa469e55eeab162cc288039da0abd8b19d956980cc3b49f6d'
REPLICATE_BABY_PROVIDER = 'replicate:smoosh-sh/baby-mystic'


class GenerationService:
    def __init__(self):
        import replicate
        self.client = replicate.Client(api_token=settings.REPLICATE_API_TOKEN)

    def build_prompt(self, gender=None, age_stage=None, background=None, outfit=None):
        parts = ['a realistic photo of a baby, natural lighting']

        if gender == 'boy':
            parts.insert(0, 'baby boy')
        elif gender == 'girl':
            parts.insert(0, 'baby girl')
        elif gender == 'twins':
            parts.insert(0, 'twin babies')

        if age_stage == 'newborn':
            parts.append('newborn baby')
        elif age_stage == '3m':
            parts.append('3 month old baby')
        elif age_stage == '6m':
            parts.append('6 month old baby')
        elif age_stage == '1y':
            parts.append('1 year old baby')

        if background == 'studio':
            parts.append('studio background')
        elif background == 'home':
            parts.append('at home')
        elif background == 'nature':
            parts.append('outdoors in nature')

        if outfit:
            parts.append(f'wearing {outfit}')

        return ', '.join(parts)

    def generate_baby(self, father_photo_url, mother_photo_url, gender=None, prompt_extra=''):
        input_data = {
            'image': father_photo_url,
            'image2': mother_photo_url,
        }
        if gender in ('boy', 'girl'):
            input_data['gender'] = gender

        prediction = self.client.predictions.create(
            version=REPLICATE_BABY_VERSION,
            input=input_data,
        )
        return prediction

    def get_prediction_result(self, prediction_id):
        prediction = self.client.predictions.get(prediction_id)
        return prediction
