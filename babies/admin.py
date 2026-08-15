from django.contrib import admin
from django import forms
from .models import BabyImage, GenerationPrompt, GenerationTemplate, ParentPhotoScan, SafetySettings


@admin.register(BabyImage)
class BabyImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'generation_type', 'generation_status', 'created_at')
    list_filter = ('generation_type', 'generation_status', 'is_favorite', 'is_deleted')
    search_fields = ('user__email',)


@admin.register(GenerationPrompt)
class GenerationPromptAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'updated_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'content')
    actions = ['set_active']

    @admin.action(description='Set selected prompts as active')
    def set_active(self, request, queryset):
        queryset.update(status='active')


@admin.register(GenerationTemplate)
class GenerationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'status', 'order', 'updated_at')
    list_filter = ('status', 'category')
    search_fields = ('name', 'ai_prompt')
    actions = ['set_active']

    @admin.action(description='Set selected templates as active')
    def set_active(self, request, queryset):
        queryset.update(status='active')


@admin.register(ParentPhotoScan)
class ParentPhotoScanAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'overall_status', 'scan_result', 'created_at')
    list_filter = ('overall_status', 'father_scan_status', 'mother_scan_status')
    search_fields = ('user__email',)
    readonly_fields = ('father_scan_details', 'mother_scan_details')
    actions = ['reset_scan', 'rescan']

    @admin.action(description='Reset selected scans (delete photos, clear results)')
    def reset_scan(self, request, queryset):
        from .services.parent_photo_scan_service import ParentPhotoScanService
        service = ParentPhotoScanService(user=request.user)
        for scan in queryset:
            service.reset_scan(scan.id)

    @admin.action(description='Re-scan selected photos')
    def rescan(self, request, queryset):
        from .services.parent_photo_scan_service import ParentPhotoScanService
        service = ParentPhotoScanService(user=request.user)
        for scan in queryset:
            service.rescan(scan.id)


@admin.register(SafetySettings)
class SafetySettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
