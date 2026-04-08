# FinWise v2.0

FinWise is a Django-based personal finance manager with AI chat, receipt scanning, goals, reports, and gamification.

## Features

- AI chat assistant powered by Google Gemini
- Receipt scanner with AI extraction
- CSV statement upload and categorization
- Savings goals and streak-based gamification
- PDF monthly reports

## Local Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run migrations:

```bash
python manage.py migrate
```

3. Optional: enable real AI responses:

```bash
# Linux/macOS
export GEMINI_API_KEY=your_key_here

# Windows PowerShell
$env:GEMINI_API_KEY="your_key_here"
```

4. Start the app:

```bash
python manage.py runserver
```

5. Open:

```text
http://127.0.0.1:8000/
```

## Tech Stack

- Backend: Django
- AI: Google Gemini API (gemini-2.5-flash)
- Database: SQLite (local), PostgreSQL supported in production via DATABASE_URL
- Static files: WhiteNoise
- Server: Gunicorn

## Free Deployment (Render)

This repository includes [render.yaml](render.yaml) for one-click setup.

1. Push code to GitHub.
2. In Render, choose New +, then Blueprint.
3. Select this repository.
4. Render will create the web service using [render.yaml](render.yaml).
5. Set GEMINI_API_KEY in Render environment variables.
6. Deploy.

### Notes for Render Free Plan

- Free services spin down after inactivity.
- First request after idle can be slow.
- Use PostgreSQL for persistent production data (recommended), or SQLite for quick demos.

## Required Environment Variables

- GEMINI_API_KEY: Gemini API key
- DJANGO_SECRET_KEY: generated automatically by Render via render.yaml
- DJANGO_DEBUG: False in production
- DJANGO_ALLOWED_HOSTS: includes .onrender.com
- DJANGO_CSRF_TRUSTED_ORIGINS: includes https://*.onrender.com
- DATABASE_URL: optional, required when using PostgreSQL
