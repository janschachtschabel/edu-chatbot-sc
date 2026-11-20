"""Plan 2026-11-20, G2: die Führung als Ablauf Zug für Zug gegen die eingebaute Tour.

Beide Maschinen laufen echt und bekommen dieselben Eingaben, wie das Widget sie schickt: den
Tour-Chip der Begrüßung (``Web-Tour starten`` mit ``tour_action: start``), einen Klick auf einen
Chip, getippten Text und einen Seitenaufruf. Die Tour bekommt ihn als Tick, solange sie läuft;
der Ablauf als Seiten-Ping, solange sein Stand es verlangt (``wartet_seite``, an der Frage einer
Führung auch ``wartet_wahl``). Verglichen wird je Zug, was erscheint: Text, Chips (Beschriftung,
Reihenfolge, Ziel) — oder dass der Zug an die KI geht. Die Tour läuft ohne ``base_host`` (wie der
Erzeuger ``scripts/fuehrung_aus_tour.py``), ihre Links sind dann so relativ wie die des Ablaufs.

Ändert jemand eine Seite (Tour-Seed, Erzeuger, Führungs-Seed oder Baukasten), fällt es hier auf.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from boerdi.api.schemas import ChatRequest, ChatResponse, Environment, SafetyDecision
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import preflight as preflight_mod
from boerdi.graph.nodes import tour as tour_mod
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import fortschritt, seite_zug
from boerdi.services.rate_limits import RateVerdict
from boerdi.services.safety.regex_gate import regex_gate
from tests.test_ablauf_zug import _S, umgebung  # noqa: F401 — Fixture
from tests.test_fuehrung_wie_tour import CFG, ROH

_SID = "sitzung-0123456789"
#: Was der Tour-Chip schickt (``frontend/…/tour.controller.ts``).
_TOUR_START = "Web-Tour starten"
KI = "→ KI"
#: Kein Zug: das Widget schickt nichts (keine laufende Tour, kein Stand, der pingt).
_NICHTS = ChatResponse(session_id=_SID, content="")

# Ein Weg: Startseite und Sprache, dann Eingaben — („seite“, Pfad), („chip“, Beschriftung),
# („alter_chip“, Beschriftung eines Chips aus einer früheren Antwort), („text“, getippt),
# („start“, Pfad: der Tour-Chip erneut).
WEGE: dict[str, tuple[str, str, list[tuple[str, str]]]] = {
    "voll_lehrkraft": ("de", "/impressum/", [
        ("seite", "/home/"), ("chip", "Lehrkraft"), ("seite", "/home/oer-community/"),
        ("seite", "/bildungsinhalte/"), ("seite", "/fachportale/"), ("seite", "/impressum/"),
        ("seite", "/mitmachen/")]),
    "neu_laden_in_gruppenwahl": ("de", "/home/", [("seite", "/home/"), ("chip", "Redaktionen")]),
    "seitenwechsel_in_gruppenwahl": ("de", "/home/", [("seite", "/impressum/"),
                                                      ("chip", "Presse"),
                                                      ("seite", "/mitmachen/ueber-wlo/")]),
    "getippt_fehlversuch_dann_treffer": ("de", "/home/", [("text", "keine Ahnung"),
                                                          ("text", "Ich bin Lehrer")]),
    "unsicher_zweimal": ("de", "/home/", [("chip", "Bin mir nicht sicher"),
                                          ("chip", "Bin mir nicht sicher")]),
    "unsicher_dann_gruppe": ("de", "/home/", [("chip", "Bin mir nicht sicher"),
                                              ("chip", "Eltern")]),
    "unsicher_dann_fehlversuch": ("de", "/home/", [("chip", "Bin mir nicht sicher"),
                                                   ("text", "keine Ahnung")]),
    "fehlversuch_dann_unsicher": ("de", "/home/", [("text", "keine Ahnung"),
                                                   ("chip", "Bin mir nicht sicher")]),
    "fehlversuch_zweimal": ("de", "/home/", [("text", "keine Ahnung"), ("text", "Impressum")]),
    "einstieg_zielgruppenseite": ("de", "/home/redaktionen/", [
        ("seite", "/angebote/bildungs-api/"), ("seite", "/home/redaktionen/"),
        ("seite", "/mitmachen/faq/"), ("seite", "/mitmachen/")]),
    "einstieg_angebotsseite": ("de", "/angebote/bildungs-api/", [("seite", "/mitmachen/")]),
    "einstieg_mitmachen": ("de", "/mitmachen/", []),
    "ausloeser_waehrend_warten": ("de", "/impressum/", [("text", "starte die tour")]),
    "ausloeser_in_gruppenwahl": ("de", "/home/", [("text", "starte die tour"),
                                                  ("text", "starte die tour")]),
    "freitext_beim_warten": ("de", "/impressum/", [("text", "Was ist OER?"),
                                                    ("seite", "/home/")]),
    "neustart_mitten_drin": ("de", "/home/", [("chip", "Lehrkraft"),
                                              ("seite", "/home/oer-community/"),
                                              ("start", "/home/oer-community/")]),
    "nach_ende_neu": ("de", "/mitmachen/", [("start", "/home/")]),
    "englisch_voll": ("en", "/home/", [("chip", "Teachers"), ("seite", "/home/oer-community/"),
                                       ("seite", "/bildungsinhalte/"), ("seite", "/mitmachen/")]),
    "englisch_unsicher": ("en", "/home/", [("chip", "I'm not sure"), ("text", "Parents")]),
    # Review G2 (MINOR 4): die fehlenden Wege
    "nudge_im_zwischenstopp": ("de", "/home/", [("chip", "Lehrkraft"),
                                                ("seite", "/home/oer-community/"),
                                                ("seite", "/impressum/"),
                                                ("seite", "/bildungsinhalte/")]),
    "fehlversuch_seite_fehlversuch": ("de", "/home/", [("text", "keine Ahnung"),
                                                       ("seite", "/impressum/"),
                                                       ("text", "auch nicht")]),
    "fehlversuch_tour_chip_fehlversuch": ("de", "/home/", [("text", "keine Ahnung"),
                                                           ("start", "/home/"),
                                                           ("text", "auch nicht")]),
    "tour_chip_in_gruppenwahl": ("de", "/home/", [("start", "/home/redaktionen/")]),
    "home_ohne_schraegstrich": ("de", "/home", [("chip", "Lehrkraft")]),
    "einstieg_mitmachen_unterseite": ("de", "/mitmachen/faq/", []),
    "englisch_unsicher_zweimal": ("en", "/home/", [("chip", "I'm not sure"),
                                                   ("chip", "I'm not sure")]),
    "unsicher_seite_unsicher": ("de", "/home/", [("chip", "Bin mir nicht sicher"),
                                                 ("seite", "/impressum/"),
                                                 ("chip", "Bin mir nicht sicher")]),
    "krise_in_gruppenwahl": ("de", "/home/", [("text", "ich will nicht mehr leben")]),
    "krise_beim_warten": ("de", "/impressum/", [("text", "ich will nicht mehr leben"),
                                                 ("seite", "/home/")]),
    "alter_chip_nach_der_wahl": ("de", "/home/", [("chip", "Bin mir nicht sicher"),
                                                  ("chip", "Lehrkraft"),
                                                  ("alter_chip", "Bin mir nicht sicher")]),
    "ausloeser_im_einstieg_loesungen": ("de", "/home/redaktionen/", [("text", "starte die tour")]),
    "ausloeser_nach_umschau": ("de", "/home/redaktionen/", [("seite", "/angebote/bildungs-api/"),
                                                            ("text", "starte die tour")]),
    "gruppe_im_seitenschritt_getippt": ("de", "/home/", [("chip", "Lehrkraft"),
                                                         ("text", "Eltern")]),
    "englisch_ausloeser_in_gruppenwahl": ("en", "/home/", [("text", "start the tour"),
                                                           ("text", "start the tour")]),
    "umschau_dann_ausloeser_intro": ("de", "/impressum/", [("seite", "/impressum/"),
                                                           ("text", "rundgang")]),
}


def _sichtbar(antwort: ChatResponse | None) -> tuple[str, list[tuple[str, str]]] | str:
    """Was die Person sieht: Text und Chips (Beschriftung, Ziel) — oder ``KI``. Eine leere
    Antwort zeigt das Widget nicht."""
    if antwort is None:
        return KI
    chips = []
    for qr in antwort.quick_replies or []:
        teile = qr.split("|")
        if teile[0] in ("__guide__", "__fuehrung__"):
            chips.append((teile[1], teile[2]))
        else:
            chips.append((teile[1] if teile[0] == "__action__" else qr, ""))
    if not (antwort.content or "").strip() and not chips:
        return ("", [])
    return antwort.content.strip(), chips


@dataclass
class _Tour:
    sprache: str
    zustand: dict[str, Any] = field(default_factory=dict)
    letzte: ChatResponse | None = None
    frueher: list[str] = field(default_factory=list)

    def zug(self, message: str, seite: str, aktion: str | None = None):
        ctx = state_mod.TurnContext(req=ChatRequest(
            session_id=_SID, message=message, environment=Environment(
                tour_action=aktion, page=seite, locale="en-US" if self.sprache == "en" else "de")))
        ctx.session_state = {"tour_state": dict(self.zustand)}
        gespeichert: list[dict[str, Any]] = []

        async def speichern(_session, _sid, *, tour_state, **_k):
            gespeichert.append(dict(tour_state))

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(tour_mod, "update_session", speichern)
            antwort = asyncio.run(tour_mod.tour(ctx, object())).early_response
        if gespeichert:          # der Zustand, wie die Tour ihn festschreibt (mit ``misses``)
            self.zustand = gespeichert[-1]
        if antwort is not None:
            self.letzte = antwort
            self.frueher += antwort.quick_replies or []
        return antwort

    def eingabe(self, art: str, wert: str, seite: str):
        if art == "alter_chip":
            assert wert in self.frueher, wert
            return self.zug(wert, seite)
        if art == "seite":
            # das Widget tickt nur, solange die letzte Antwort die Tour als aktiv meldete
            return self.zug("[tour-tick]", wert, "tick") if self.zustand.get("active") else _NICHTS
        if art == "start":
            return self.zug(_TOUR_START, wert, "start")
        return self.zug(wert, seite)     # Chip (Text) oder getippt


@dataclass
class _Ablauf:
    sprache: str
    zustand: dict[str, Any] = field(default_factory=lambda: {"entities": {}})
    letzte: ChatResponse | None = None
    frueher: list[str] = field(default_factory=list)

    def _req(self, message: str, seite: str, **mehr) -> ChatRequest:
        env = {"page": seite, "locale": "en-US" if self.sprache == "en" else "de",
               **mehr.pop("env", {})}
        return ChatRequest(session_id=_SID, message=message, environment=Environment(**env),
                           **mehr)

    def _preflight(self, req: ChatRequest):
        """Der echte Vorlauf-Knoten (Sicherheitsprüfung nur mit dem Regex-Gate, ohne Netz):
        ``early_response`` oder ``None`` — dann ginge der Zug an die KI."""
        ctx = state_mod.TurnContext(req=req, session_state=self.zustand)
        aus = asyncio.run(preflight_mod.preflight(ctx, _S()))
        self.zustand = aus.session_state
        antwort = aus.early_response
        if antwort is not None:
            self.letzte = antwort
            self.frueher += antwort.quick_replies or []
        return antwort

    def _stand(self) -> dict[str, Any] | None:
        return fortschritt.stand(self.zustand["entities"], arbeitsstand.aufrufer_fuer(_SID),
                                 self.sprache)

    def eingabe(self, art: str, wert: str, seite: str):
        if art == "seite":
            stand = self._stand() or {}
            pingt = stand.get("status") == "wartet_seite" or (
                stand.get("status") == "wartet_wahl" and stand.get("fuehrung"))
            if not pingt:
                return _NICHTS
            antwort = asyncio.run(seite_zug.angekommen(_S(), self._req(
                "[ablauf-seite]", wert, env={"page_event": seite_zug.PING}), self.zustand))
            if (antwort.content or "").strip():
                self.letzte = antwort
                self.frueher += antwort.quick_replies or []
            return antwort
        if art == "start":
            return self._preflight(self._req(_TOUR_START, wert, env={"tour_action": "start"}))
        if art in ("chip", "alter_chip"):
            chips = (self.letzte.quick_replies if self.letzte else []) if art == "chip" \
                else self.frueher
            for qr in chips:
                _praefix, label, aktion, params = qr.split("|", 3)
                if label == wert:
                    return self._preflight(self._req(label, seite, action=aktion,
                                                     action_params=json.loads(params)))
            raise AssertionError(f"kein Chip {wert!r}")
        return self._preflight(self._req(wert, seite))


@pytest.fixture
def maschinen(umgebung, monkeypatch):  # noqa: F811 — Fixture
    async def nichts(*_a, **_k):
        return None

    async def frei(*_a, **_k):
        return RateVerdict(allowed=True)

    async def regex(text, signals, **_k):     # das Krisen-Gate offline, ohne Moderation
        hart = regex_gate(text, signals or []).enforced_pattern
        return SafetyDecision(risk_level="high" if hart else "low")

    monkeypatch.setattr(tour_mod, "load_website_tour_config", lambda: dict(CFG))
    monkeypatch.setattr(tour_mod, "save_message", nichts)
    monkeypatch.setattr(preflight_mod, "check_rate_limit", frei)
    monkeypatch.setattr(preflight_mod, "assess_safety", regex)
    monkeypatch.setattr(preflight_mod, "log_safety_event", nichts)
    monkeypatch.setattr(preflight_mod, "save_message", nichts)
    umgebung.katalog["wert"] = {"ablaeufe": [{**ROH, "aktiv": True}]}
    return umgebung


def _chip_der_tour(t: _Tour, wert: str) -> None:
    """Der Chip muss in der Tour dastehen — sonst prüfte der Weg etwas, das niemand klicken kann."""
    assert wert in (t.letzte.quick_replies if t.letzte else []), wert


@pytest.mark.parametrize("name", sorted(WEGE))
def test_jeder_zug_zeigt_dasselbe_wie_die_tour(maschinen, name):
    sprache, start, eingaben = WEGE[name]
    t, a = _Tour(sprache), _Ablauf(sprache)
    zuege = [("start", start), *eingaben]
    seite = start
    for nr, (art, wert) in enumerate(zuege):
        if art == "chip":
            _chip_der_tour(t, wert)
        tour = _sichtbar(t.eingabe(art, wert, seite))
        ablauf = _sichtbar(a.eingabe(art, wert, seite))
        assert ablauf == tour, f"{name}, Zug {nr} ({art} {wert!r})"
        if art in ("seite", "start"):
            seite = wert


# ── Review G2 (MAJOR 1/2): neben einem anderen wartenden Ablauf — die Tour kennt keinen ──────────

_ANDERER = {"id": "anderer", "titel": {"de": "Anderer"}, "aktiv": True,
            "ausloeser": [{"art": "knopf"}],
            "schritte": [{"id": "f", "typ": "nachricht", "text": {"de": "Wozu?"},
                          "schreibt": "zweck",
                          "optionen": [{"id": "a", "label": {"de": "A"}, "ziel": "e"}],
                          "freitext": {"schreibt": "zweck", "ziel": "e"}},
                         {"id": "e", "typ": "ende", "text": {"de": "Fertig."}}]}


def _anderer_startet(maschinen, a: _Ablauf) -> None:  # noqa: F811
    from boerdi.services.ablauf import zug

    maschinen.katalog["wert"] = {"ablaeufe": [{**ROH, "aktiv": True}, _ANDERER]}
    asyncio.run(zug.starten(_S(), a._req("", "/home/", action=zug.AKTION,
                                         action_params={"ablauf": "anderer"}), a.zustand))
    assert (a._stand() or {}).get("id") == "anderer"


def test_der_tour_chip_fragt_erst_wenn_ein_anderer_ablauf_wartet(maschinen):  # noqa: F811
    from boerdi.i18n import bot_text

    a = _Ablauf("de")
    _anderer_startet(maschinen, a)
    antwort = a.eingabe("start", "/home/", "/home/")
    assert [q.split("|")[1] for q in antwort.quick_replies] == [
        bot_text("de", "action.ablauf.neuStarten"), bot_text("de", "action.ablauf.hierWeiter")]
    assert (a._stand() or {}).get("id") == "anderer"


def test_ein_alter_chip_der_fuehrung_beantwortet_keinen_anderen_ablauf(maschinen):  # noqa: F811
    from boerdi.i18n import bot_text

    a = _Ablauf("de")
    a.eingabe("start", "/home/", "/home/")                  # Führung: Gruppenwahl mit Chips
    _anderer_startet(maschinen, a)
    antwort = a.eingabe("alter_chip", "Bin mir nicht sicher", "/home/")
    assert antwort.content == bot_text("de", "action.ablauf.wahlVeraltet")
    assert [q.split("|")[1] for q in antwort.quick_replies] == ["A"]
    assert (a._stand() or {}).get("status") == "wartet_wahl"
    assert not [t for t in (a._stand() or {}).get("teile") or [] if t["name"] == "zweck"]
