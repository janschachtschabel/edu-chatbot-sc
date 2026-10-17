"""Wächter für den Auslieferungsstand (Paket 6, W1).

Der Werkszustand („Alles auf Auslieferungsstand“ im Studio, ``boerdi
import-config --exact``) schreibt den Seed-Baum aus dem Image in die Datenbank.
Damit er jederzeit trägt, muss der Baum zwei Dinge erfüllen, die bisher kein
Test festhielt:

* Registry und Baum decken sich in beiden Richtungen — ein registrierter Bereich
  ohne Seed fehlte nach einem Reset, eine Seed-Datei ohne Modell ginge ungeprüft
  durch.
* Jedes Seed-Dokument besteht dieselbe Prüfung wie ein Wiederherstellen (Modell,
  Schlüssel, Lotsen- und Policy-Regex, reservierte Kennung). Sonst käme ein
  ungültiger Seed erst beim Reset ans Licht — oder gar nicht, denn bis Paket 6
  prüfte das Seed-Anwenden nicht.

Ohne Datenbank: gelesen wird der echte Baum unter ``backend/seeds``.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from boerdi.domain.config_models import AREA_MODELS, model_for
from boerdi.services import seed_sync

#: Gruppen-Bereiche: ein Modell für jedes Dokument darunter, kein eigener Schlüssel.
_GRUPPEN = ("03-patterns", "04-personas")


def _seed_pfad() -> Path:
    pfad = seed_sync.seed_pfad("seeds")
    assert pfad is not None, "backend/seeds nicht gefunden"
    return pfad


def _seed(pfad: Path | None = None) -> dict[str, dict]:
    return asyncio.run(seed_sync.seed_lesen(pfad or _seed_pfad()))


def test_jeder_feste_bereich_der_registry_hat_eine_seed_datei():
    seed = _seed()
    fehlend = sorted(k for k in AREA_MODELS if k not in _GRUPPEN and k not in seed)
    assert fehlend == [], f"registriert, aber nicht ausgeliefert: {fehlend}"


def test_jede_seed_datei_hat_ein_modell():
    ohne = sorted(k for k in _seed() if model_for(k) is None)
    assert ohne == [], f"ausgeliefert, aber ohne Modell (ungeprüft): {ohne}"


def test_jede_gruppe_bringt_dokumente_mit():
    seed = _seed()
    for gruppe in _GRUPPEN:
        assert any(k.startswith(f"{gruppe}/") for k in seed), f"{gruppe}: kein Dokument im Seed"


def test_jedes_seed_dokument_besteht_die_pruefung_des_wiederherstellens():
    from boerdi.api.config_guards import pruefe_bereiche

    seed = _seed()
    assert pruefe_bereiche(seed, "de").keys() == seed.keys()


def test_ein_seed_mit_modellfehler_wird_abgewiesen(tmp_path):
    # Gegenprobe: dieselbe Prüfung meldet einen kaputten Baum, mit Bereich.
    from fastapi import HTTPException

    from boerdi.api.config_guards import pruefe_bereiche

    kopie = tmp_path / "seeds"
    shutil.copytree(_seed_pfad(), kopie, ignore=shutil.ignore_patterns("rag"))
    (kopie / "01-base" / "engine.yaml").write_text("mode: kaputt\n", encoding="utf-8")
    with pytest.raises(HTTPException) as err:
        pruefe_bereiche(_seed(kopie), "de")
    assert err.value.status_code == 422
    assert any(f["area"] == "01-base/engine" for f in err.value.detail)


def _kennungs_fehler(seed: dict[str, dict]) -> list[str]:
    """Die Regeln, die das Studio seit S1 beim Speichern durchsetzt
    (``api/config_kennungen.kennungs_einwand``): Form der Kennung, eine Kennung je
    Ordner ohne Rücksicht auf Groß/Klein, Persona unter ``_persona_slug(id)``."""
    from boerdi.api.config_kennungen import KENNUNG, schluessel_fuer

    fehler: list[str] = []
    for gruppe in _GRUPPEN:
        gesehen: dict[str, str] = {}
        for key, data in sorted(seed.items()):
            if not key.startswith(f"{gruppe}/"):
                continue
            fm = data.get("frontmatter") if isinstance(data, dict) else None
            kennung = str((fm or {}).get("id") or "").strip()
            if not kennung:
                continue
            if not KENNUNG.fullmatch(kennung):
                fehler.append(f"{key}: Kennung {kennung!r} ungültig")
            if kennung.lower() in gesehen:
                fehler.append(f"{key}: Kennung {kennung!r} schon in {gesehen[kennung.lower()]}")
            gesehen[kennung.lower()] = key
            if gruppe == "04-personas" and schluessel_fuer(gruppe, kennung) != key:
                soll = schluessel_fuer(gruppe, kennung)
                fehler.append(f"{key}: Persona {kennung!r} gehört nach {soll}")
    return fehler


def test_die_kennungen_im_seed_halten_die_regeln_des_studios():
    # Review Paket 6: sonst ließe sich ein ausgeliefertes Dokument im Studio
    # nicht mehr speichern.
    assert _kennungs_fehler(_seed()) == []


def test_die_kennungs_pruefung_findet_verstoesse():
    seed = {
        "03-patterns/a": {"frontmatter": {"id": "M05"}, "body": ""},
        "03-patterns/b": {"frontmatter": {"id": "m05"}, "body": ""},
        "03-patterns/c": {"frontmatter": {"id": "M06 neu"}, "body": ""},
        "04-personas/x": {"frontmatter": {"id": "P-LEH"}, "body": ""},
    }
    assert len(_kennungs_fehler(seed)) == 3

