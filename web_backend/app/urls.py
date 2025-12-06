from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UploadImageView, ImageListView, ImageDetailView,
    ExtractedTextDetailView, AccessTokenViewSet, DashboardView
)
from .views_auth import LoginView
router = DefaultRouter()
router.register(r"access-tokens", AccessTokenViewSet, basename="access-token")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("images/upload/", UploadImageView.as_view(), name="image-upload"),
    path("images/", ImageListView.as_view(), name="image-list"),
    path("images/<uuid:id>/", ImageDetailView.as_view(), name="image-detail"),
    path("texts/<uuid:pk>/", ExtractedTextDetailView.as_view(), name="text-detail"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("", include(router.urls)),
]
