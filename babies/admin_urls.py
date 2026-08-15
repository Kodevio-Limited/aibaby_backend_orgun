from django.urls import path
from .admin_views import (
    AdminGenerationPromptListView, AdminGenerationPromptDetailView, AdminGenerationPromptDuplicateView,
    AdminGenerationTemplateListView, AdminGenerationTemplateDetailView, AdminGenerationTemplateDuplicateView,
    AdminParentPhotoScanListView, AdminParentPhotoScanDetailView,
    AdminParentPhotoScanResetView, AdminParentPhotoScanRescanView,
    AdminModerationStatsView, AdminSafetySettingsView,
)

urlpatterns = [
    path('prompts/', AdminGenerationPromptListView.as_view(), name='admin-prompt-list'),
    path('prompts/<uuid:pk>/', AdminGenerationPromptDetailView.as_view(), name='admin-prompt-detail'),
    path('prompts/<uuid:pk>/duplicate/', AdminGenerationPromptDuplicateView.as_view(), name='admin-prompt-duplicate'),

    path('templates/', AdminGenerationTemplateListView.as_view(), name='admin-template-list'),
    path('templates/<uuid:pk>/', AdminGenerationTemplateDetailView.as_view(), name='admin-template-detail'),
    path('templates/<uuid:pk>/duplicate/', AdminGenerationTemplateDuplicateView.as_view(), name='admin-template-duplicate'),

    path('moderation/', AdminParentPhotoScanListView.as_view(), name='admin-moderation-list'),
    path('moderation/stats/', AdminModerationStatsView.as_view(), name='admin-moderation-stats'),
    path('moderation/settings/', AdminSafetySettingsView.as_view(), name='admin-moderation-settings'),
    path('moderation/<uuid:pk>/', AdminParentPhotoScanDetailView.as_view(), name='admin-moderation-detail'),
    path('moderation/<uuid:pk>/reset/', AdminParentPhotoScanResetView.as_view(), name='admin-moderation-reset'),
    path('moderation/<uuid:pk>/rescan/', AdminParentPhotoScanRescanView.as_view(), name='admin-moderation-rescan'),
]
