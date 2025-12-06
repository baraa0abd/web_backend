from django.contrib import admin
from django.urls import path, include
from app.views import LoginView, UploadImageView, DashboardView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login/", LoginView.as_view()),
    path("api/images/upload/", UploadImageView.as_view()),
    path("api/dashboard/", DashboardView.as_view()),
    path("api/", include("app.urls")),

]
