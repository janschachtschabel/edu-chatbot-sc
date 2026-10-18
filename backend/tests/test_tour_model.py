"""Paket 15 (D2): die Tour-Schritte und die Angebote einer Besuchergruppe sind typisiert.

Bis dahin ``steps: dict[str, Any]`` und ``angebote: Any`` — im Studio zwei JSON-Kästen, die
niemand ohne den Code lesen konnte (Nutzer-Rundgang 2026-10-17). Das Speicherformat bleibt:
dieselben Schlüssel, die Rohdaten werden weiter unverändert abgelegt.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from boerdi.domain.config_models.base_widget import TourSteps, WebsiteTourArea
from boerdi.domain.config_models.schema import area_schema

_SEED = Path(__file__).resolve().parents[1] / "seeds" / "01-base" / "website-tour.yaml"


def test_der_seed_bleibt_gueltig_und_wird_typisiert() -> None:
    daten = yaml.safe_load(_SEED.read_text(encoding="utf-8"))
    area = WebsiteTourArea.model_validate(daten)
    assert area.website_tour.steps.solutions.angebote_label
    assert area.website_tour.groups[0].angebote[0].path.startswith("/")


def test_das_schema_zeigt_felder_statt_json() -> None:
    defs = area_schema(WebsiteTourArea)["$defs"]
    assert set(defs["TourSteps"]["properties"]) == {
        "intro", "group", "group_page", "content", "solutions", "contact"}
    angebote = defs["TourGroup"]["properties"]["angebote"]
    assert "LabelPath" in str(angebote)


def test_die_vorgaben_sind_die_rueckfaelle_des_tour_codes() -> None:
    # `domain/tour.py` liest ``st.get("nav_label", "Zur Startseite")`` usw. — das Studio zeigt
    # eine fehlende Angabe mit der Schema-Vorgabe; beide müssen dasselbe sagen.
    s = TourSteps()
    assert s.intro.nav_label == "Zur Startseite"
    assert s.group_page.nav_label == "Zur Seite"
    assert s.content.nav_label == "Zu den Bildungsinhalten"
    assert s.solutions.nav_label == "Weiter zum Abschluss"
    assert s.solutions.angebote_label == "Für dich relevant"
    assert s.solutions.sublinks_label == "Zum Stöbern"
    assert s.contact.links_label == "Hier geht's weiter"


def test_pills_tragen_kein_ungelesenes_params_feld() -> None:
    """Paket 15 (D3): ``ContextPill.params`` las niemand — die Parameter einer Aktion baut
    ``graph/nodes/context_greeting`` selbst. Im Studio stand je Pill-Liste ein JSON-Kasten
    dafür. Alte Dokumente mit ``params`` bleiben gültig (``extra="allow"``)."""
    from boerdi.domain.config_models.base_widget import ContextPill

    assert "params" not in ContextPill.model_fields
    alt = ContextPill.model_validate({"label": "x", "kind": "action", "params": {"a": 1}})
    assert alt.model_extra == {"params": {"a": 1}}


def test_leere_yaml_werte_gelten_wie_in_der_laufzeit() -> None:
    """Review-Runde 2 (R2-13): ein leerer YAML-Schlüssel (``null``) — ``domain/tour`` setzt den
    Rückfall ein, die Prüfung darf ihn nicht mit 422 abweisen (Formular, Rohtext,
    Wiederherstellen)."""
    from boerdi.domain.config_models.base_widget import WebsiteTourBlock

    block = WebsiteTourBlock.model_validate({
        "steps": {"intro": None, "contact": {"text": None, "links_label": None}},
        "groups": [{"id": "g1", "angebote": [{"label": "A", "path": None}]}],
        "contact_links": [{"label": None, "path": "/x"}],
    })
    assert block.steps.intro.nav_label == "Zur Startseite"
    assert block.steps.contact.text == ""
    assert block.steps.contact.links_label == "Hier geht's weiter"
    assert block.groups[0].angebote[0].path == ""
    assert block.contact_links[0].label == ""
