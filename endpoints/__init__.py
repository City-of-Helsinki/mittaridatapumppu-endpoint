import abc

import ipaddress
import logging
import os
from typing import Tuple, Union


def is_ip_address_allowed(request_data: dict, allowed_ip_addresses: str):
    """
    Check if the request IP address is in the allowed IP addresses list.
    """

    def log_match(header: str, ip: str, allowed_network):
        """Shortcut to log a match"""
        logging.debug(f"{header} IP {ip} was in {allowed_network}")

    allowed_ips = [ip.strip() for ip in allowed_ip_addresses.split("\n") if ip.strip()]

    # Loop all allowed IP addresses and networks and check if the request IP address is in one of them
    for a_ip in allowed_ips:
        try:
            allowed_network = ipaddress.ip_network(a_ip, strict=False)
            r_ip = request_data["remote_addr"]
            if ipaddress.ip_address(r_ip) in allowed_network:
                log_match("remote_addr", r_ip, allowed_network)
                return True
            r_ip = request_data["request"]["headers"].get("x-real-ip")
            if (
                r_ip
                and ipaddress.ip_address(request_data["request"]["headers"].get("x-real-ip", "")) in allowed_network
            ):
                log_match("x-real-ip", r_ip, allowed_network)
                return True

            forwarded_for_ips = request_data["request"]["headers"].get("x-forwarded-for", "").split(",")
            for r_ip in forwarded_for_ips:
                r_ip = r_ip.strip()
                if a_ip:
                    if ipaddress.ip_address(r_ip) in allowed_network:
                        log_match("x-forwarded-for", r_ip, allowed_network)
                        return True
        except ValueError as e:
            logging.exception(f"Failed to check IP address {a_ip} / {allowed_ips}: {e}")
    logging.warning("IP address was not allowed")
    return False



# TODO: remove as this is not used anywhere
class BaseRequestHandler(abc.ABC):
    def __init__(self):
        pass

    @abc.abstractmethod
    def process_request(self, request_data: dict) -> Tuple[bool, Union[str, None], Union[str, dict, list], int]:
        """
        Validate request and generate response
        :param request_data:
        :return: (
            bool: request was valid or not
            str: kafka topic's name
            str/dict/list: response str or dict
            int: HTTP status code
        )
        """
        auth_ok = True
        topic_name = os.getenv("KAFKA_RAW_DATA_TOPIC_NAME")
        response_message = {"status": "ok"}
        status_code = 200
        return auth_ok, topic_name, response_message, status_code


class AsyncRequestHandler(abc.ABC):
    """
    Async version of BaseRequestHandler, compatible with Starlette, FastAPI and Device registry.
    """

    def __init__(self):
        pass

    @abc.abstractmethod
    async def process_request(
        self, request_data: dict, endpoint_data: dict
    ) -> Tuple[bool, Union[str, None], Union[str, None], Union[str, dict, list], int]:
        """
        Validate request and generate response
        :param request_data:
        :param endpoint_data:
        :return: (
            bool: request was valid or not
            str: kafka topic's name
            str/dict/list: response str or dict
            int: HTTP status code
        )
        """
        auth_ok = True
        device_id = None
        topic_name = os.getenv("KAFKA_RAW_DATA_TOPIC_NAME")
        response_message = {"status": "ok"}
        status_code = 200
        return auth_ok, device_id, topic_name, response_message, status_code

    @abc.abstractmethod
    async def get_metadata(self, request_data: dict, device_id: str) -> str:
        metadata = "{}"
        # Get metadata from somewhere here, if needed
        return metadata
