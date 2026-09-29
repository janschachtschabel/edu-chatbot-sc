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
    # Ihre einzigen Leser (`domain/canvas/intent.py`) ruft kein Produktionscode.
    for area in ("05-canvas/create-triggers", "05-canvas/edit-triggers"):
        assert AREA_EFFECTS[area] == {"pattern": "keine", "agent": "keine"}, area
    # Die Klassifikator-Achsen: die Agent-Schleife klassifiziert nicht.
    assert AREA_EFFECTS["04-intents/intents"] == {"pattern": "voll", "agent": "keine"}
