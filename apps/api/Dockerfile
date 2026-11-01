# KarenBot API — production image (Railway/Render/Fly all accept this).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install .

# Run migrations, then serve. $PORT is injected by the platform.
CMD ["sh", "-c", "alembic upgrade head && uvicorn karenbot.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
