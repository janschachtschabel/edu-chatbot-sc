"""P2-8: public GET /api/config/guide-mode — bundles guide-mode config +
header_nav buttons + welcome (ALT config_areas.py:176-198). Contract test:
response shape identical to ALT; live key-set diff when ALT runs on :8000.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_ALT_URL = "http://localhost:8000/api/config/guide-mode"


def _neu_bundle() -> dict:
    with TestClient(create_app()) as client:
        resp = client.get("/api/config/guide-mode")
        assert resp.status_code == 200
        return resp.json()


def test_guide_mode_bundle_shape() -> None:
    body = _neu_bundle()
    assert set(body) >= {
        "default_enabled", "allowed_hosts", "url_fields_priority",
        "max_guide_targets_per_turn", "max_guide_quick_replies",
        "trusted_domains", "repo_base_url", "header_nav", "welcome",
    }
    assert isinstance(body["header_nav"], list)
    assert set(body["welcome"]) == {"greeting", "quick_replies", "tour_reply"}
    assert body["welcome"]["greeting"]  # dev DB seeded => real content
    assert isinstance(body["trusted_domains"], list)


def test_guide_mode_is_public_no_auth() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/config/guide-mode").status_code == 200


def _alt_available() -> bool:
    try:
        return httpx.get(_ALT_URL, timeout=3).status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _alt_available(), reason="ALT-Backend nicht erreichbar (:8000)")
def test_key_set_matches_live_alt() -> None:
    alt = httpx.get(_ALT_URL, timeout=5).json()
    neu = _neu_bundle()
    assert set(neu) == set(alt), (
        f"nur NEU: {set(neu) - set(alt)}; nur ALT: {set(alt) - set(neu)}"
    )
    assert set(neu["welcome"]) == set(alt["welcome"])
