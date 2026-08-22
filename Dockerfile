FROM python:3.13-slim

# PYTHONUNBUFFERED (không phải PYTHONBUFFERED): log ra stdout ngay, không bị buffer.
# PYTHONDONTWRITEBYTECODE (không phải PYTHONDOTWRITEBYTECODE): không sinh .pyc trong image.
# DJANGO_SETTINGS_MODULE (không phải DJANGO_SETTING_MODULE): manage.py và daphne cùng dùng production.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PORT=10000

WORKDIR /app

# Cài dependency trước khi COPY source để layer pip được cache khi chỉ đổi code.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic chỉ cần SECRET_KEY (không chạy system check, không cần DB/Redis/Cloudinary).
RUN SECRET_KEY=build-only-not-a-secret python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:10000/health/', timeout=4).status==200 else 1)"

# migrate chạy system check (apps/core/checks.py): thiếu DATABASE_URL/REDIS/CLOUDINARY/ALLOWED_HOSTS
# thì container dừng ngay với thông báo rõ ràng. exec để daphne nhận SIGTERM trực tiếp.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec daphne -b 0.0.0.0 -p ${PORT:-10000} config.asgi:application"]
