import logging
from pprint import pprint
from typing import Tuple, Union

from .. import AsyncRequestHandler, is_ip_address_allowed


class RequestHandler(AsyncRequestHandler):
    @staticmethod
    async def validate(request_data: dict, endpoint_data: dict) -> Tuple[bool, Union[str, None], Union[int, None]]:
        """
        Use Starlette request_data and endpoint_data from the Device registry here to determine
        should we accept or reject this request.

        :param request_data: deserialized Starlette Request
        :param endpoint_data: endpoint data from the Device registry
        :return: (bool ok, str error text, int status code)
        """
        pprint(request_data)
        pprint(endpoint_data)
        # Reject requests not matching the one defined in env
        # Compare request's full path with endpoint's path
        if request_data["path"] != endpoint_data["endpoint_path"]:
            return False, "Not found", 404
        # Reject requests without token parameter, which can be in query string or http header
        api_key = request_data["request"]["get"].get("x-api-key")
        if api_key is None:
            api_key = request_data["request"]["headers"].get("x-api-key")
        if api_key is None or api_key != endpoint_data["auth_token"]:
            logging.warning("Missing or invalid authentication token (x-api-key)")
            return False, "Missing or invalid authentication token, see logs for error", 401
        elif request_data["request"]["get"].get("test") == "true":
            logging.info("Test ok")
            return False, "Test OK", 400
        # Reject requests from unknown IP addresses
        allowed_ip_addresses = endpoint_data.get("allowed_ip_addresses", "")
        if allowed_ip_addresses == "":
            logging.warning("Set 'allowed_ip_addresses' in endpoint settings to restrict requests from unknown sources")
        else:
            if is_ip_address_allowed(request_data, allowed_ip_addresses) is False:
                return False, "IP address not allowed", 403
        return True, None, None

    async def process_request(
        self, request_data: dict, endpoint_data: dict
    ) -> Tuple[bool, str, Union[str, None], Union[str, dict, list], int]:
        """
        Just do minimal validation for request_data and
        return ok if token was valid.
        """
        auth_ok, response_message, status_code = await self.validate(request_data, endpoint_data)
        if auth_ok:
            topic_name = endpoint_data["kafka_raw_data_topic"]
            response_message = "Request OK"
            status_code = 202
        else:
            topic_name = None
        return auth_ok, "unknown_device_id", topic_name, response_message, status_code

    async def get_metadata(self, request_data: dict, device_id: str) -> str:
        metadata = "{}"
        # Get metadata from somewhere here, if needed
        return metadata
