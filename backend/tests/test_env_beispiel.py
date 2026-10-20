"""Paket 17 (D6): ``deploy/.env.example`` nennt jede Einstellung — und kennzeichnet Geheimnisse.

Leitfaden „Übergabe an Team 6“: jede Einstellung ist als Env-Variable verfügbar, mit einer
Liste der Werte und ihrer Vorgaben; Secrets sind getrennt gekennzeichnet. Vor Paket 17 fehlten
38 Variablen (gemessen 2026-10-20). Dieser Wächter vergleicht die Datei mit ``Settings`` und
den direkten ``os.getenv``-Stellen im Code — eine neue Variable ohne Eintrag wird rot.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import AliasChoices

from boerdi.settings import Settings

_BACKEND = Path(__file__).resolve().parents[1]
_BEISPIEL = _BACKEND.parent / "deploy" / ".env.example"
_MARKE = "[GEHEIMNIS]"
#: Geheimnisse ohne ``SecretStr``-Feld: Compose baut daraus die Datenbank-Adresse.
_WEITERE_GEHEIMNISSE = {"POSTGRES_PASSWORD", "DATABASE_URL"}
#: Gelesen, aber von der Plattform gesetzt, nie vom Betreiber (Paket 17, C4).
_VON_DER_PLATTFORM = {"KUBERNETES_SERVICE_HOST"}


def _namen(feld: str, info) -> list[str]:
    alias = info.validation_alias
    if isinstance(alias, AliasChoices):
        return [str(n) for n in alias.choices]
    return [str(alias or feld.upper())]


def _einstellungen() -> dict[str, bool]:
    """Name → ist ein Geheimnis."""
    namen: dict[str, bool] = {}
    for feld, info in Settings.model_fields.items():
        for name in _namen(feld, info):
            namen[name] = "SecretStr" in str(info.annotation)
    muster = re.compile(r"""os\.(?:getenv|environ\.get)\(\s*["']([A-Z][A-Z0-9_]+)["']"""
                        r"""|os\.environ\[\s*["']([A-Z][A-Z0-9_]+)["']\]""")
    for pfad in (_BACKEND / "src" / "boerdi").rglob("*.py"):
        for treffer in muster.finditer(pfad.read_text(encoding="utf-8")):
            name = treffer.group(1) or treffer.group(2)
            if name not in _VON_DER_PLATTFORM:
                namen.setdefault(name, False)
    for name in _WEITERE_GEHEIMNISSE:
        namen[name] = True
    return namen


def _zeilen() -> list[str]:
    return _BEISPIEL.read_text(encoding="utf-8").splitlines()


def _eintrag(name: str) -> int | None:
    for i, zeile in enumerate(_zeilen()):
        if re.match(rf"^#?\s*{re.escape(name)}=", zeile):
            return i
    return None


def test_jede_einstellung_steht_in_der_beispieldatei() -> None:
    fehlt = sorted(n for n in _einstellungen() if _eintrag(n) is None)
    assert not fehlt, f"in deploy/.env.example ergänzen: {fehlt}"


def test_geheimnisse_sind_gekennzeichnet() -> None:
    zeilen = _zeilen()
    ohne = []
    for name, geheim in _einstellungen().items():
        i = _eintrag(name)
        if not geheim or i is None:
            continue
        if _MARKE not in zeilen[i] and (i == 0 or _MARKE not in zeilen[i - 1]):
            ohne.append(name)
    assert not ohne, f"{_MARKE} fehlt über: {sorted(ohne)}"


def test_keine_einstellung_traegt_die_marke_zu_unrecht() -> None:
    geheim = {n for n, g in _einstellungen().items() if g}
    zeilen = _zeilen()
    falsch = []
    for i, zeile in enumerate(zeilen):
        treffer = re.match(r"^#?\s*([A-Z][A-Z0-9_]+)=", zeile)
        if not treffer:
            continue
        markiert = _MARKE in zeile or (i > 0 and _MARKE in zeilen[i - 1])
        if markiert and treffer.group(1) not in geheim:
            falsch.append(treffer.group(1))
    assert not falsch, falsch


#: Nur für Compose, nicht für die App (traefik, Image-Name, Repliken, Sicherung, Host-Ordner).
_NUR_COMPOSE = {"ACME_EMAIL", "BACKEND_REPLICAS", "BACKUP_KEEP_DAYS", "BOERDI_IMAGE",
                "PUBLIC_HOST", "RERANK_MODEL_HOST_DIR"}


def test_kein_veralteter_eintrag() -> None:
    """Review Phase D (K10): auch die Gegenrichtung — ein Eintrag, dessen Einstellung im Code
    entfernt wurde, stünde sonst still weiter in der Datei."""
    bekannt = set(_einstellungen()) | _NUR_COMPOSE
    eintraege = re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", _BEISPIEL.read_text(encoding="utf-8"),
                           re.M)
    assert not sorted(set(eintraege) - bekannt)
