from django.urls import path
from .views import OCRExtractView

urlpatterns = [
    path("ocr/extract/", OCRExtractView.as_view(), name="ocr-extract"),
]
