"""ST-5: wo ein Config-Bereich wirkt — je Maschine, als Zuordnung im Backend.

Das Studio zeigt sie an jedem Abschnitt („Wirkt in: Muster · Agent") und warnt,
wenn die Vorgabe-Maschine eine Seite nicht nutzt. Eine falsche Zuordnung wäre
eine sichtbare Falschaussage — deshalb hält dieser Wächter sie fest: jeder
Bereich hat einen Eintrag, und die am Code belegten Fälle stehen hier.
"""

from boerdi.domain.area_effects import AREA_EFFECTS, EFFECTS, ENGINES
from boerdi.domain.config_models import AREA_MODELS


def test_jeder_bereich_hat_eine_zuordnung() -> None:
    # Ein neuer Bereich ohne Eintrag fiele im Studio still auf „unbekannt" —
    # hier fällt er laut auf.
    assert set(AREA_EFFECTS) == set(AREA_MODELS)


def test_jede_zuordnung_nennt_beide_maschinen_mit_gueltiger_stufe() -> None:
    for area, wirkung in AREA_EFFECTS.items():
        assert set(wirkung) == set(ENGINES), area
        assert set(wirkung.values()) <= set(EFFECTS), area


def test_krisen_zuege_laufen_auch_unter_der_agent_schleife_ueber_die_muster(
) -> None:
    # SF-1 (`engine_choice.zug_laeuft_ueber_die_schleife`): erzwingt das Gate
    # M01/M02, antwortet der Muster-Weg — gleich, welche Maschine gewählt ist.
    # „keine" wäre hier gefährlich falsch: wer daraus schlösse, die Muster
    # seien im Agent-Modus egal, beschädigte die Krisenantwort.
    for area in ("03-patterns", "01-base/base-persona", "02-domain/domain-rules",
                 "02-domain/wlo-plattform-wissen", "01-base/tone-modifiers"):
        assert AREA_EFFECTS[area] == {"pattern": "voll", "agent": "krise"}, area


def test_belegte_faelle() -> None:
    # Das Widget holt Begrüßung und Chips selbst — gleich, wer antwortet.
    assert AREA_EFFECTS["01-base/welcome-config"] == {"pattern": "voll", "agent": "voll"}
    # Seit ST-9 am Code belegt: der Zweig der Widget-Modi läuft nie
    # (`domain/widget_modes.py` setzt `cards_enabled` fest).
    assert AREA_EFFECTS["01-base/widget-modes"] == {"pattern": "keine", "agent": "keine"}
    # Kosten und Gold-Läufe gibt es für beide Maschinen.
    assert AREA_EFFECTS["01-base/pricing"] == {"pattern": "voll", "agent": "voll"}
    assert AREA_EFFECTS["eval/gold-flows"] == {"pattern": "voll", "agent": "voll"}
    # Die Klassifikator-Achsen: die Agent-Schleife klassifiziert nicht.
    assert AREA_EFFECTS["04-intents/intents"] == {"pattern": "voll", "agent": "keine"}


# ── Rundgang 3: Wirkung je Feld ──────────────────────────────────────────────
def _pfade(area: str) -> set[str]:
    """Alle Feldpfade eines Bereichs (Punkt-Schreibweise, durch ``$ref`` hindurch)."""
    from boerdi.domain.config_models.schema import area_schema

    schema = area_schema(AREA_MODELS[area])
    defs = schema.get("$defs", {})

    def aufloesen(knoten: dict) -> dict:
        while "$ref" in knoten:
            knoten = defs[knoten["$ref"].rsplit("/", 1)[-1]]
        if len(knoten.get("allOf", [])) == 1:
            return aufloesen(knoten["allOf"][0])
        return knoten

    pfade: set[str] = set()

    def gehe(knoten: dict, praefix: str) -> None:
        for name, kind in (aufloesen(knoten).get("properties") or {}).items():
            pfade.add(praefix + name)
            gehe(kind, praefix + name + ".")

    gehe(schema, "")
    return pfade


def test_jede_feld_ausnahme_nennt_einen_echten_pfad_und_gueltige_stufen() -> None:
    from boerdi.domain.area_effects import FIELD_EFFECTS

    for area, felder in FIELD_EFFECTS.items():
        assert area in AREA_MODELS, area
        vorhanden = _pfade(area)
        for pfad, wirkung in felder.items():
            assert pfad in vorhanden, (area, pfad)
            assert set(wirkung) == set(ENGINES), (area, pfad)
            assert set(wirkung.values()) <= set(EFFECTS), (area, pfad)


def test_feld_ausnahmen_belegte_faelle() -> None:
    """Die Etiketten galten je Bereich — an Feld-Ausschnitten falsch (Rundgang 3)."""
    from boerdi.domain.area_effects import FIELD_EFFECTS

    engine = FIELD_EFFECTS["01-base/engine"]
    # Rolle & Schutz: wirkt allein im Agent-Kopf und in der Schleife.
    assert engine["agent_rolle"] == {"pattern": "keine", "agent": "voll"}
    assert engine["agent"] == {"pattern": "keine", "agent": "voll"}
    # Skill-Brücke: nur Muster-Züge (`route.py`).
    assert engine["muster_skills"] == {"pattern": "voll", "agent": "keine"}
    # Der Krisentext gilt nur am Endpunkt /api/agent (`agent_gate.py`); im Chat antwortet M01.
    assert FIELD_EFFECTS["01-base/safety-config"]["crisis_message"] == {
        "pattern": "keine", "agent": "extern"}
    # Boxen je Muster: der Agent heißt `AGENT`, der Ratepfad prüft M09/M10/M11.
    assert FIELD_EFFECTS["01-base/display-rules"][
        "display_rules.inline_documents.per_pattern"] == {"pattern": "voll", "agent": "keine"}
    # Ohne Leser.
    assert FIELD_EFFECTS["01-base/website-tour"]["website_tour.start_label"] == {
        "pattern": "keine", "agent": "keine"}
    assert FIELD_EFFECTS["02-domain/guide-rules"]["rag_area_rules"] == {
        "pattern": "keine", "agent": "keine"}
    # Review Paket 16 (B-4): die Korrekturen aus Plan B1.
    assert AREA_EFFECTS["01-base/safety-config"] == {"pattern": "teilweise", "agent": "teilweise"}
    geraet = FIELD_EFFECTS["01-base/device-config"]
    assert geraet["device_max_items"] == {"pattern": "voll", "agent": "voll"}
    assert geraet["persona_formality"] == {"pattern": "voll", "agent": "voll"}
    assert FIELD_EFFECTS["01-base/website-tour"]["website_tour.flows"] == {
        "pattern": "keine", "agent": "keine"}


def test_der_endpunkt_liefert_auch_die_feld_ausnahmen() -> None:
    import asyncio

    from boerdi.api.config_effects import get_effects
    from boerdi.domain.area_effects import FIELD_EFFECTS

    antwort = asyncio.run(get_effects())
    assert antwort["fields"] == FIELD_EFFECTS
    assert "areas" in antwort
