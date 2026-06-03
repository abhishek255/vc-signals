#!/usr/bin/env python3
"""Detect configured source/enrichment provider access without calling vendors."""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from last30days_adapter import DEFAULT_CONFIG_PATH
except ImportError:  # pragma: no cover - damaged local installs
    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "last30days" / ".env"

VC_SIGNALS_CONFIG_PATH = Path.home() / ".config" / "vc-signals" / ".env"

PLACEHOLDER_VALUES = {"", "...", "TODO", "YOUR_KEY", "YOUR_API_KEY", "<YOUR_API_KEY>"}
PROVIDERS = {
    "Crunchbase": {
        "keys": ("CRUNCHBASE_API_KEY", "CRUNCHBASE_TOKEN"),
        "coverage": ["company_identity_funding_founders_headcount"],
        "manual_mode": True,
        "manual_strategy": "Use manual funding/stage lookup from launch articles, investor posts, public snippets, and company pages for top candidates.",
    },
    "PitchBook": {
        "keys": ("PITCHBOOK_API_KEY", "PITCHBOOK_CLIENT_ID"),
        "coverage": ["funding_stage_private_market_metadata"],
    },
    "Coresignal": {
        "keys": ("CORESIGNAL_API_KEY",),
        "coverage": ["company_identity_headcount_linkedin_profile"],
        "manual_mode": True,
        "manual_strategy": "Use Brave/last30days/company-site resolver for official domain, team, careers, customers, and hiring evidence.",
    },
    "People Data Labs": {
        "keys": ("PDL_API_KEY", "PEOPLE_DATA_LABS_API_KEY"),
        "coverage": ["people_founder_company_identity"],
    },
    "Dealroom": {
        "keys": ("DEALROOM_API_KEY",),
        "coverage": ["company_identity_funding_stage"],
    },
    "Apollo": {
        "keys": ("APOLLO_API_KEY",),
        "coverage": ["company_identity_people_headcount"],
    },
    "Clay": {
        "keys": ("CLAY_API_KEY",),
        "coverage": ["manual_workflow_enrichment"],
    },
    "Product Hunt API": {
        "keys": ("PRODUCT_HUNT_TOKEN", "PRODUCTHUNT_API_TOKEN", "PRODUCT_HUNT_API_TOKEN"),
        "coverage": ["launch_company_identity_makers"],
    },
    "X": {
        "keys": ("XAI_API_KEY", "AUTH_TOKEN+CT0", "TWITTER_AUTH_TOKEN+TWITTER_CT0"),
        "coverage": ["launch_social_confidence"],
    },
    "Attio": {
        "keys": ("ATTIO_ACCESS_TOKEN",),
        "coverage": ["crm_owner_status_dedupe_context"],
    },
    "LinkedIn": {
        "keys": ("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_API_KEY"),
        "coverage": ["company_profile_people_headcount"],
        "manual_mode": True,
        "manual_strategy": "Use manual LinkedIn checks only for high-value candidates; do not scrape or treat missing API access as a weekly blocker.",
    },
}


def _configured(value: object) -> bool:
    normalized = str(value or "").strip().strip("\"'")
    return normalized not in PLACEHOLDER_VALUES


def load_env_file(path: Path | str = DEFAULT_CONFIG_PATH) -> dict[str, str]:
    env: dict[str, str] = {}
    config_path = Path(path)
    if not config_path.exists():
        return env
    for line in config_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip().strip("\"'")
    return env


def _merged_env(env: dict[str, str] | None, *, config_path: Path | str = DEFAULT_CONFIG_PATH) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in dict.fromkeys((Path(config_path), VC_SIGNALS_CONFIG_PATH)):
        for key, value in load_env_file(path).items():
            if _configured(value) or key not in merged:
                merged[key] = value
    merged.update(os.environ)
    if env is not None:
        merged.update(env)
    return merged


def _provider_configured(provider: dict, env: dict[str, str]) -> tuple[bool, list[str]]:
    configured_keys = []
    for key in provider["keys"]:
        if "+" in key:
            key_parts = key.split("+")
            if all(_configured(env.get(part)) for part in key_parts):
                configured_keys.append(key)
        elif _configured(env.get(key)):
            configured_keys.append(key)
    return bool(configured_keys), configured_keys


def detect_enrichment_provider_access(
    env: dict[str, str] | None = None,
    *,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
) -> dict:
    source_env = _merged_env(env, config_path=config_path)
    providers = {}
    configured = []
    missing = []
    manual_mode = []
    for name, provider in PROVIDERS.items():
        is_configured, configured_keys = _provider_configured(provider, source_env)
        if is_configured:
            configured.append(name)
        elif provider.get("manual_mode"):
            manual_mode.append(name)
        else:
            missing.append(name)
        providers[name] = {
            "status": "configured" if is_configured else "manual_mode" if provider.get("manual_mode") else "missing",
            "direct_access_status": "configured" if is_configured else "missing",
            "configured_keys": configured_keys,
            "accepted_keys": list(provider["keys"]),
            "coverage": list(provider["coverage"]),
            "manual_mode": bool(provider.get("manual_mode", False)) and not is_configured,
            "manual_strategy": provider.get("manual_strategy", ""),
        }
    return {
        "summary": {
            "configured": configured,
            "manual_mode": manual_mode,
            "missing": missing,
            "recommendation": (
                "Product Hunt and X are configured; Coresignal, Crunchbase, and LinkedIn are intentionally manual-mode for now."
                if "Product Hunt API" in configured and "X" in configured
                else "Product Hunt is configured; next direct unlock should be X. Coresignal, Crunchbase, and LinkedIn are intentionally manual-mode for now."
                if "Product Hunt API" in configured
                else "Unlock Product Hunt API and X next; Coresignal, Crunchbase, and LinkedIn can stay manual-mode for this sprint."
            ),
        },
        "providers": providers,
    }


def main() -> None:
    print(json.dumps(detect_enrichment_provider_access(), indent=2))


if __name__ == "__main__":
    main()
