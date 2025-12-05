# web_backend/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Add your app's API routes
    path("api/", include("app.urls")),
]
