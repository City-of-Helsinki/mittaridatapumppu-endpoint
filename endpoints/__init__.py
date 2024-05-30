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
                and ipaddress.ip_address(
                    request_data["request"]["headers"].get("x-real-ip", "")
                )
                in allowed_network
            ):
                log_match("x-real-ip", r_ip, allowed_network)
                return True

            forwarded_for_ips = (
                request_data["request"]["headers"].get("x-forwarded-for", "").split(",")
            )
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


class AsyncRequestHandler(abc.ABC):
    """
    Async version of BaseRequestHandler, compatible with Starlette, FastAPI and Device registry.
    """

    @abc.abstractmethod
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
        # Reject requests not matching the one defined in env
        if request_data["path"] != endpoint_data["endpoint_path"]:
            return False, "Not found", 404
        # Reject requests without token parameter, which can be in query string or http header
        api_key = request_data["request"]["get"].get("x-api-key")
        if api_key is None:
            api_key = request_data["request"]["headers"].get("x-api-key")
        if api_key is None or api_key != endpoint_data["auth_token"]:
            logging.warning("Missing or invalid authentication token (x-api-key)")
            return (
                False,
                "Missing or invalid authentication token, see logs for error",
                401,
            )
        logging.info("Authentication token validated")
        if request_data["request"]["get"].get("test") == "true":
            logging.info("Test ok")
            return False, "Test OK", 400
        allowed_ip_addresses = endpoint_data.get("allowed_ip_addresses", "")
        if allowed_ip_addresses == "":
            logging.warning(
                "Set 'allowed_ip_addresses' in endpoint settings to restrict requests unknown sources"
            )
        else:
            if is_ip_address_allowed(request_data, allowed_ip_addresses) is False:
                return False, "IP address not allowed", 403

        # if all checks passed, return True
        return True, None, None

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
