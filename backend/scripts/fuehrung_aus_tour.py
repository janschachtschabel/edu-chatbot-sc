"""Die Führung als Ablauf (``seeds/06-ablaeufe/fuehrung.yaml``) aus der eingebauten Web-Tour
erzeugen (``seeds/01-base/website-tour.yaml``).

Rückmeldung 16.11.: Die Führung soll dieselben Texte und Verzweigungen haben wie die eingebaute
Tour. Darum schreibt dieses Skript die Texte nicht nach, sondern lässt sie von der Tour selbst
erzeugen (``domain/tour.render`` mit ``tour_i18n.localize``, ohne ``base_host``). Der Einstieg je
Seite folgt ``detect_entry``, die Ankunft und die Umschau-Seiten folgen ``expected``.
``tests/test_fuehrung_wie_tour.py`` hält beides gleich.

Aufruf aus ``backend``:  ``uv run python scripts/fuehrung_aus_tour.py``
Ändert die Redaktion die eingebaute Tour, gilt die Führung in ihrer Fassung weiter, bis jemand das
Skript neu laufen lässt.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from boerdi.domain import (
    seiten_muster,  # noqa: E402
    tour,  # noqa: E402
)
from boerdi.domain.tour_i18n import localize  # noqa: E402

BACKEND = pathlib.Path(__file__).resolve().parents[1]
QUELLE = BACKEND / "seeds" / "01-base" / "website-tour.yaml"
ZIEL = BACKEND / "seeds" / "06-ablaeufe" / "fuehrung.yaml"
SPRACHEN = ("de", "en")


def tour_config() -> dict[str, Any]:
    """Die Tour wie im Zug, nur ohne ``base_host``: Links und Chips bleiben relative Pfade."""
    cfg = yaml.safe_load(QUELLE.read_text(encoding="utf-8"))["website_tour"]
    return {**cfg, "base_host": ""}


def sid(gruppe: str) -> str:
    return gruppe.replace("-", "_")


def _je_sprache(cfg: dict[str, Any], schritt: str, gruppe: str = "", art: str = "normal"
                ) -> dict[str, dict[str, Any]]:
    return {s: tour.render(schritt, localize(cfg, s), gruppe, kind=art) for s in SPRACHEN}


def _text(gerendert: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {s: r["text"] for s, r in gerendert.items()}


def _chip(gerendert: dict[str, dict[str, Any]]) -> tuple[dict[str, str], str]:
    """Der eine Weiter-Chip ``__guide__|Label|Pfad`` → (Label je Sprache, Pfad)."""
    teile = {s: r["quick_replies"][0].split("|") for s, r in gerendert.items()}
    pfade = {t[2] for t in teile.values()}
    if len(pfade) != 1:
        raise ValueError(f"Der Weiter-Chip führt je Sprache woandershin: {sorted(pfade)}")
    return {s: t[1] for s, t in teile.items()}, pfade.pop()


def einstiege(cfg: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Jede Seite, auf der ``detect_entry`` mitten einsteigt → (Schritt, Gruppe)."""
    kandidaten = [cfg["home_path"], cfg["contact_hub"]]
    for g in cfg["groups"]:
        kandidaten += [g["page"], *(a["path"] for a in g.get("angebote") or [])]
    return {tour._norm_path(p): tour.detect_entry(p, cfg) for p in kandidaten}


def _seiten_schritt(sid_: str, gerendert: dict[str, dict[str, Any]], weiter: str,
                    nudge: dict[str, str], ankunft: str,
                    umsehen: tuple[list[str], dict[str, str]] | None = None) -> dict[str, Any]:
    label, url = _chip(gerendert)
    schritt: dict[str, Any] = {"id": sid_, "typ": "seite", "text": _text(gerendert), "url": url,
                               "label": label, "ankunft": [ankunft], "abweichung": nudge}
    if umsehen:
        schritt["umsehen"] = {"muster": umsehen[0], "text": umsehen[1]}
    schritt["weiter"] = weiter
    return schritt


def erzeugen(cfg: dict[str, Any]) -> dict[str, Any]:
    gruppen = [g["id"] for g in cfg["groups"]]
    unsicher_label = {s: localize(cfg, s)["steps"]["group"]["unsure_label"] for s in SPRACHEN}
    nudge = _text(_je_sprache(cfg, "intro", art="nudge"))
    explore = _text(_je_sprache(cfg, "solutions", gruppen[0], art="explore"))
    kontakt_pfad = tour._norm_path(cfg["contact_hub"])

    # ── Einstieg je Seite (detect_entry) ──────────────────────────────────────────────────
    je_ziel: dict[str, list[str]] = {}
    for pfad, (schritt, gruppe) in einstiege(cfg).items():
        if schritt == "solutions":
            je_ziel.setdefault(f"einstieg_{sid(gruppe)}", []).append(pfad)
    einstieg_gruppen = [g for g in gruppen if f"einstieg_{sid(g)}" in je_ziel]
    wo: list[dict[str, Any]] = [{"wenn_seite": [tour._norm_path(cfg["home_path"])],
                                 "dann": "gruppe"}]
    for g in einstieg_gruppen:
        pfade = je_ziel[f"einstieg_{sid(g)}"]
        for i in range(0, len(pfade), seiten_muster.MAX_MUSTER):
            wo.append({"wenn_seite": pfade[i:i + seiten_muster.MAX_MUSTER],
                       "dann": f"einstieg_{sid(g)}"})
    wo += [{"wenn_seite": [kontakt_pfad + "/*"], "dann": "kontakt"}, {"sonst": "intro"}]
    schritte: list[dict[str, Any]] = [{"id": "wo", "typ": "verzweigung", "weiter": wo}]

    # ── Intro → Startseite ────────────────────────────────────────────────────────────────
    adv, _, _ = tour.expected("intro", "", cfg)
    schritte.append(_seiten_schritt("intro", _je_sprache(cfg, "intro"), "gruppe", nudge, adv))

    # ── Gruppenwahl; „Bin mir nicht sicher“ und der erste Fehlversuch zeigen den Hilfetext ─
    optionen = []
    for g in cfg["groups"]:
        optionen.append({"id": sid(g["id"]),
                         "label": {s: localize(cfg, s)["groups"][gruppen.index(g["id"])]["label"]
                                   for s in SPRACHEN},
                         "ziel": "zur_gruppenseite",
                         "synonyme": [w for w in dict.fromkeys(g.get("synonyms") or [])
                                      if len(w) >= 3]})
    optionen.append({"id": "unsicher", "label": unsicher_label, "ziel": "unsicher"})
    unsicher = _text(_je_sprache(cfg, "group", art="unsure"))
    schritte.append({"id": "gruppe", "typ": "nachricht", "text": _text(_je_sprache(cfg, "group")),
                     "schreibt": "gruppe", "optionen": optionen, "kein_treffer": unsicher})
    # Nach dem Hilfetext beendet der nächste Fehlversuch die Führung (endet_bei_text) — wie im
    # Original, das den Hilfetext als ersten Fehlversuch zählt.
    schritte.append({"id": "unsicher", "typ": "nachricht", "text": unsicher,
                     "schreibt": "gruppe", "optionen": optionen})

    # ── Zielgruppenseite je Gruppe ────────────────────────────────────────────────────────
    schritte.append({"id": "zur_gruppenseite", "typ": "verzweigung", "weiter": [
        *({"wenn_gewaehlt": sid(g), "dann": f"seite_{sid(g)}"} for g in gruppen),
        {"sonst": "kontakt"}]})   # ohne Wahl (nicht erreichbar): zum Ziel, kein Rückweg
    for g in gruppen:
        adv, _, _ = tour.expected("group_page", g, cfg)
        schritte.append(_seiten_schritt(f"seite_{sid(g)}", _je_sprache(cfg, "group_page", g),
                                        "inhalte", nudge, adv))

    # ── Zwischenstopp Bildungsinhalte (ein Schritt für alle; {group} → {wahl.gruppe}) ─────
    adv, _, _ = tour.expected("content", gruppen[0], cfg)
    schritte.append(_seiten_schritt("inhalte", {
        s: tour.render("content", _mit_platzhalter(localize(cfg, s)), "__wahl__")
        for s in SPRACHEN}, "zu_loesungen", nudge, adv))
    schritte.append({"id": "zu_loesungen", "typ": "verzweigung", "weiter": [
        *({"wenn_gewaehlt": sid(g), "dann": f"loesungen_{sid(g)}"} for g in gruppen),
        {"sonst": "kontakt"}]})

    # ── Lösungen je Gruppe, und derselbe Halt beim Einstieg mitten drin ───────────────────
    def loesungen(sid_: str, g: str, art: str) -> dict[str, Any]:
        adv, umschau, _ = tour.expected("solutions", g, cfg)
        return _seiten_schritt(sid_, _je_sprache(cfg, "solutions", g, art), "kontakt", nudge,
                               adv, (list(dict.fromkeys(umschau)), explore))

    schritte += [loesungen(f"loesungen_{sid(g)}", g, "normal") for g in gruppen]
    schritte += [loesungen(f"einstieg_{sid(g)}", g, "entry") for g in einstieg_gruppen]

    # ── Mitmach-Seite (Ziel) ──────────────────────────────────────────────────────────────
    schritte.append({"id": "kontakt", "typ": "ende", "text": _text(_je_sprache(cfg, "contact"))})

    phrasen = list(dict.fromkeys(p.lower() for p in cfg["trigger_phrases"] if len(p) >= 3))
    return {
        "id": "fuehrung",
        "titel": {"de": "Führung durch WLO", "en": "Tour of WLO"},
        "beschreibung": ("Nachbau der eingebauten Web-Tour mit denselben Texten und "
                         "Verzweigungen: Selbstzuordnung, die Seite der eigenen Gruppe, die "
                         "Bildungsinhalte, passende Angebote und am Ende die Mitmach-Seite. Steigt "
                         "wie die Tour mitten ein, wenn die Person schon auf einer Zielgruppen-, "
                         "Angebots- oder Mitmach-Seite ist."),
        "wann": ["Die Person möchte WLO kennenlernen, eine Führung über die Webseite oder sucht "
                 "den Weg zum Mitmachen"],
        "aktiv": False,
        "endet_bei_text": True,
        "ausloeser": [{"art": "knopf"},
                      *({"art": "text", "wendungen": phrasen[i:i + 10]}
                        for i in range(0, len(phrasen), 10))],
        "schritte": schritte,
        "tests": _tests(cfg),
    }


def _mit_platzhalter(cfg: dict[str, Any]) -> dict[str, Any]:
    """Eine Gruppe ``__wahl__`` mit dem Label ``{wahl.gruppe}`` — der Zwischenstopp ist ein
    Schritt für alle Gruppen, der Ablauf setzt die Beschriftung der Wahl in der Sprache ein."""
    erste = cfg["groups"][0]
    return {**cfg, "groups": [*cfg["groups"],
                              {**erste, "id": "__wahl__", "label": "{wahl.gruppe}"}]}


def _tests(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    gruppen = [g["id"] for g in cfg["groups"]]
    erste = sid(gruppen[0])
    return [
        {"name": "Von der Startseite mit Chip bis zur Anfrage", "seite": "/home/",
         "eingaben": [{"bei": "gruppe", "option": erste},
                      {"bei": f"seite_{erste}", "seite": "/home/redaktionen/"},
                      {"bei": "inhalte", "seite": "/bildungsinhalte/"},
                      {"bei": f"loesungen_{erste}", "seite": "/mitmachen/"}],
         "erwartet": {"weg": ["wo", "gruppe", "zur_gruppenseite", f"seite_{erste}", "inhalte",
                              "zu_loesungen", f"loesungen_{erste}", "kontakt"],
                      "status": "fertig"}},
        {"name": "Getippte Gruppe trifft wie in der Tour über Synonyme", "seite": "/home/",
         "eingaben": [{"bei": "gruppe", "text": "Ich bin Lehrer"}],
         "erwartet": {"weg": ["wo", "gruppe", "zur_gruppenseite", "seite_lehrkraft"],
                      "ende": "seite_lehrkraft"}},
        {"name": "Unbekannte Seite: erst zur Startseite", "seite": "/impressum/",
         "erwartet": {"status": "wartet_seite", "ende": "intro"}},
        {"name": "Bin mir nicht sicher: Hilfetext mit denselben Chips", "seite": "/home/",
         "eingaben": [{"bei": "gruppe", "option": "unsicher"}],
         "erwartet": {"weg": ["wo", "gruppe", "unsicher"], "ende": "unsicher"}},
        {"name": "Auf einer Zielgruppenseite: Einstieg bei den Lösungen",
         "seite": "/home/redaktionen/",
         "erwartet": {"weg": ["wo", "einstieg_redaktionen"], "status": "wartet_seite",
                      "ende": "einstieg_redaktionen"}},
        {"name": "Auf einer Angebotsseite: Einstieg bei der Gruppe, die es zuerst nennt",
         "seite": "/angebote/bildungs-api/",
         "erwartet": {"weg": ["wo", "einstieg_abnehmer"], "ende": "einstieg_abnehmer"}},
        {"name": "Schon auf der Mitmach-Seite", "seite": "/mitmachen/",
         "erwartet": {"weg": ["wo", "kontakt"], "status": "fertig"}},
    ]


KOPF = """\
# Ablauf „Führung durch WLO“ — Nachbau der eingebauten Web-Tour mit denselben Texten und
# Verzweigungen. ERZEUGT von backend/scripts/fuehrung_aus_tour.py aus 01-base/website-tour.yaml
# (die Texte kommen aus domain/tour.render) — nicht von Hand ändern, sondern das Skript neu laufen
# lassen. tests/test_fuehrung_wie_tour.py vergleicht beide.
#
# Das Skript liest den Seed website-tour.yaml, nicht eine im Studio geänderte Tour: Ändert die
# Redaktion die Tour im Studio, bleibt die Führung, bis jemand den Seed nachzieht und das Skript
# neu laufen lässt.
#
# Was eine Führung als Ablauf anders macht als die eingebaute Tour:
# - Pfade relativ statt base_host — der Chip und die Links in den Texten öffnen die Seite auf dem
#   Host, auf dem das Widget läuft (in einer Studio-Probe oder Fremdeinbettung der Chatbot-Host).
# - Die Ablauf-Leiste („Schritt n von m“, „Ablauf abbrechen“) steht über dem Chat.
# - Das Widget öffnet sich von selbst, solange ein Seiten-Schritt wartet (die Tour in jedem
#   Schritt); ein Seitenwechsel während der Gruppenwahl zeigt die Wahl nicht erneut.
# - „Bin mir nicht sicher“ im Hilfetext zeigt den Hilfetext noch einmal; die Tour endete dort.
# - Die Antworten tragen nicht das Etikett „KI-generierte Antwort“ (fester Text der Redaktion).
#
# Aus, bis die Redaktion sie einschaltet (aktiv) und die eingebaute Tour abschaltet
# (Tour & Lotse: website_tour.enabled = false).
"""


def main() -> None:
    from boerdi.domain.config_models.ablauf import AblaufArea
    from boerdi.services.ablauf.pruefung import pruefe

    ablauf = erzeugen(tour_config())
    # Review 16.11., m6: an den Grenzen der Prüfung (40 Schritte, 12 Optionen, 10 Muster) — eine
    # weitere Gruppe in der Tour ergäbe einen ungültigen Ablauf; dann nichts schreiben
    if befunde := pruefe(AblaufArea.model_validate(ablauf)):
        raise SystemExit("Die erzeugte Führung besteht die Prüfung nicht:\n- "
                         + "\n- ".join(befunde))
    ZIEL.write_text(KOPF + yaml.safe_dump(ablauf, allow_unicode=True, sort_keys=False, width=100),
                    encoding="utf-8")
    print("Schritte:", len(ablauf["schritte"]))


if __name__ == "__main__":
    main()
