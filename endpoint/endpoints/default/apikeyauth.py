from pprint import pprint
from typing import Tuple, Union

from .. import AsyncRequestHandler


class RequestHandler(AsyncRequestHandler):
    async def validate(
        self, request_data: dict, endpoint_data: dict
    ) -> Tuple[bool, Union[str, None], Union[int, None]]:
        """
        Use Starlette request_data and endpoint_data from the Device registry here to determine
        should we accept or reject this request.

        :param request_data: deserialized Starlette Request
        :param endpoint_data: endpoint data from the Device registry
        :return: (bool ok, str error text, int status code)
        """
        pprint(request_data)
        pprint(endpoint_data)
        return super().validate(request_data, endpoint_data)

    async def process_request(
        self, request_data: dict, endpoint_data: dict
    ) -> Tuple[bool, str, Union[str, None], Union[str, dict, list], int]:
        """
        Just do minimal validation for request_data and
        return ok if token was valid.
        """
        auth_ok, response_message, status_code = await self.validate(
            request_data, endpoint_data
        )
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
