#!/usr/bin/env python3
"""Read-only Attio CRM integration for VC Signals.

The token is intentionally read from ATTIO_ACCESS_TOKEN. Do not commit tokens.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

DEFAULT_BASE_URL = "https://api.attio.com/v2"
TOKEN_ENV = "ATTIO_ACCESS_TOKEN"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "vc-signals" / ".env"

PIPELINE_LISTS = {"pipeline_2"}
OLD_PIPELINE_LISTS = {"pipeline"}
PORTFOLIO_LISTS = {"mmp_fund_1_portfolio", "pipeline_2_3"}


class AttioError(RuntimeError):
    """Raised when Attio returns an API error."""


def _read_env_file_value(path: Path | None, key: str) -> str:
    if not path or not path.exists():
        return ""
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() == key:
            return value.strip().strip("\"'")
    return ""


def get_access_token() -> tuple[str, str]:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if token:
        return token, TOKEN_ENV
    token = _read_env_file_value(DEFAULT_CONFIG_PATH, TOKEN_ENV)
    if token:
        return token, str(DEFAULT_CONFIG_PATH)
    return "", ""


def check_config() -> dict:
    """Report whether the Attio token is configured without revealing it."""
    _token, source = get_access_token()
    if not source:
        return {
            "configured": False,
            "base_url": DEFAULT_BASE_URL,
            "error": f"{TOKEN_ENV} is not set",
        }
    return {
        "configured": True,
        "base_url": DEFAULT_BASE_URL,
        "token_source": source,
    }


def parse_objects(payload: dict) -> list[dict]:
    """Return compact object metadata."""
    objects = []
    for obj in payload.get("data", []):
        objects.append({
            "api_slug": obj.get("api_slug"),
            "singular": obj.get("singular_noun"),
            "plural": obj.get("plural_noun"),
        })
    return objects


def parse_lists(payload: dict) -> list[dict]:
    """Return compact company-list metadata."""
    lists = []
    for item in payload.get("data", []):
        parent = item.get("parent_object") or []
        if "companies" not in parent:
            continue
        lists.append({
            "api_slug": item.get("api_slug"),
            "name": item.get("name"),
            "parent_object": parent,
        })
    return lists


def _status_title(attributes: dict | None) -> str:
    values = (attributes or {}).get("status_8") or []
    for value in values:
        status = value.get("status") or {}
        title = status.get("title")
        if title:
            return title
    return ""


def _has_owner(attributes: dict | None) -> bool:
    values = (attributes or {}).get("mmp_owner") or []
    return bool(values)


def classify_match(entries: list[dict], *, attributes: dict | None = None) -> dict:
    """Classify Attio list membership into VC Signals status/action fields."""
    if not entries:
        return {
            "attio_status": "no_match",
            "attio_action": "assign owner",
            "attio_lists": [],
        }

    slugs = {entry.get("list_api_slug", "") for entry in entries}
    names = [entry.get("list_name") or entry.get("list_api_slug") for entry in entries]
    lower_names = " ".join(name.lower() for name in names if name)
    status_title = _status_title(attributes).lower()

    if (
        any("pass" in slug or "pass" in name.lower() for slug, name in zip(slugs, names))
        or any(term in status_title for term in ("pass", "deprioritized", "not interested"))
    ):
        status = "passed"
        action = "flag quietly"
    elif slugs & OLD_PIPELINE_LISTS:
        status = "stale"
        action = "refresh note"
    elif (slugs & PIPELINE_LISTS) and not _has_owner(attributes):
        status = "no_owner"
        action = "assign owner"
    elif slugs & PORTFOLIO_LISTS:
        status = "active"
        action = "monitor only"
    elif slugs & PIPELINE_LISTS:
        status = "active"
        action = "monitor only"
    elif "incumbent" in lower_names:
        status = "active"
        action = "likely too late"
    else:
        status = "active"
        action = "monitor only"

    return {
        "attio_status": status,
        "attio_action": action,
        "attio_lists": names,
    }


def _normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.split("/", 1)[0]


def _domain_values(values: list[dict]) -> set[str]:
    domains = set()
    for value in values:
        for key in ("domain", "root_domain"):
            if value.get(key):
                domains.add(_normalize_domain(value[key]))
    return domains


class AttioClient:
    """Tiny Attio REST client for read-only radar enrichment."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        request_fn: Callable[[str, str, dict | None], dict] | None = None,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._request_fn = request_fn

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if self._request_fn:
            return self._request_fn(method, path, payload)

        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:500]
            raise AttioError(f"Attio HTTP {exc.code}: {body}") from exc

    def list_objects(self) -> list[dict]:
        return parse_objects(self.request("GET", "/objects"))

    def list_company_lists(self) -> list[dict]:
        return parse_lists(self.request("GET", "/lists"))

    def search_companies(self, query: str, *, limit: int = 5) -> list[dict]:
        payload = {
            "query": query,
            "objects": ["companies"],
            "request_as": {"type": "workspace"},
            "limit": limit,
        }
        return self.request("POST", "/objects/records/search", payload).get("data", [])

    def list_record_entries(self, record_id: str) -> list[dict]:
        return self.request("GET", f"/objects/companies/records/{record_id}/entries").get("data", [])

    def list_attribute_values(self, record_id: str, attribute: str) -> list[dict]:
        path = f"/objects/companies/records/{record_id}/attributes/{attribute}/values"
        return self.request("GET", path).get("data", [])

    def company_attributes(self, record_id: str) -> dict:
        attributes = {}
        for attribute in (
            "domains",
            "mmp_owner",
            "status_8",
            "last_interaction",
            "last_round_type",
            "headcount",
            "total_amount_raised_4",
            "employee_range",
        ):
            attributes[attribute] = self.list_attribute_values(record_id, attribute)
        return attributes

    def match_company(self, company: dict) -> dict:
        query = (company.get("domain") or company.get("name") or "").strip()
        if not query:
            return {"attio_status": "unknown", "attio_action": "needs company name/domain"}

        matches = self.search_companies(query, limit=5)
        if not matches:
            return classify_match([])

        match = matches[0]
        record_id = match.get("id", {}).get("record_id")
        attributes = {}
        if record_id:
            attributes["domains"] = self.list_attribute_values(record_id, "domains")
        domain = _normalize_domain(company.get("domain") or "")
        if domain and domain not in _domain_values(attributes.get("domains", [])):
            return classify_match([])
        if record_id:
            attributes.update(self.company_attributes(record_id))

        entries = self.list_record_entries(record_id) if record_id else []
        list_lookup = {item["api_slug"]: item["name"] for item in self.list_company_lists()}
        for entry in entries:
            slug = entry.get("list_api_slug")
            entry["list_name"] = list_lookup.get(slug, slug)

        classification = classify_match(entries, attributes=attributes)
        classification["attio_match"] = {
            "record_text": match.get("record_text"),
            "object_slug": match.get("object_slug"),
            "record_id": record_id,
        }
        classification["attio_attributes"] = summarize_attributes(attributes)
        return classification


def summarize_attributes(attributes: dict) -> dict:
    """Summarize selected Attio attributes for radar output."""
    out = {}
    status = _status_title(attributes)
    if status:
        out["status"] = status
    if attributes.get("mmp_owner"):
        out["has_owner"] = True
    if attributes.get("last_interaction"):
        out["last_interaction"] = attributes["last_interaction"][0].get("interacted_at")
    if attributes.get("last_round_type"):
        out["last_round_type"] = attributes["last_round_type"][0].get("value")
    if attributes.get("headcount"):
        out["headcount"] = attributes["headcount"][0].get("value")
    if attributes.get("total_amount_raised_4"):
        out["total_amount_raised"] = attributes["total_amount_raised_4"][0].get("value")
    if attributes.get("employee_range"):
        value = attributes["employee_range"][0]
        out["employee_range"] = value.get("option", {}).get("title") or value.get("value")
    return out


def enrich_companies(companies: list[dict], client: AttioClient) -> list[dict]:
    """Return companies with read-only Attio match fields merged in."""
    enriched = []
    for company in companies:
        out = company.copy()
        try:
            out.update(client.match_company(company))
        except AttioError as exc:
            out.update({"attio_status": "unknown", "attio_action": "attio error", "attio_error": str(exc)})
        enriched.append(out)
    return enriched


def _read_json_stdin():
    raw = sys.stdin.read()
    if not raw.strip():
        return None, {"error": "No data piped to stdin."}
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, {"error": f"Invalid JSON on stdin: {exc.msg}"}


def _cli_main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: attio.py <check|objects|lists|match|enrich>"}))
        return

    command = sys.argv[1]
    if command == "check":
        print(json.dumps(check_config(), indent=2))
        return

    token, _source = get_access_token()
    if not token:
        print(json.dumps({"error": f"{TOKEN_ENV} is not set"}))
        return

    client = AttioClient(token)

    if command == "objects":
        print(json.dumps({"objects": client.list_objects()}, indent=2))
        return

    if command == "lists":
        print(json.dumps({"lists": client.list_company_lists()}, indent=2))
        return

    if command == "match":
        query = " ".join(sys.argv[2:]).strip()
        if not query:
            print(json.dumps({"error": "Usage: attio.py match <company-or-domain>"}))
            return
        print(json.dumps(client.match_company({"name": query, "domain": query if "." in query else ""}), indent=2))
        return

    if command == "enrich":
        payload, error = _read_json_stdin()
        if error:
            print(json.dumps(error))
            return
        companies = payload.get("companies") if isinstance(payload, dict) else None
        if not isinstance(companies, list):
            print(json.dumps({"error": "stdin payload must be an object with companies list"}))
            return
        print(json.dumps({"companies": enrich_companies(companies, client)}, indent=2))
        return

    print(json.dumps({"error": f"Unknown command: {command}"}))


if __name__ == "__main__":
    _cli_main()
