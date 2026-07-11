from django.contrib import admin
from .models import BabyImage


@admin.register(BabyImage)
class BabyImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'generation_type', 'generation_status', 'created_at')
    list_filter = ('generation_type', 'generation_status', 'is_favorite', 'is_deleted')
    search_fields = ('user__email',)
