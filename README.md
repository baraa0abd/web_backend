# OCR Upload Backend

A Django REST backend that accepts image uploads and extracts text from them using a self-hosted LLaVA model via Ollama. Built for the ITS Vision Hackathon (Computiq, Dec 2025).

## Quick start

```bash
git clone https://github.com/baraa0abd/web_backend.git
cd web_backend
python -m venv venv
venv\Scripts\activate        # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cd web_backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

By default the app expects Ollama on `http://localhost:11434`. Point it elsewhere with:

```bash
export OLLAMA_HOST=http://<ollama-host>:11434
```

## What it does

- **`POST /api/ocr/extract/`** — upload an image (`image` field), get back `extracted_text`, `model_version`, and `tokens_count`.
- **`POST /api/images/upload/`** — upload + persist (`file` field); saves the image and its extracted text as records.
- **`GET /api/ollama/health/`** — checks whether the configured Ollama host is reachable.
- **`POST /api/auth/login/`** — basic login that issues an access token for API use.

## Why it's built this way

- **Deduplication by SHA256** — identical images aren't reprocessed; a repeat upload returns the cached result (or `202` if the first one is still processing).
- **Per-IP rate limiting** — 25 uploads/day/IP, enforced in the view.
- **Defensive Ollama parsing** — `app/utils/ollama_ocr.py` handles timeouts, retries, and several possible response shapes from the model, and always returns a stable `{extracted_text, tokens_count, model_version, raw_response}` dict, even on failure. This was a deliberate choice after hitting `KeyError`s from unexpected Ollama response shapes during the hackathon.
- **Cloudflare Tunnel** was used in the hackathon deployment to expose the local backend securely without opening ports directly.

## Project structure

```
web_backend/
├── web_backend/        # Django project (settings, urls, wsgi/asgi)
└── app/
    ├── models.py        # User, Image, ExtractedText
    ├── views.py         # upload, OCR-only, login, dashboard, Ollama health
    └── utils/
        ├── ollama_ocr.py  # Ollama client: retries, defensive parsing
        └── common.py      # hashing, file storage, client IP, cache helpers
```

## Testing

```bash
curl http://127.0.0.1:8000/api/ollama/health/
curl -F "image=@sample.png" http://127.0.0.1:8000/api/ocr/extract/
```

There's no automated test suite yet — the next useful addition would be unit tests that mock `requests.post` in `ollama_ocr.py` against different response shapes (success, missing keys, non-JSON, error status).

## Known limitations

- Rate limiting is in-process (not Redis-backed), so it resets on restart and doesn't scale across multiple server instances.
- OCR runs synchronously in the request; a real deployment should offload it to a background worker (Celery/RQ) and return `202` immediately.
- No structured logging/metrics on Ollama call success or failure rates yet.

## License

No license file is currently included.
