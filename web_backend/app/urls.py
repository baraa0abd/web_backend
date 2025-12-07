from django.urls import path
from .views import OCRExtractView, OllamaHealthView

urlpatterns = [
    path("ocr/extract/", OCRExtractView.as_view(), name="ocr-extract"),
    path("ollama/health/", OllamaHealthView.as_view(), name="ollama-health"),
]
