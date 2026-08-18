from django.test import TestCase

from babies.prompt_builder import (
    age_descriptor,
    build_prompt_extra,
    build_context_snapshot,
    outfit_phrase,
    GENDER_DESCRIPTORS,
    BACKGROUND_DESCRIPTORS,
)


class AgeDescriptorTests(TestCase):
    def test_known_stages(self):
        self.assertEqual(age_descriptor('newborn'), 'a newborn baby, just a few days old, tiny infant')
        self.assertEqual(age_descriptor('3m'), 'a 3 month old baby')
        self.assertEqual(age_descriptor('6m'), 'a 6 month old baby')
        self.assertEqual(age_descriptor('1y'), 'a 1 year old baby')

    def test_free_text_years(self):
        self.assertEqual(age_descriptor('5y'), 'a 5 year old child, age exactly 5 years')
        self.assertEqual(age_descriptor('2y'), 'a 2 year old child, age exactly 2 years')

    def test_free_text_months(self):
        self.assertEqual(age_descriptor('18m'), 'a 18 month old baby')

    def test_case_insensitive(self):
        self.assertEqual(age_descriptor('5Y'), 'a 5 year old child, age exactly 5 years')

    def test_empty(self):
        self.assertEqual(age_descriptor(''), '')


class OutfitPhraseTests(TestCase):
    def test_outfit(self):
        self.assertEqual(outfit_phrase('a red dress'), 'wearing a red dress')

    def test_blank(self):
        self.assertEqual(outfit_phrase(''), '')
        self.assertEqual(outfit_phrase(None), '')


class PromptBuilderTests(TestCase):
    class FakeBabyImage:
        gender = 'girl'
        age_stage = '5y'
        background = 'nature'
        outfit = 'a yellow dress'
        timeline = None
        generation_type = 'outfit_change'
        parent_image_id = None

    def test_prompt_extra_contains_all_context(self):
        extra = build_prompt_extra(self.FakeBabyImage())
        self.assertIn(GENDER_DESCRIPTORS['girl'], extra)
        self.assertIn('5 year old child', extra)
        self.assertIn(BACKGROUND_DESCRIPTORS['nature'], extra)
        self.assertIn('wearing a yellow dress', extra)

    def test_context_snapshot(self):
        snapshot = build_context_snapshot(self.FakeBabyImage())
        self.assertEqual(snapshot['age_stage'], '5y')
        self.assertEqual(snapshot['outfit'], 'a yellow dress')
        self.assertIn('5 year old child', snapshot['age_descriptor'])
        self.assertEqual(len(snapshot['segments']), 4)

    def test_prompt_extra_uses_timeline_fallback_for_age(self):
        image = self.FakeBabyImage()
        image.age_stage = None
        image.timeline = '6m'
        extra = build_prompt_extra(image)
        self.assertIn('6 month old baby', extra)