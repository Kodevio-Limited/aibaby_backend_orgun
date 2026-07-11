from rest_framework import serializers
from .models import BabyImage


class BabyImageGenerateSerializer(serializers.Serializer):
    father_photo = serializers.ImageField()
    mother_photo = serializers.ImageField()

    def validate_father_photo(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Image must be under 10MB.')
        return value

    def validate_mother_photo(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Image must be under 10MB.')
        return value


class BabyImageGenerateWithOptionsSerializer(serializers.Serializer):
    father_photo = serializers.ImageField()
    mother_photo = serializers.ImageField()
    gender = serializers.ChoiceField(choices=['boy', 'girl', 'twins'])
    age_stage = serializers.ChoiceField(choices=['newborn', '3m', '6m', '1y'])
    background = serializers.ChoiceField(choices=['studio', 'home', 'nature'])

    def validate_father_photo(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Image must be under 10MB.')
        return value

    def validate_mother_photo(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Image must be under 10MB.')
        return value


class ChangeAgeSerializer(serializers.Serializer):
    age_stage = serializers.ChoiceField(choices=['newborn', '3m', '6m', '1y'])


class ChangeOutfitSerializer(serializers.Serializer):
    outfit = serializers.CharField(max_length=50)


class GenerateTimelineSerializer(serializers.Serializer):
    father_photo = serializers.ImageField()
    mother_photo = serializers.ImageField()
    timeline = serializers.ChoiceField(choices=['newborn', '3m', '6m', '1y'])

    def validate_father_photo(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Image must be under 10MB.')
        return value

    def validate_mother_photo(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Image must be under 10MB.')
        return value


class BabyImageOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = BabyImage
        fields = [
            'id', 'generation_type', 'generation_status', 'generated_image',
            'gender', 'age_stage', 'background', 'outfit', 'timeline',
            'eyes_similarity', 'face_shape_similarity', 'skin_tone_similarity',
            'error_message', 'is_favorite', 'created_at', 'updated_at',
        ]


class BabyImageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BabyImage
        fields = [
            'id', 'generation_type', 'generation_status', 'generated_image',
            'gender', 'age_stage', 'eyes_similarity', 'face_shape_similarity',
            'skin_tone_similarity', 'is_favorite', 'created_at',
        ]
