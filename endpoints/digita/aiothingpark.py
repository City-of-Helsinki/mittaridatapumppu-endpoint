import logging
import os
from typing import Tuple, Union

from .. import AsyncRequestHandler, is_ip_address_allowed


class RequestHandler(AsyncRequestHandler):
    @staticmethod
    async def validate(request_data: dict, endpoint_data: dict) -> Tuple[bool, Union[str, None], Union[int, None]]:
        """
        Use Starlette request_data here to determine should we accept or reject
        this request
        :param request_data: deserialized (FastAPI) Starlette Request
        :param endpoint_data: endpoint data from device registry
        :return: (bool ok, str error text, int status code)
        """
        # Reject requests not matching the one defined in env
        if request_data["path"] != endpoint_data["endpoint_path"]:
            return False, "Not found", 404
        # Reject requests without token parameter, which can be in query string or http header
        api_key = request_data["request"]["get"].get("x-api-key")
        if api_key is None:
            api_key = request_data["request"]["headers"].get("x-api-key")
        if api_key is None or api_key != endpoint_data["auth_token"]:
            logging.warning("Missing or invalid authentication token (x-api-key)")
            return False, "Missing or invalid authentication token, see logs for error", 401
        logging.info("Authentication token validated")
        if request_data["request"]["get"].get("test") == "true":
            logging.info("Test ok")
            return False, "Test OK", 400
        allowed_ip_addresses = endpoint_data.get("allowed_ip_addresses", "")
        if allowed_ip_addresses == "":
            logging.warning("Set 'allowed_ip_addresses' in endpoint settings to restrict requests unknown sources")
        else:
            if is_ip_address_allowed(request_data, allowed_ip_addresses) is False:
                return False, "IP address not allowed", 403

        if request_data["request"]["get"].get("LrnDevEui") is None:
            logging.warning("LrnDevEui not found in request params")
            return False, "Invalid arguments, see logs for error", 400
        else:
            return True, "Request accepted", 202

    async def process_request(
        self,
        request_data: dict,
        endpoint_data: dict,
    ) -> Tuple[bool, str, Union[str, None], Union[str, dict, list], int]:
        auth_ok, response_message, status_code = await self.validate(request_data, endpoint_data)
        device_id = request_data["request"]["get"].get("LrnDevEui")
        if device_id:  # a LrnDevEui must be present to send the data to Kafka topic
            topic_name = endpoint_data["kafka_raw_data_topic"]
            # topic_name = os.getenv("KAFKA_RAW_DATA_TOPIC_NAME")
        else:
            topic_name = None
        logging.info("Validation: {}, {}, {}".format(auth_ok, response_message, status_code))
        return auth_ok, device_id, topic_name, response_message, status_code

    async def get_metadata(self, request_data: dict, device_id: str) -> str:
        # TODO: put this function to BaseRequestHandler or remove from endpoint
        # (and add to parser)
        metadata = "{}"
        redis_url = os.getenv("REDIS_URL")
        if redis_url is None:
            logging.info("No REDIS_URL defined, querying device metadata failed")
            return metadata
        if device_id is None:
            logging.info("No device_id available, querying device metadata failed")
            return metadata
        if metadata is None:
            return "{}"
        return metadata
