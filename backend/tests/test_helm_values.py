"""Paket 17 (D7): ``deploy/helm/values.example.yaml`` — das Mapping für Team 6 (Helm).

Leitfaden „Übergabe an Team 6“: T4 liefert eine Beispiel-Values-Struktur, die auf die
Env-Variablen abgebildet wird; Secrets getrennt; optionale Bestandteile (Datenbank, Valkey)
abschaltbar; Ressourcen, Skalierung und Proben, die Compose nicht enthält. T6 baut das Chart
(Nutzer-Entscheid 2026-10-20). Der Wächter hält die Datei mit ``Settings`` und Compose gleich.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
_VALUES = _REPO / "deploy" / "helm" / "values.example.yaml"
_COMPOSE = _REPO / "deploy" / "compose.prod.yml"


def _env_modul():
    pfad = Path(__file__).with_name("test_env_beispiel.py")
    spec = importlib.util.spec_from_file_location("test_env_beispiel", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _values() -> dict:
    return yaml.safe_load(_VALUES.read_text(encoding="utf-8"))


def test_jede_einstellung_ist_abgebildet() -> None:
    v = _values()
    abgebildet = set(v["env"]) | set(v["secretEnv"]["keys"]) | set(v["imageEnv"])
    fehlt = sorted(set(_env_modul()._einstellungen()) - abgebildet)
    assert not fehlt, f"in values.example.yaml ergänzen: {fehlt}"


def test_geheimnisse_nur_als_secret() -> None:
    v = _values()
    geheim = {n for n, g in _env_modul()._einstellungen().items() if g}
    assert geheim <= set(v["secretEnv"]["keys"])
    assert not geheim & set(v["env"]), "Geheimnis im Klartext-Block"


def test_proben_am_internen_port_und_ingress_nur_oeffentlich() -> None:
    v = _values()
    assert v["ports"] == {"public": 8100, "internal": 8101}
    assert v["probes"]["liveness"]["path"] == "/health"
    assert v["probes"]["readiness"]["path"] == "/ready"
    assert {v["probes"][p]["port"] for p in ("liveness", "readiness", "startup")} == {"internal"}
    assert v["ingress"]["port"] == "public"
    assert "/metrics" not in str(v["ingress"])


def test_die_gnadenfrist_deckt_das_herunterfahren() -> None:
    """Uvicorn 30 s + Nachlauf der Züge + Abbruch + Aufräumen (wie ``stop_grace_period``)."""
    from boerdi.api.sse import NACHLAUF_FRIST_S
    from boerdi.obs.tasks import ABBRUCH_FRIST_S

    v = _values()
    # Kubernetes zieht preStop von der Gnadenfrist ab (Review Phase D, K3).
    pre_stop = v["lifecycle"]["preStopSleepSeconds"]
    assert pre_stop >= 5
    from boerdi.services.laeufe_beenden import _FRIST_S as abschluss_s

    assert (v["terminationGracePeriodSeconds"]
            >= abschluss_s + 30 + NACHLAUF_FRIST_S + 2 * ABBRUCH_FRIST_S + 2 + pre_stop)


def test_proben_haben_eine_frist_ueber_der_datenbank_probe() -> None:
    v = _values()
    assert all(v["probes"][p]["timeoutSeconds"] >= 3 for p in ("liveness", "readiness", "startup"))


def test_forwarded_for_nur_mit_bedingung() -> None:
    """Review Phase D (K1): ohne überschreibenden Ingress fälschte jeder Client seine IP."""
    assert _values()["env"]["TRUST_FORWARDED_FOR"] == "false"


def test_cluster_pflichten() -> None:
    v = _values()
    assert v["env"]["RATE_LIMIT_STORAGE_URI"].startswith("valkey://")
    assert v["env"]["LOG_FORMAT"] == "json"
    assert v["postgresql"]["enabled"] is False and v["postgresql"]["external"]["host"]
    assert "enabled" in v["valkey"]


def test_migration_wie_in_compose() -> None:
    compose = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    assert _values()["migrateJob"]["command"] == compose["services"]["migrate"]["command"]


def test_image_mit_versions_tag() -> None:
    tag = _values()["image"]["tag"]
    assert tag != "latest" and tag.count(".") == 2  # SemVer für Produktion
