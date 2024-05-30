# syntax=docker/dockerfile:1

ARG PYTHON_VERSION="3.12"
ARG ALPINE_VERSION="3.19"

FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} as build

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

# Install requirements to build aiokafka
RUN --mount=type=cache,target=/var/cache/apk \
  apk add gcc python3-dev libc-dev zlib-dev

# Copy and install requirements only first to cache the dependency layer
RUN pip install uv

COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
uv venv $VIRTUAL_ENV && \
uv pip install -r pyproject.toml

FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

RUN addgroup -S app && adduser -S app -G app
WORKDIR /home/app

COPY --from=build --chown=app:app $VIRTUAL_ENV $VIRTUAL_ENV
COPY --chown=app:app endpoint/ ./endpoint
COPY --chown=app:app endpoints/ ./endpoints

# Support Arbitrary User IDs
RUN chgrp -R 0 /home/app && \
  chmod -R g+rwX /home/app

USER app

EXPOSE 8000/tcp
CMD ["uvicorn", "endpoint.endpoint:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
