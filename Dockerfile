# mittaridatapumppu-endpoint

FROM python:3.11-alpine

LABEL org.opencontainers.image.source=https://github.com/city-of-helsinki/mittaridatapumppu
LABEL org.opencontainers.image.description="Mittaridatapumppu Endpoint"
LABEL org.opencontainers.image.licenses="Apache License 2.0"

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Device registry config
ENV DEVREG_ENDPOINTS_URL "http://devreg:8000/api/v1/hosts/localhost/"
ENV DEVREG_API_TOKEN "abcdef1234567890abcdef1234567890abcdef12"

# Kafka config
ENV KAFKA_BOOTSTRAP_SERVERS "kafka:9092"

RUN addgroup -S app && adduser -S app -G app
WORKDIR /home/app

# Copy and install requirements only first to cache the dependency layer
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir --no-compile --upgrade -r requirements.txt

COPY --chown=app:app . .

# Support Arbitrary User IDs
RUN chgrp -R 0 /home/app && \
  chmod -R g+rwX /home/app

USER app

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
EXPOSE 8000/tcp
