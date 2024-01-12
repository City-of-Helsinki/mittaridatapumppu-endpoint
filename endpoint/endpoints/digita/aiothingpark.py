import logging
import os
from typing import Tuple, Union

from .. import AsyncRequestHandler


class RequestHandler(AsyncRequestHandler):
    async def validate(
        self, request_data: dict, endpoint_data: dict
    ) -> Tuple[bool, Union[str, None], Union[int, None]]:
        """
        Use Starlette request_data here to determine should we accept or reject
        this request
        :param request_data: deserialized (FastAPI) Starlette Request
        :param endpoint_data: endpoint data from device registry
        :return: (bool ok, str error text, int status code)
        """
        [status_ok, response_message, status_code] = await super().validate(
            request_data, endpoint_data
        )

        if status_ok is False:
            return False, response_message, status_code

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
        auth_ok, response_message, status_code = await self.validate(
            request_data, endpoint_data
        )
        device_id = request_data["request"]["get"].get("LrnDevEui")
        if device_id:  # a LrnDevEui must be present to send the data to Kafka topic
            topic_name = endpoint_data["kafka_raw_data_topic"]
        else:
            topic_name = None
        logging.info(
            "Validation: {}, {}, {}".format(auth_ok, response_message, status_code)
        )
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
