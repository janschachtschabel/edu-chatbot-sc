"""ST-4: ``x-primary`` — Inhalt vor Technik.

Bis ST-4 stand im Studio „Grundwerte" bzw. „Kopfangaben" zuerst und offen, der
Begrüßungstext und die Regeltexte dahinter und zugeklappt. Das Modell sagt jetzt,
welche Felder der Inhalt eines Bereichs sind; das Studio stellt sie vorn hin.

Der Wächter hält die Liste bewusst eng: ein Hinweis, den jedes Modell trägt,
ordnete nichts mehr.
"""

from typing import Any

from boerdi.domain.config_models import AREA_MODELS

#: Modell → Felder, die der Inhalt sind (Plan 2026-09-26 §9.3, ST-4a).
ERWARTET = {
    ("WelcomeBlock", "greeting"),
    ("WelcomeBlock", "quick_replies"),
    # Paket 15: die englischen Texte sind ebenso Inhalt (sonst zwischen den Grundwerten).
    ("WelcomeBlock", "greeting_en"),
    ("WelcomeBlock", "quick_replies_en"),
    ("LayerDocArea", "body"),
    ("PersonaArea", "body"),
}


def _objekte(schema: dict) -> list[dict]:
    """Das Wurzelobjekt und alle ``$defs`` mit Eigenschaften."""
    gefunden = [schema] if schema.get("properties") else []
    gefunden += [d for d in (schema.get("$defs") or {}).values() if d.get("properties")]
    return gefunden


def _markiert() -> dict[tuple[str, str], dict[str, Any]]:
    treffer: dict[tuple[str, str], dict[str, Any]] = {}
    for model in set(AREA_MODELS.values()):
        schema = model.model_json_schema()
        for objekt in _objekte(schema):
            for key, prop in objekt["properties"].items():
                if prop.get("x-primary"):
                    treffer[(objekt["title"], key)] = prop
    return treffer


def test_genau_die_inhaltsfelder_sind_markiert() -> None:
    assert set(_markiert()) == ERWARTET


def test_der_hinweis_vertraegt_sich_mit_den_uebrigen() -> None:
    # Annotated mit zwei Field()-Hinweisen: pydantic muss beide Zusätze behalten,
    # sonst verlöre der Begrüßungstext seine Textfläche oder die Liste ihr Radio.
    markiert = _markiert()
    assert markiert[("WelcomeBlock", "greeting")].get("x-widget") == "textarea"
    assert markiert[("WelcomeBlock", "quick_replies")].get("x-marker") == "tour_reply"
    assert markiert[("LayerDocArea", "body")].get("x-widget") == "textarea"
    assert markiert[("PersonaArea", "body")].get("x-widget") == "textarea"
