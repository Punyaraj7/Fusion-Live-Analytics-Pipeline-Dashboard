import json
import time

import requests

from config import BASE_URL

# Shared across every call in this module so the ~600+ requests a full refresh makes
# (workspaces/users/companies plus one per workspace for modules) reuse pooled
# TCP/TLS connections instead of paying a fresh handshake per request.
_session = requests.Session()


def _extract_pagination(payload):
    if not isinstance(payload, dict):
        return {}

    if isinstance(payload.get("pagination"), dict):
        return payload["pagination"]

    data = payload.get("data")
    if isinstance(data, dict):
        if isinstance(data.get("pagination"), dict):
            return data["pagination"]
        pagination = {
            key: data[key]
            for key in ["page", "pageSize", "totalItems", "totalPages"]
            if key in data
        }
        if pagination:
            return pagination

    pagination = {
        key: payload[key]
        for key in ["page", "pageSize", "totalItems", "totalPages"]
        if key in payload
    }
    return pagination


def _extract_page_size(payload, default_page_size):
    pagination = _extract_pagination(payload)
    if isinstance(pagination, dict):
        page_size = pagination.get("pageSize")
        if page_size is not None:
            try:
                return int(page_size)
            except (TypeError, ValueError):
                pass
    return default_page_size


def _extract_items(payload, item_key):
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, dict):
            if item_key in data and isinstance(data[item_key], list):
                return data[item_key]
            if "items" in data and isinstance(data["items"], list):
                return data["items"]
            for value in data.values():
                if isinstance(value, list):
                    return value
            return []
        if isinstance(data, list):
            return data
    if isinstance(payload, list):
        return payload
    return []


def _item_signature(item):
    if isinstance(item, (dict, list)):
        return json.dumps(item, sort_keys=True, default=str)
    return repr(item)


def _request_with_retry(endpoint, headers, params=None):
    for attempt in range(3):
        try:
            response = _session.get(endpoint, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as exc:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except requests.exceptions.RequestException:
            raise


def _request_page(endpoint, headers, page, page_size):
    # For the workspace modules endpoint, try a plain GET first (no pagination params).
    # Other endpoints should use the paginated strategies immediately to preserve
    # the expected call pattern used in tests and by the API.
    # support both singular and plural workspace path forms used by the API/docs
    do_plain_get = (("/workspace/" in endpoint or "/workspaces/" in endpoint) and "/modules" in endpoint)
    if do_plain_get:
        try:
            payload = _request_with_retry(endpoint, headers)
            if isinstance(payload, list):
                return payload, {}
            if isinstance(payload, dict):
                if payload.get("data") is not None or payload.get("items") is not None or payload.get("content") is not None or payload.get("pagination") is not None:
                    return payload, {}
                # If dict but no obvious payload, fall through to pagination strategies
        except requests.HTTPError as he:
            # If the plain GET returned 404 for this workspace, treat as no modules
            try:
                status = response.status_code
            except Exception:
                status = None
            if status == 404:
                return {}, {}
            raise
        except Exception:
            # If plain GET fails for other reasons, we'll try the paginated strategies below
            pass

    strategies = [
        {"page": page, "pageSize": page_size},
        {"fromRow": (page - 1) * page_size, "maxRows": page_size},
    ]

    last_error = None
    for params in strategies:
        try:
            payload = _request_with_retry(endpoint, headers, params=params)
            if isinstance(payload, dict):
                if payload.get("data") is None and payload.get("items") is None and payload.get("content") is None:
                    continue
            return payload, params
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return {}, {}


def _fetch_paginated_resource(token, endpoint, item_key, page_size=100):
    headers = {"Authorization": f"Bearer {token}"}
    all_items = []
    page = 1
    current_page_size = page_size
    max_pages = 100
    last_pagination = {}
    seen_items = set()

    while page <= max_pages:
        payload, params = _request_page(endpoint, headers, page, current_page_size)
        page_items = _extract_items(payload, item_key)
        if not page_items:
            break

        # Some API endpoints ignore page/pageSize and return page one again.
        # Retry the repeated page with the offset-based parameters instead.
        page_signatures = [_item_signature(item) for item in page_items]
        if page > 1 and page_signatures and all(signature in seen_items for signature in page_signatures):
            offset_params = {
                "fromRow": (page - 1) * current_page_size,
                "maxRows": current_page_size,
            }
            payload = _request_with_retry(endpoint, headers, params=offset_params)
            page_items = _extract_items(payload, item_key)
            if not page_items:
                break
            page_signatures = [_item_signature(item) for item in page_items]

        pagination = _extract_pagination(payload)
        if isinstance(pagination, dict):
            if not last_pagination:
                last_pagination = pagination.copy()
            else:
                last_pagination = {
                    **last_pagination,
                    **{k: v for k, v in pagination.items() if k in {"page", "pageSize"} or not last_pagination.get(k)},
                }
        current_page_size = _extract_page_size(payload, current_page_size)

        total_pages = pagination.get("totalPages") if isinstance(pagination, dict) else None
        total_items = pagination.get("totalItems") if isinstance(pagination, dict) else None

        if total_items is not None:
            try:
                total_items = int(total_items)
                remaining_items = max(0, total_items - len(all_items))
                if remaining_items <= 0:
                    break
                page_items = page_items[:remaining_items]
            except (TypeError, ValueError):
                total_items = None

        all_items.extend(page_items)
        seen_items.update(page_signatures)

        total_pages = pagination.get("totalPages") if isinstance(pagination, dict) else None
        total_items = pagination.get("totalItems") if isinstance(pagination, dict) else None

        if total_pages is not None:
            try:
                total_pages = int(total_pages)
                if page >= total_pages:
                    break
            except (TypeError, ValueError):
                total_pages = None

        if total_items is not None:
            try:
                total_items = int(total_items)
                if len(all_items) >= total_items:
                    break
            except (TypeError, ValueError):
                total_items = None

        if total_pages is None and total_items is None and len(page_items) < current_page_size:
            break

        page += 1

    result = {"data": all_items}
    if last_pagination:
        result["pagination"] = {
            **last_pagination,
            "page": last_pagination.get("page", page),
            "pageSize": last_pagination.get("pageSize", current_page_size),
            "totalItems": last_pagination.get("totalItems", len(all_items)),
        }
    return result


def get_workspaces(token):
    return _fetch_paginated_resource(token, f"{BASE_URL}/workspaces", "workspaces", page_size=100)


def get_users(token):
    return _fetch_paginated_resource(token, f"{BASE_URL}/users", "users", page_size=200)


def get_companies(token):
    return _fetch_paginated_resource(token, f"{BASE_URL}/companies", "companies", page_size=200)


def get_workspace_modules(token, workspace_id):
    """Fetch modules for a specific workspace, handling pagination similarly to other endpoints.

    Use the plural path `/workspaces/{id}/modules` which matches the Swagger docs.
    """
    endpoint = f"{BASE_URL}/workspaces/{workspace_id}/modules"
    return _fetch_paginated_resource(token, endpoint, "modules", page_size=100)
