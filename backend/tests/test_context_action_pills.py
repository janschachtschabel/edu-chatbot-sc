"""P7: die Knopf-Listen je Seitenart — und was sie wirklich auslösen.

Nutzer-Vorgabe 2026-08-13, eine Liste je Seitenart. Der Haken steht schon im
Kopf von ``01-base/context-actions.yaml``: bei ``kind: text`` **IST die
Beschriftung die gesendete Nachricht**. Eine Zeile, die gut klingt, aber ihr
Muster verfehlt, ist eine Schaltfläche, die nichts tut — und nichts an ihr
verrät das.

Diese Datei hält die drei Stellen fest, an denen das beim Bauen nachgemessen
wurde. Ohne sie wäre jede spätere „Verbesserung" der Beschriftung ein stiller
Rückschritt.
"""

from __future__ import annotations

import json
import pathlib

import pytest
import yaml

from boerdi.domain.lp_intent import _lp_keywords
from boerdi.graph.nodes.preflight import _DIRECT_ACTIONS
from boerdi.services.config_loader.widget import _CONTEXT_ACTIONS_DEFAULT_PILLS

_ARTEN = ("collection", "content", "topic", "search", "home", "external",
          "editorial")
_SEEDS = pathlib.Path(__file__).resolve().parents[1] / "seeds" / "01-base"


def _seed(datei: str) -> dict:
    """Der Seed, nicht ``load_*``.

    Gemessen beim Bau von P7: ohne Datenbankeintrag liefert der Loader die
    **Code-Vorgabe** (``config_loader.widget``), nicht die Seed-Datei —
    ``load_website_tour_config()`` gibt dort ``enabled: False`` und *keine*
    Trigger-Phrasen zurück. Ein Test gegen den Loader prüfte also je nach
    Umgebung etwas anderes. Der Seed ist, was die Redaktion pflegt und was der
    Import in die Datenbank schreibt; er ist hier die Quelle.
    """
    text = (_SEEDS / datei).read_text(encoding="utf-8")
    geladen = yaml.safe_load(text) or {}
    # Die Bereichsdateien tragen einen Wurzelschlüssel (``context_actions:``).
    return next(iter(geladen.values())) if len(geladen) == 1 else geladen


def _pills(art: str) -> list[dict]:
    return list((_seed("context-actions.yaml").get("pills") or {}).get(art) or [])


def _labels(art: str, kind: str | None = None) -> list[str]:
    return [str(p.get("label") or "") for p in _pills(art)
            if kind is None or p.get("kind") == kind]


# ── Befund 1: der Lernpfad-Schnellweg frisst „Unterrichtsstunde" ─────────
# ``lp_intent._lp_keywords`` wird als TEILZEICHENKETTE geprüft, und der
# Schnellweg läuft VOR der Musterwahl. Ein Chip „Unterrichtsstunde planen"
# landete also nie bei M09 — und damit nie bei der Freigabeliste der Sammlung,
# die P1/P2 gerade erst dorthin gebracht haben. „Stunde planen" enthält kein
# Stichwort und ist zugleich der wörtliche Titel des Skills.


@pytest.mark.parametrize("art", ["collection", "topic", "editorial"])
def test_kein_text_chip_faellt_in_den_lernpfad_schnellweg(art):
    for label in _labels(art, "text"):
        low = label.lower()
        treffer = [kw for kw in _lp_keywords if kw in low]
        assert not treffer, (
            f"{art}: {label!r} enthaelt {treffer} — der LP-Schnellweg feuert vor "
            "der Musterwahl, das Muster (und damit der Skill) kaeme nie zum Zug"
        )


def test_die_stundenplanung_steht_trotzdem_auf_der_sammlung():
    # Gegenprobe: der Wächter darüber wäre auch grün, wenn der Knopf fehlte.
    assert any("stunde planen" in text.lower() for text in _labels("collection", "text"))


# ── Befund 2: die Webseiten-Tour hat einen HARTEN Auslöser ───────────────
# ``graph/nodes/tour.py`` prüft die Nachricht gegen ``website-tour.yaml
# trigger_phrases`` (Teilzeichenkette, klein geschrieben). Anders als bei den
# Mustern entscheidet hier kein Klassifikator: trifft die Beschriftung keine
# Phrase, passiert schlicht nichts.


def _tour_phrasen() -> list[str]:
    return [str(t).strip().lower()
            for t in (_seed("website-tour.yaml").get("trigger_phrases") or [])
            if str(t).strip()]


def test_der_tour_knopf_trifft_eine_konfigurierte_phrase():
    phrasen = _tour_phrasen()
    assert phrasen, "keine Trigger gepflegt — Test prüft nichts"
    tour = [p for p in _pills("home") if "tour" in str(p.get("label") or "").lower()]
    assert len(tour) == 1, "genau ein Tour-Knopf erwartet"
    for schluessel in ("label", "label_en"):
        text = str(tour[0].get(schluessel) or "").lower()
        assert any(ph in text for ph in phrasen), (
            f"{schluessel}={text!r} loest die Tour nicht aus — "
            f"keine der Phrasen {phrasen[:6]} steckt darin"
        )


# ── Befund 3: eine Aktion braucht die ID, die ihr Handler liest ──────────


def test_jede_aktion_ist_dem_dispatcher_bekannt():
    for art in _ARTEN:
        for pill in _pills(art):
            if pill.get("kind") != "action":
                continue
            aktion = str(pill.get("action") or "")
            assert aktion in _DIRECT_ACTIONS, f"{art}: {aktion} kennt der Dispatcher nicht"


def test_die_volltext_aktion_bekommt_eine_node_id(monkeypatch):
    """``show_content_text`` liest ``action_params['node_id']`` — der Dispatcher
    schrieb bis P7 nur ``collection_id``. Der Knopf wäre im Fehlerzweig gelandet
    („Ich brauche die ID des Inhalts"), ohne dass irgendwer es merkt."""
    from boerdi.graph.nodes import context_greeting as g

    pills = g._build_quick_replies(
        _seed("context-actions.yaml"), "content",
        {"page_kind": "content", "node_id": "N9"}, {"node_id": "N9"}, "Ein Arbeitsblatt",
    )
    volltext = [p for p in pills if "|show_content_text|" in p]
    assert len(volltext) == 1, "Volltext-Knopf fehlt auf der Inhaltsseite"
    params = json.loads(volltext[0].split("|", 3)[3])
    assert params["node_id"] == "N9"


# ── Die bestellten Listen ────────────────────────────────────────────────
# Festgehalten, weil sie eine Nutzer-Entscheidung sind und nicht mein Geschmack.


@pytest.mark.parametrize(("art", "erwartet"), [
    ("collection", ["Sammlungsinhalte zeigen", "Stunde planen",
                    "Sammlung kuratieren", "Zu Lehrplänen beraten"]),
    ("content", ["Mehr Details zeigen", "Volltext abrufen und bearbeiten",
                 "Inhalte remixen", "Ähnliche Inhalte suchen"]),
    ("topic", ["Themenseiteninhalte zeigen", "Stunde planen",
               "Sammlung kuratieren", "Zu Lehrplänen beraten"]),
    ("search", ["Videos zum Thema", "Arbeitsblätter zum Thema"]),
    ("home", ["Informiere mich über WLO", "Webseiten-Tour starten",
              "Inhalte finden", "Kontakt und mitmachen"]),
    # EK2 (2026-08-20): die drei bestellten Erschließungs-Angebote — Hinweise
    # zum Inhalt, Sammlungs-Suche, Kuratierungshilfe.
    ("editorial", ["Gib mir Hinweise zu diesem Inhalt",
                   "Such eine passende Sammlung für diesen Inhalt",
                   "Hilf mir beim Erschließen dieses Inhalts"]),
])
def test_die_bestellten_knoepfe_stehen_da(art, erwartet):
    vorhanden = _labels(art)
    for label in erwartet:
        assert label in vorhanden, f"{art}: {label!r} fehlt, da steht {vorhanden}"


def test_die_fremdseite_bleibt_woertlich_bei_m20():
    # Diese zwei Zeilen sind WÖRTLICH M20s trigger_phrases. Der Nutzer hat sie
    # ausdrücklich ausgenommen; frei formuliert löste der Chip sein Muster nicht.
    assert _labels("external") == [
        "Nimm diese Seite in WLO auf",
        "Was steht auf der Seite, und passt das zu uns",
    ]


def test_seed_und_code_vorgabe_bieten_dieselben_knoepfe():
    """Die Listen stehen ZWEIMAL — und liefen bereits auseinander.

    Ohne Datenbankeintrag greift ``_CONTEXT_ACTIONS_DEFAULT_PILLS``; mit
    importiertem Seed die YAML. Beim Bau von P7 gemessen: die Code-Vorgabe hatte
    **kein einziges** ``label_en``, die YAML für jeden Chip eines. Ein englischer
    Nutzer bekam auf einer frischen Anlage also deutsche Beschriftungen — und bei
    ``kind: text`` heisst das: deutschen Text in den Mund gelegt.

    Beides zu pflegen ist die Bestandslage (der Loader braucht eine Vorgabe, die
    Redaktion eine Datei). Dass sie dasselbe sagen, hält dieser Test.
    """
    seed_pills = (_seed("context-actions.yaml").get("pills") or {})
    assert set(seed_pills) == set(_CONTEXT_ACTIONS_DEFAULT_PILLS)
    for art in seed_pills:
        assert seed_pills[art] == _CONTEXT_ACTIONS_DEFAULT_PILLS[art], art


def test_jeder_text_chip_hat_eine_englische_fassung():
    # Bei ``kind: text`` ist die Beschriftung die Nachricht — eine fehlende
    # englische Fassung legte einem englischen Nutzer deutschen Text in den Mund
    # und vor den Klassifikator.
    for art in _ARTEN:
        for pill in _pills(art):
            if pill.get("kind") != "text":
                continue
            assert str(pill.get("label_en") or "").strip(), f"{art}: {pill.get('label')}"
