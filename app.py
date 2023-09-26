import importlib
import logging
import json
import os
import pprint
import httpx
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import Response, PlainTextResponse, JSONResponse
from fastapi.routing import APIRoute
from sentry_asgi import SentryMiddleware

from endpoints import AsyncRequestHandler as RequestHandler
from fvhiot.utils import init_script
from fvhiot.utils.aiokafka import (
    get_aiokafka_producer_by_envs,
    on_send_success,
    on_send_error,
)
from fvhiot.utils.data import data_pack
from fvhiot.utils.http.starlettetools import extract_data_from_starlette_request

# TODO: for testing, add better defaults
ENDPOINTS_URL = os.getenv("ENDPOINTS_URL", "http://127.0.0.1:8000/api/v1/hosts/localhost/")
API_TOKEN = os.getenv("API_TOKEN", "abcdef1234567890abcdef1234567890abcdef12")

device_registry_request_headers = {
    "Authorization": f"Token {API_TOKEN}",
    "User-Agent": "mittaridatapumppu-endpoint/0.0.1",
    "Accept": "application/json",
}


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
            response = await client.get(ENDPOINTS_URL, headers=device_registry_request_headers)
            if response.status_code == 200:
                data = response.json()
                logging.info(f"Got {len(data['endpoints'])} endpoints from device registry {ENDPOINTS_URL}")
            else:
                logging.error(f"Failed to get endpoints from device registry {ENDPOINTS_URL}")
                return endpoints
        except Exception as e:
            logging.error(f"Failed to get endpoints from device registry {ENDPOINTS_URL}: {e} ERSKA")
            if fail_on_error:
                raise e
    for endpoint in data["endpoints"]:
        # Import requesthandler module. It must exist in python path.
        try:
            request_handler_module = importlib.import_module(endpoint["http_request_handler"])
            request_handler_function: RequestHandler = request_handler_module.RequestHandler()
            endpoint["request_handler"] = request_handler_function
            logging.info(f"Imported {endpoint['http_request_handler']}")
        except ImportError as e:
            logging.error(f"Failed to import {endpoint['http_request_handler']}: {e}")
        endpoints[endpoint["endpoint_path"]] = endpoint
    return endpoints


async def root(_request: Request) -> Response:
    return JSONResponse({"message": "Test ok"})


async def notify(_request: Request) -> Response:
    global app
    endpoints = await get_endpoints_from_device_registry(False)
    logging.debug("Got endpoints:\n" + pprint.pformat(endpoints))
    endpoint_count = len(endpoints)
    if endpoints:
        logging.info(f"Got {endpoint_count} endpoints from device registry in notify")
        app.endpoints = endpoints
    return PlainTextResponse(f"OK ({endpoint_count})")


async def readiness(_request: Request) -> Response:
    return PlainTextResponse("OK")


async def healthz(_request: Request) -> Response:
    return PlainTextResponse("OK")


async def trigger_error(_request: Request) -> Response:
    _ = 1 / 0
    return PlainTextResponse("Shouldn't reach this")


async def api_v2(request: Request, endpoint: dict) -> Response:
    request_data = await extract_data_from_starlette_request(request)  # data validation done here
    # TODO : remove
    logging.error(request_data)
    if request_data.get("extra"):
        logging.warning(f"RequestModel contains extra values: {request_data['extra']}")
    if request_data["request"].get("extra"):
        logging.warning(f"RequestData contains extra values: {request_data['request']['extra']}")
    path = request_data["path"]
    (auth_ok, device_id, topic_name, response_message, status_code) = await endpoint["request_handler"].process_request(
        request_data, endpoint
    )
    response_message = str(response_message)
    print("REMOVE ME", auth_ok, device_id, topic_name, response_message, status_code)
    # We assume device data is valid here
    logging.debug(pprint.pformat(request_data))
    if topic_name:
        if app.producer:
            logging.info(f'Sending path "{path}" data to {topic_name}')
            packed_data = data_pack(request_data)
            logging.debug(packed_data[:1000])
            try:
                res = await app.producer.send_and_wait(topic_name, value=packed_data)
                on_send_success(res)
            except Exception as e:
                on_send_error(e)
        else:
            logging.error(
                f'Failed to send "{path}" data to {topic_name}, producer was not initialised even we had a topic name'
            )
            # Endpoint process has failed and no data was sent to Kafka. This is a fatal error.
            response_message, status_code = "Internal server error, see logs for details", 500
    else:
        logging.info("No action: topic_name is not defined")

    return PlainTextResponse(response_message, status_code=status_code or 200)


async def catch_all(request: Request) -> Response:
    """Catch all requests (except static paths) and route them to correct request handlers."""
    full_path = get_full_path(request)
    # print(full_path, app.endpoints.keys())
    if full_path in app.endpoints:
        endpoint = app.endpoints[full_path]
        response = await api_v2(request, endpoint)
        return response
    else:  # return 404
        return PlainTextResponse("Not found: " + full_path, status_code=404)


async def startup():
    """
    Get endpoints from Device registry and create KafkaProducer .
    TODO: Test external connections here, e.g. device registry, redis etc. and crash if some mandatory
    service is missing.
    """
    global app
    endpoints = await get_endpoints_from_device_registry(True)
    logging.debug("\n" + pprint.pformat(endpoints))
    if endpoints:
        app.endpoints = endpoints
    try:
        app.producer = await get_aiokafka_producer_by_envs()
    except Exception as e:
        logging.error(f"Failed to create KafkaProducer: {e}")
        app.producer = None
    logging.info("Ready to go, listening to endpoints: {}".format(", ".join(app.endpoints.keys())))


async def shutdown():
    """
    Close KafkaProducer and other connections.
    """
    global app
    logging.info("Shutdown, close connections")
    if app.producer:
        await app.producer.stop()


routes = [
    APIRoute("/", endpoint=root),
    APIRoute("/notify", endpoint=notify, methods=["GET"]),
    APIRoute("/readiness", endpoint=readiness, methods=["GET", "HEAD"]),
    APIRoute("/healthz", endpoint=healthz, methods=["GET", "HEAD"]),
    APIRoute("/debug-sentry", endpoint=trigger_error, methods=["GET", "HEAD"]),
    APIRoute("/{full_path:path}", endpoint=catch_all, methods=["HEAD", "GET", "POST", "PUT", "PATCH", "DELETE"]),
]


init_script()
debug = True if os.getenv("DEBUG") else False
app = FastAPI(debug=debug, routes=routes, on_startup=[startup], on_shutdown=[shutdown])
app.producer = None
app.endpoints = {}
app.add_middleware(SentryMiddleware)

# This part is for debugging / PyCharm debugger
# See https://fastapi.tiangolo.com/tutorial/debugging/
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
