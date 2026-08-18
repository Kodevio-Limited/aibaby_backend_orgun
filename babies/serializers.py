from rest_framework import serializers
from .models import BabyImage, ParentPhotoScan, GenerationPrompt, GenerationTemplate, SafetySettings


class ParentPhotoScanUploadSerializer(serializers.Serializer):
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


class ParentPhotoScanOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentPhotoScan
        fields = [
            'id', 'father_photo', 'mother_photo',
            'father_scan_status', 'mother_scan_status',
            'overall_status', 'scan_result', 'confidence',
            'reason', 'moderator_notes',
            'created_at', 'updated_at',
        ]


class ParentPhotoScanAdminOutputSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    thumbnail = serializers.SerializerMethodField()
    upload_time = serializers.DateTimeField(source='created_at', read_only=True)
    status = serializers.CharField(source='overall_status', read_only=True)

    class Meta:
        model = ParentPhotoScan
        fields = [
            'id', 'user_id', 'user_name', 'user_email', 'thumbnail', 'upload_time',
            'father_scan_status', 'mother_scan_status', 'overall_status',
            'scan_result', 'confidence', 'status', 'reason', 'moderator_notes',
            'father_scan_details', 'mother_scan_details',
            'created_at', 'updated_at',
        ]

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.father_photo and request:
            return request.build_absolute_uri(obj.father_photo.url)
        return ''


class BabyImageGenerateSerializer(serializers.Serializer):
    parent_photo_scan_id = serializers.UUIDField()
    template_id = serializers.UUIDField(required=False, allow_null=True)


class BabyImageGenerateWithOptionsSerializer(serializers.Serializer):
    parent_photo_scan_id = serializers.UUIDField()
    template_id = serializers.UUIDField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=['boy', 'girl', 'twins'])
    age_stage = serializers.CharField(max_length=20)
    background = serializers.ChoiceField(choices=['studio', 'home', 'nature'])


class ChangeAgeSerializer(serializers.Serializer):
    age_stage = serializers.CharField(max_length=20)


class ChangeOutfitSerializer(serializers.Serializer):
    outfit = serializers.CharField(max_length=50)


class GenerateTimelineSerializer(serializers.Serializer):
    parent_photo_scan_id = serializers.UUIDField()
    template_id = serializers.UUIDField(required=False, allow_null=True)
    timeline = serializers.ChoiceField(choices=['newborn', '3m', '6m', '1y'])


class BabyImageOutputSerializer(serializers.ModelSerializer):
    generation_prompt_text = serializers.CharField(read_only=True)

    class Meta:
        model = BabyImage
        fields = [
            'id', 'generation_type', 'generation_status', 'generated_image',
            'gender', 'age_stage', 'background', 'outfit', 'timeline',
            'eyes_similarity', 'face_shape_similarity', 'skin_tone_similarity',
            'error_message', 'is_favorite', 'generation_prompt_text',
            'created_at', 'updated_at',
        ]


class BabyImageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BabyImage
        fields = [
            'id', 'generation_type', 'generation_status', 'generated_image',
            'gender', 'age_stage', 'eyes_similarity', 'face_shape_similarity',
            'skin_tone_similarity', 'is_favorite', 'created_at',
        ]


class GenerationPromptOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationPrompt
        fields = [
            'id', 'title', 'description', 'content', 'negative_prompt', 'variables',
            'category', 'status', 'created_at', 'updated_at',
        ]


class GenerationPromptInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationPrompt
        fields = [
            'title', 'description', 'content', 'negative_prompt', 'variables',
            'category', 'status',
        ]


class GenerationTemplateOutputSerializer(serializers.ModelSerializer):
    background = serializers.ImageField(use_url=True, read_only=True)

    class Meta:
        model = GenerationTemplate
        fields = [
            'id', 'name', 'description', 'category', 'background', 'theme',
            'background_type', 'ai_prompt', 'maintain_face_identity',
            'keep_original_gender', 'keep_original_age', 'enhance_lighting',
            'high_quality_rendering', 'allow_background_blur', 'prompt_weight',
            'negative_prompt', 'seed', 'status', 'order', 'created_at', 'updated_at',
        ]


class GenerationTemplateInputSerializer(serializers.ModelSerializer):
    background = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = GenerationTemplate
        fields = [
            'name', 'description', 'category', 'background', 'theme',
            'background_type', 'ai_prompt', 'maintain_face_identity',
            'keep_original_gender', 'keep_original_age', 'enhance_lighting',
            'high_quality_rendering', 'allow_background_blur', 'prompt_weight',
            'negative_prompt', 'seed', 'status', 'order',
        ]


class GenerationTemplateListSerializer(serializers.ModelSerializer):
    background = serializers.ImageField(use_url=True, read_only=True)

    class Meta:
        model = GenerationTemplate
        fields = [
            'id', 'name', 'description', 'category', 'background', 'theme',
            'background_type', 'status', 'order', 'created_at',
        ]


class SafetySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetySettings
        fields = [
            'enable_ai_scanning', 'enable_face_detection', 'enable_nsfw_detection',
            'enable_duplicate_detection', 'enable_watermark_detection',
            'enable_identity_matching', 'minimum_confidence', 'auto_reject',
            'manual_review', 'max_upload_size', 'allowed_image_types',
            'blocked_words', 'blocked_prompt_list', 'negative_prompt_settings',
            'updated_at',
        ]
