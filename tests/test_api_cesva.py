import logging
import os
from datetime import datetime, timedelta, timezone
import json
import httpx

logging.basicConfig(level=logging.INFO)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
API_TOKEN = os.getenv("API_TOKEN", "abc123")


# query params
PARAMS = {
    "x-api-key": API_TOKEN
}

# Body
PAYLOAD = {"sensors":[
	{
		"sensor":"TA120-T246187-N",
		"observations":[
			{"value":"61.2", "timestamp":"24/02/2022T17:45:15UTC"}
		]
	},{
		"sensor":"TA120-T246187-O",
		"observations":[
			{"value":"false", "timestamp":"24/02/2022T17:45:15UTC"}
		]
	},{
		"sensor":"TA120-T246187-U",
		"observations":[
			{"value":"false", "timestamp":"24/02/2022T17:45:15UTC"}
		]
	},{
		"sensor":"TA120-T246187-M",
		"observations":[
			{"value":"77", "timestamp":"24/02/2022T17:45:15UTC"}
		]
	},{
		"sensor":"TA120-T246187-S",
		"observations":[
			{"value":"060.6,0,0;060.8,0,0;060.4,0,0;059.9,0,0;059.9,0,0;060.6,0,0;060.7,0,0;060.4,0,0;059.9,0,0;059.9,0,0;060.2,0,0;060.4,0,0;060.8,0,0;059.9,0,0;059.7,0,0;060.6,0,0;061.1,0,0;061.1,0,0;060.6,0,0;061.3,0,0;061.4,0,0;060.6,0,0;060.7,0,0;060.6,0,0;061.4,0,0;061.3,0,0;061.0,0,0;060.3,0,0;059.6,0,0;059.6,0,0;060.4,0,0;062.0,0,0;062.6,0,0;061.7,0,0;061.8,0,0;062.5,0,0;061.8,0,0;062.1,0,0;061.6,0,0;061.1,0,0;063.0,0,0;061.2,0,0;061.1,0,0;060.6,0,0;060.1,0,0;061.8,0,0;062.1,0,0;062.4,0,0;061.5,0,0;061.9,0,0;062.5,0,0;061.9,0,0;061.1,0,0;061.8,0,0;062.0,0,0;062.2,0,0;062.2,0,0;062.9,0,0;062.2,0,0;061.3,0,0", "timestamp":"24/02/2022T17:45:15UTC"}
		]
	}
]}


def test_service_up():
    url = API_BASE_URL
    resp = httpx.get(url)
    assert resp.status_code == 200, "service is up"
    assert resp.json()["message"] == "Test ok", "service is up"


def test_cesva_endpoint_up():
    url = f"{API_BASE_URL}/api/v1/cesva"
    resp = httpx.put(url)
    assert resp.status_code == 401, "error: /api/v1/cesva accessible without token"
    assert resp.text.startswith("Missing or invalid authentication token"), "error: /api/v1/cesva accessible without token"


def test_cesva_endppoint_authenticated_access():
    url = f"{API_BASE_URL}/api/v1/cesva"
    payload = PAYLOAD.copy()
    params = PARAMS.copy()

    resp = httpx.put(url, params=params, data=json.dumps(payload))
    logging.info(resp.text)
    assert resp.status_code in [200, 201, 202], "message forwarded"
    params["x-api-key"] = "wrong"
    resp = httpx.put(url, params=params, data=payload)
    logging.info(resp.text)
    assert resp.status_code == 401, "failed as intended"


def main():
    #test_service_up()
    #test_cesva_endpoint_up()
    test_cesva_endppoint_authenticated_access()


if __name__ == "__main__":
    main()
