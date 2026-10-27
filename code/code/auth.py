import requests
from config import BASE_URL, FUSION_USERNAME, FUSION_PASSWORD, FUSION_CLIENT_TYPE


def _extract_token(payload):
    if payload is None:
        return None

    if not isinstance(payload, dict):
        return None

    data = payload.get("data")

    if isinstance(data, list) and data:
        first_item = data[0]
        if isinstance(first_item, dict):
            return first_item.get("token") or first_item.get("access_token")

    if isinstance(data, dict):
        return data.get("token") or data.get("access_token")

    return payload.get("token") or payload.get("access_token")


def get_token():
    if not FUSION_USERNAME or not FUSION_PASSWORD:
        raise ValueError("Please set FUSION_USERNAME and FUSION_PASSWORD in your environment or .env file")

    params = {
        "username": FUSION_USERNAME,
        "password": FUSION_PASSWORD,
        "clientType": FUSION_CLIENT_TYPE,
    }

    endpoints = [f"{BASE_URL}/auth/token", f"{BASE_URL}/logon"]
    errors = []

    for url in endpoints:
        try:
            response = requests.post(url, params=params, timeout=60)
        except requests.RequestException as exc:
            errors.append(f"{url}: {exc}")
            continue

        if response.status_code == 401:
            # A definite "wrong credentials": trying the fallback endpoint with them too would
            # only add another failed login toward an account lockout.
            raise RuntimeError(
                f"FusionLive rejected the username/password in the ETL .env file (401 Unauthorized from {url}). "
                "Check you can log in to FusionLive in a browser with them, then update FUSION_PASSWORD "
                "(and FUSION_USERNAME if it changed)."
            )
        if not response.ok:
            errors.append(f"{url}: {response.status_code} {response.reason}")
            continue

        try:
            payload = response.json()
        except ValueError:
            errors.append(f"{url}: response was not JSON")
            continue
        token = _extract_token(payload)
        if token:
            return token
        errors.append(f"Token not found in response from {url}: {payload}")

    raise RuntimeError("Authentication failed with both endpoints: " + " | ".join(errors))
