# Mittaridatapumppu endpoint

```
pip install pip-tools pre-commit
. venv/bin/activate
pre-commit install
pip-sync requirements*.txt
uvicorn endpoint.endpoint:app --host 0.0.0.0 --port 8080 --proxy-headers
API_TOKEN=abcdef1234567890abcdef1234567890abcdef12 venv/bin/python tests/test_api2.py
```
