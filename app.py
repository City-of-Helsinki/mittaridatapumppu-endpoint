import importlib
import logging
import os
import pprint
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fvhiot.utils import init_script
from fvhiot.utils.aiokafka import (get_aiokafka_producer_by_envs,
                                   on_send_error, on_send_success)
from fvhiot.utils.data import data_pack
from fvhiot.utils.http.starlettetools import \
    extract_data_from_starlette_request
from sentry_asgi import SentryMiddleware

from endpoints import AsyncRequestHandler as RequestHandler

app_producer = None
app_endpoints = {}
init_script()

# TODO: for testing, add better defaults (or remove completely to make sure it is set in env)
ENDPOINT_CONFIG_URL = os.getenv(
    "ENDPOINT_CONFIG_URL", "http://127.0.0.1:8000/api/v1/hosts/localhost/"
)
DEVICE_REGISTRY_TOKEN = os.getenv(
    "DEVICE_REGISTRY_TOKEN", "abcdef1234567890abcdef1234567890abcdef12"
)

device_registry_request_headers = {
    "Authorization": f"Token {DEVICE_REGISTRY_TOKEN}",
    "User-Agent": "mittaridatapumppu-endpoint/0.1.0",
    "Accept": "application/json",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Get endpoints from Device registry and create KafkaProducer .
    # TODO: Test external connections here, e.g. device registry, redis etc. and crash if some mandatory
    # service is missing.
    global app_endpoints
    global app_producer
    endpoints = await get_endpoints_from_device_registry(True)
    logging.debug("\n" + pprint.pformat(endpoints))
    if endpoints:
        app_endpoints = endpoints
    try:
        app_producer = await get_aiokafka_producer_by_envs()
    except Exception as e:
        logging.error(f"Failed to create KafkaProducer: {e}")
        app_producer = None
    logging.info(
        "Ready to go, listening to endpoints: {}".format(
            ", ".join(endpoints.keys())
        )
    )
    yield

    # Close KafkaProducer and other connections.
    logging.info("Shutdown, close connections")
    if app_producer:
        await app_producer.stop()


app = FastAPI(lifespan=lifespan)
app.add_middleware(SentryMiddleware)


def get_full_path(request: Request) -> str:
    """Make sure there is always exactly one leading slash in path."""
    return "/" + request.path_params["full_path"].lstrip("/")


async def get_endpoints_from_device_registry(fail_on_error: bool) -> dict:
    """
    Update endpoints from device registry. This is done on startup and when device registry is updated.
    """
    endpoints = {}
    # Create request to ENDPOINTS_URL and get data using httpx
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                ENDPOINT_CONFIG_URL, headers=device_registry_request_headers
            )
            if response.status_code == 200:
                data = response.json()
                logging.info(
                    f"Got {len(data['endpoints'])} endpoints from device registry {ENDPOINT_CONFIG_URL}"
                )
            else:
                logging.error(
                    f"Failed to get endpoints from device registry {ENDPOINT_CONFIG_URL}"
                )
                return endpoints
        except Exception as e:
            logging.error(
                f"Failed to get endpoints from device registry {ENDPOINT_CONFIG_URL}: {e}"
            )
            if fail_on_error:
                raise e
    for endpoint in data["endpoints"]:
        # Import requesthandler module. It must exist in python path.
        try:
            request_handler_module = importlib.import_module(
                endpoint["http_request_handler"]
            )
            request_handler_function: RequestHandler = (
                request_handler_module.RequestHandler()
            )
            endpoint["request_handler"] = request_handler_function
            logging.info(f"Imported {endpoint['http_request_handler']}")
        except ImportError as e:
            logging.error(
                f"Failed to import {endpoint['http_request_handler']}: {e}")
        endpoints[endpoint["endpoint_path"]] = endpoint
    return endpoints


@app.get("/")
async def root(_request: Request) -> Response:
    return JSONResponse({"message": "Test ok"})


@app.get("/notify")
async def notify(_request: Request) -> Response:
    global app_endpoints
    endpoints = await get_endpoints_from_device_registry(False)
    logging.debug("Got endpoints:\n" + pprint.pformat(endpoints))
    endpoint_count = len(endpoints)
    if endpoints:
        logging.info(
            f"Got {endpoint_count} endpoints from device registry in notify")
        app_endpoints = endpoints
    return PlainTextResponse(f"OK ({endpoint_count})")


@app.get("/readiness")
@app.head("/readiness")
async def readiness(_request: Request) -> Response:
    return PlainTextResponse("OK")


@app.get("/liveness")
@app.head("/liveness")
async def liveness(_request: Request) -> Response:
    return PlainTextResponse("OK")


@app.get("/debug-sentry")
@app.head("/debug-sentry")
async def trigger_error(_request: Request) -> Response:
    _ = 1 / 0
    return PlainTextResponse("Shouldn't reach this")


async def api_v2(request: Request, endpoint: dict) -> Response:
    global app_producer
    request_data = await extract_data_from_starlette_request(
        request
    )  # data validation done here
    # TODO : remove
    # DONE
    # logging.error(request_data)
    if request_data.get("extra"):
        logging.warning(
            f"RequestModel contains extra values: {request_data['extra']}")
    if request_data["request"].get("extra"):
        logging.warning(
            f"RequestData contains extra values: {request_data['request']['extra']}"
        )
    path = request_data["path"]
    (auth_ok, device_id, topic_name, response_message, status_code) = await endpoint[
        "request_handler"
    ].process_request(request_data, endpoint)
    response_message = str(response_message)
    print("REMOVE ME", auth_ok, device_id, topic_name, response_message, status_code)
    # add extracted device id to request data before pushing to kafka raw data topic
    request_data["device_id"] = device_id
    # We assume device data is valid here
    logging.debug(pprint.pformat(request_data))
    if auth_ok and topic_name:
        if app_producer:
            logging.info(f'Sending path "{path}" data to {topic_name}')
            packed_data = data_pack(request_data)
            logging.debug(packed_data[:1000])
            try:
                res = await app_producer.send_and_wait(topic_name, value=packed_data)
                on_send_success(res)
            except Exception as e:
                on_send_error(e)
        else:
            logging.error(
                f'Failed to send "{path}" data to {topic_name}, producer was not initialised even we had a topic name'
            )
            # Endpoint process has failed and no data was sent to Kafka. This is a fatal error.
            response_message, status_code = (
                "Internal server error, see logs for details",
                500,
            )
    else:
        logging.info("No action: topic_name is not defined")

    return PlainTextResponse(response_message, status_code=status_code or 200)


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "HEAD", "DELETE", "PATCH"])
async def catch_all(request: Request) -> Response:
    """Catch all requests (except static paths) and route them to correct request handlers."""
    global app_endpoints
    full_path = get_full_path(request)
    # print(full_path, app_endpoints.keys())
    if full_path in app_endpoints:
        endpoint = app_endpoints[full_path]
        response = await api_v2(request, endpoint)
        return response
    else:  # return 404
        return PlainTextResponse("Not found: " + full_path, status_code=404)


# This part is for debugging / PyCharm debugger
# See https://fastapi.tiangolo.com/tutorial/debugging/
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
