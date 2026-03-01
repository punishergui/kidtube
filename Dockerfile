FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG APP_UID=10001
ARG APP_GID=10001

RUN groupadd --gid ${APP_GID} kidtube && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin kidtube

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip install --upgrade pip && pip install .

RUN mkdir -p /data /app/app/static/uploads /app/static/uploads/kids \
    && chown -R kidtube:kidtube /app /data \
    && chmod 770 /data

USER kidtube

EXPOSE 2018

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:2018/health', timeout=3)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-2018}"]
