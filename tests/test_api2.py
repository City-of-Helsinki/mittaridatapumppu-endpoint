import json
import os
from datetime import datetime, timedelta, timezone

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
API_TOKEN = os.getenv("API_TOKEN", "abc123")


def test_service_up():
    url = API_BASE_URL
    resp = httpx.get(url)
    assert resp.status_code == 200, "service is up"
    assert resp.json()["message"] == "Test ok", "service is up"


def test_digita_endpoint_up():
    url = f"{API_BASE_URL}/api/v1/digita"
    resp = httpx.get(url)
    assert resp.status_code == 401, "digita v1 is up"
    assert resp.text.startswith("Missing or invalid authentication token"), "digita v1 is up"


def test_digita_endppoint_authenticated_access():
    url = f"{API_BASE_URL}/api/v1/digita"
    # Create a Time string in ISO 8601 format a few seconds in the past
    # This is to make sure that the message is not rejected because of being too old
    # (the default is 60 seconds)

    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Connection": "close",
        "X-Real-Ip": "52.16.83.187",
        "X-Forwarded-For": "52.16.83.187",
        "X-Forwarded-Proto": "https",
        "User-Agent": "ACTILITY-LRCLRN-DEVICE-AGENT/1.0",
    }
    # query params
    params = {
        "token": API_TOKEN,
        "LrnDevEui": "70B3D57050011422",
        "LrnFPort": "2",
        "LrnInfos": "TWA_100002581.57949.AS-1-556889314",
    }
    # Body
    payload = {
        "DevEUI_uplink": {
            "Time": "2022-02-24T16:23:17.468+00:00",
            "DevEUI": "70B3D57050011422",
            "FPort": 20,
            "FCntUp": 3866,
            "ADRbit": 1,
            "MType": 4,
            "FCntDn": 3900,
            "payload_hex": "901429c204282705",
            "mic_hex": "3af4037a",
            "Lrcid": "00000201",
            "LrrRSSI": -113.000000,
            "LrrSNR": -11.000000,
            "LrrESP": -124.331955,
            "SpFact": 8,
            "SubBand": "G1",
            "Channel": "LC1",
            "DevLrrCnt": 1,
            "Lrrid": "FF0109A4",
            "Late": 0,
            "LrrLAT": 60.242538,
            "LrrLON": 25.211100,
            "Lrrs": {
                "Lrr": [
                    {
                        "Lrrid": "FF0109A4",
                        "Chain": 0,
                        "LrrRSSI": -113.000000,
                        "LrrSNR": -11.000000,
                        "LrrESP": -124.331955,
                    }
                ]
            },
            "CustomerID": "100002581",
            "CustomerData": {"alr": {"pro": "mcf88/lw12terwp", "ver": "1"}},
            "ModelCfg": "0",
            "DevAddr": "E00324CA",
            "TxPower": 14.000000,
            "NbTrans": 1,
            "Frequency": 868.1,
            "DynamicClass": "A",
        }
    }
    # Replace Time with ~current time
    ts = (datetime.now(timezone.utc) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    payload["DevEUI_uplink"]["Time"] = ts
    # convert dict to json by json.dumps() for body data.
    resp = httpx.post(url, headers=headers, params=params, data=json.dumps(payload))
    print(params)
    # resp = httpx.post(url, headers=headers, params=params, data=payload)
    print(resp.status_code)
    assert resp.status_code in [200, 201, 202], "message forwarded"
    assert resp.text == "Request accepted", "message forwarded"


def main():
    # test_service_up()
    # test_digita_endpoint_up()
    test_digita_endppoint_authenticated_access()


if __name__ == "__main__":
    main()
