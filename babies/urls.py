from django.urls import path
from .views import (
    GenerateBabyView, GenerateBabyWithOptionsView,
    ChangeAgeView, ChangeOutfitView, GenerateHighResView,
    GenerateTimelineView, BabyImageStatusView, BabyImageListView,
    ToggleFavoriteView,
)

urlpatterns = [
    path('generate/', GenerateBabyView.as_view(), name='generate-baby'),
    path('generate-with-options/', GenerateBabyWithOptionsView.as_view(), name='generate-with-options'),
    path('generate-timeline/', GenerateTimelineView.as_view(), name='generate-timeline'),
    path('', BabyImageListView.as_view(), name='baby-image-list'),
    path('<uuid:pk>/status/', BabyImageStatusView.as_view(), name='baby-status'),
    path('<uuid:pk>/change-age/', ChangeAgeView.as_view(), name='change-age'),
    path('<uuid:pk>/change-outfit/', ChangeOutfitView.as_view(), name='change-outfit'),
    path('<uuid:pk>/generate-high-res/', GenerateHighResView.as_view(), name='generate-high-res'),
    path('<uuid:pk>/favorite/', ToggleFavoriteView.as_view(), name='toggle-favorite'),
]
