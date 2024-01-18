# mittaridatapumppu-endpoint

FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN addgroup -S app && adduser -S app -G app
WORKDIR /home/app

# Install requirements to build aiokafka
RUN apk add --no-cache \
  gcc \
  python3-dev \
  libc-dev \
  zlib-dev

# Copy and install requirements only first to cache the dependency layer
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir --no-compile --upgrade -r requirements.txt

COPY --chown=app:app . .

# Support Arbitrary User IDs
RUN chgrp -R 0 /home/app && \
  chmod -R g+rwX /home/app

USER app

HEALTHCHECK CMD wget --no-verbose --tries=1 --spider localhost:8000/healthz || exit
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
EXPOSE 8000/tcp
