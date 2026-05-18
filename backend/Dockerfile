FROM python:3.12-slim

ARG BUILD_ENV=production

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN if [ "$BUILD_ENV" = "development" ]; then \
        pip install --no-cache-dir -r requirements/development.txt; \
    else \
        pip install --no-cache-dir -r requirements/base.txt; \
    fi

RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

COPY . .

# جمع ملفّات الـ static (لـ admin css + أي assets) — WhiteNoise يقدّمها.
# نُمرّر SECRET_KEY وهمي لأن collectstatic يقرأ الإعدادات.
RUN SECRET_KEY=build-time-only \
    DEBUG=False \
    ALLOWED_HOSTS=localhost \
    DB_HOST=localhost DB_NAME=x DB_USER=x DB_PASSWORD=x \
    python manage.py collectstatic --noinput || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
