#!/usr/bin/env python
"""Messlauf zu Paket N3 mit echten WLO-Materialien (Review N3, MINOR 4).

Grundlage: ``tests/zuordnung_wlo_echt.json`` — 69 Materialien: 57 öffentliche aus der WLO-Suche
(``search_wlo_content``, Staging-MCP, lesend, 19.11.2026) zu Vulkane, Plattentektonik, Erdbeben,
Klima(wandel) und Wetter sowie fachfremde (Bruchrechnung, Satzglieder), dazu 12 abgeleitete
Einträge nur mit Titel bzw. nur mit Dateinamen. Benachbarte Störer sind gewollt (Wetter/Klima,
Vulkane/Plattentektonik); wo beide Punkte stimmen, nennt ``erwartet`` beide.

* **Einbettung allein** (Vorgabe): ein Aufruf für Punkte und Materialien. Die Schwelle wird NUR
  an der Kalibrierhälfte gewählt und an der Prüfhälfte geprüft — das ist das unabhängige Ergebnis.
  Geteilt wird nach Originalgruppen (zweites Review): ein Eintrag „nur Titel“ liegt in derselben
  Hälfte wie sein Original. Ausgegeben: die Prüfquote bei der kalibrierten Schwelle, zum Vergleich
  bei der eingestellten (``strukturentwurf_naehe.SCHWELLEN`` — nicht unabhängig, wenn sie aus allen
  Daten gewählt wurde), Fehlzuordnungen, Quote „nicht zugeordnet“, Quote der abgeleiteten Einträge.
* **Ganzer Entwurf** (``--entwurf``): ``aus_inhalten`` mit echtem Modell über alle Materialien und
  danach die Zuordnung — wie viele ordnet das Modell zu, wie viele die Einbettung, wie viele
  bleiben übrig.

Nur gegen OpenAI direkt (``LLM_PROVIDER=openai``). Kosten: ein Einbettungsaufruf (rund 6 000
Token); mit ``--entwurf`` rund acht Modellaufrufe.

    uv run python scripts/zuordnung_messen_echt.py [--entwurf]

Rückgabe: 0 = Prüfung ≥ 80 % richtig · 1 = verfehlt · 2 = falscher Anbieter.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from boerdi.obs.usage import new_accumulator
from boerdi.services import llm_einbettungen, strukturentwurf_naehe
from boerdi.services import strukturentwurf_zuordnung as zu
from boerdi.services.llm_models import get_embed_model
from boerdi.settings import get_settings

logging.basicConfig(level=logging.WARNING)
SOLL = 0.80
_DATEI = Path(__file__).resolve().parents[1] / "tests" / "zuordnung_wlo_echt.json"
PUNKTE = [
    {"id": "vulkane", "titel": "Vulkane", "beschreibung": "Aufbau, Arten und Ausbrüche von "
     "Vulkanen und ihre Folgen.", "kinder": [{"titel": "Vulkantypen"}, {"titel": "Ausbrüche"}]},
    {"id": "plattentektonik", "titel": "Plattentektonik", "beschreibung": "Lithosphärenplatten, "
     "ihre Bewegung und die Vorgänge an den Plattengrenzen.",
     "kinder": [{"titel": "Plattengrenzen"}, {"titel": "Gebirgsbildung"}]},
    {"id": "erdbeben", "titel": "Erdbeben", "beschreibung": "Entstehung, Messung und Folgen von "
     "Erdbeben und Tsunamis, Schutz davor.",
     "kinder": [{"titel": "Erdbebenwellen"}, {"titel": "Erdbebenschutz"}]},
    {"id": "klima", "titel": "Klimawandel", "beschreibung": "Treibhauseffekt, Ursachen und Folgen "
     "des Klimawandels, Klimaschutz.", "kinder": [{"titel": "Ursachen"}, {"titel": "Folgen"}]},
    {"id": "wetter", "titel": "Wetter", "beschreibung": "Wetterelemente, Wetterbeobachtung und "
     "extreme Wetterereignisse.",
     "kinder": [{"titel": "Wetterelemente"}, {"titel": "Extremwetter"}]},
]


def _laden() -> list[dict]:
    return json.loads(_DATEI.read_text(encoding="utf-8"))["materialien"]


def _teil(mats: list[dict]) -> dict:
    return {"format": "wlo.metadaten@1", "inhalte": [
        {"i": n, "titel": m["titel"], "beschreibung": m["beschreibung"],
         "schlagworte": m["schlagworte"]} for n, m in enumerate(mats)]}


def _richtig(gewaehlt: str | None, erwartet: list[str] | None) -> bool:
    return gewaehlt is None if erwartet is None else gewaehlt in erwartet


def _quote(zeilen: list[tuple[dict, str, float]], schwelle: float) -> float:
    return sum(_richtig(p if w >= schwelle else None, m["erwartet"])
               for m, p, w in zeilen) / max(len(zeilen), 1)


def _haelften(zeilen: list[tuple[dict, str, float]]
              ) -> tuple[list[tuple[dict, str, float]], list[tuple[dict, str, float]]]:
    """Nach Originalgruppen geteilt: ein Eintrag „nur Titel“ (gleicher Titel) gehört zur Gruppe
    seines Originals; Gruppen abwechselnd in Kalibrierung und Prüfung."""
    gruppen: dict[str, int] = {}
    for m, _p, _w in zeilen:
        schluessel = m["titel"] if m.get("art") in (None, "nur_titel") else f"datei:{m['titel']}"
        gruppen.setdefault(schluessel, len(gruppen))
    def haelfte(m: dict) -> int:
        schluessel = m["titel"] if m.get("art") in (None, "nur_titel") else f"datei:{m['titel']}"
        return gruppen[schluessel] % 2
    return ([z for z in zeilen if haelfte(z[0]) == 0], [z for z in zeilen if haelfte(z[0]) == 1])


def _kalibrieren(zeilen: list[tuple[dict, str, float]]) -> float:
    """Die Mitte des längsten Bereichs mit der besten Quote (Schritte 0,01)."""
    stufen = [round(0.20 + s / 100, 2) for s in range(41)]
    quoten = [_quote(zeilen, s) for s in stufen]
    beste = max(quoten)
    laeufe, lauf = [], []
    for s, q in zip(stufen, quoten, strict=True):
        if q == beste:
            lauf.append(s)
        elif lauf:
            laeufe.append(lauf)
            lauf = []
    laeufe.append(lauf) if lauf else None
    laengster = max(laeufe, key=len)
    return laengster[len(laengster) // 2]


async def einbettung_allein() -> float:
    acc = new_accumulator()
    mats = _laden()
    texte = [zu.punkt_text(p) for p in PUNKTE] + [m.text for m in zu.materialien(_teil(mats))]
    vektoren = await llm_einbettungen.einbettungen(texte, usage_acc=acc, phase="zuordnung")
    punkte, rest = vektoren[:len(PUNKTE)], vektoren[len(PUNKTE):]
    zeilen = []
    for m, v in zip(mats, rest, strict=True):
        aehnlich = [strukturentwurf_naehe.kosinus(v, p) for p in punkte]
        beste = max(range(len(PUNKTE)), key=aehnlich.__getitem__)
        zeilen.append((m, PUNKTE[beste]["id"], aehnlich[beste]))
    kalib, pruef = _haelften(zeilen)
    eingestellt = strukturentwurf_naehe.schwelle(get_embed_model())
    gewaehlt = _kalibrieren(kalib)
    print(f"Modell {get_embed_model()}, {len(mats)} Materialien, {acc['prompt_tokens']} Token")
    print(f"Kalibrierung ({len(kalib)}): beste Schwelle {gewaehlt:.2f} → "
          f"{_quote(kalib, gewaehlt):.0%}")
    print(f"UNABHÄNGIG — Prüfung ({len(pruef)}) bei der kalibrierten Schwelle {gewaehlt:.2f}: "
          f"{_quote(pruef, gewaehlt):.0%}")
    if eingestellt is not None:
        print(f"zum Vergleich (nicht unabhängig) — Prüfung bei der eingestellten Schwelle "
              f"{eingestellt:.2f}: {_quote(pruef, eingestellt):.0%}")
    s = eingestellt if eingestellt is not None else gewaehlt
    print(f"\nFehlzuordnungen (alle, Schwelle {s:.2f}):")
    for m, p, w in zeilen:
        g = p if w >= s else None
        if not _richtig(g, m["erwartet"]):
            print(f"  {m['titel'][:60]:<60} → {g} ({w:.3f}), erwartet {m['erwartet']}")
    nicht = sum(1 for _m, _p, w in zeilen if w < s)
    print(f"nicht zugeordnet: {nicht} von {len(zeilen)} ({nicht / len(zeilen):.0%}); fachfremd: "
          f"{sum(1 for m in mats if m['erwartet'] is None)}")
    for art in ("nur_titel", "dateiname"):
        teil = [z for z in zeilen if z[0].get("art") == art]
        print(f"Quote {art} ({len(teil)}): {_quote(teil, s):.0%}")
    print(f"Quote gesamt bei {s:.2f}: {_quote(zeilen, s):.0%}")
    richtig = [w for m, p, w in zeilen if m["erwartet"] and p in m["erwartet"]]
    fremd = [w for m, _p, w in zeilen if m["erwartet"] is None]
    print(f"Ähnlichkeit: richtige Paare {min(richtig):.3f}–{max(richtig):.3f}, fachfremd "
          f"höchstens {max(fremd):.3f}")
    print("Quote je Schwelle (Prüfung): " + ", ".join(
        f"{x / 100:.2f}: {_quote(pruef, x / 100):.0%}" for x in range(30, 52, 2)))
    return _quote(pruef, s)


async def ganzer_entwurf() -> None:
    from boerdi.services import strukturentwurf_dienst as dienst
    from boerdi.services.ablauf import metadaten

    mats = _laden()
    teil = _teil(mats)
    acc = new_accumulator()
    frist = asyncio.get_running_loop().time() + 150
    erzeugt = await dienst.erzeugen(
        dienst.Auftrag(thema="Erdkunde", anzahl_oben=6, tiefe=2), llm=dienst.llm_json(acc),
        frist_ende=frist, dokument=metadaten.als_dokument(teil))
    if erzeugt.daten is None:
        print(f"\nKein Entwurf: {erzeugt.grund}")
        return
    erg = await zu.zuordnen(erzeugt.daten, teil, einbetten=zu.einbetten_mit(acc, frist + 60),
                            frist_ende=asyncio.get_running_loop().time() + 60)
    print(f"\nEntwurf „{erg.daten['titel']}“: Modell {erg.modell}, Einbettung {erg.einbettung}, "
          f"übrig {erg.uebrig} (von {len(mats)})")
    for k in erg.daten["knoten"]:
        themen = Counter(str((mats[e["i"]]["erwartet"] or ["fremd"])[0])
                         for e in k.get("inhalte") or [])
        print(f"- {k['titel']}: {sum(themen.values())} {dict(themen)}")
    fremd = [mats[e["i"]]["titel"][:40] for e in erg.daten.get("nicht_zugeordnet") or []]
    print(f"nicht zugeordnet: {fremd}")
    print(f"Verbrauch: {acc['prompt_tokens']} + {acc['completion_tokens']} Token, "
          f"{acc['calls']} Aufrufe")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--entwurf", action="store_true", help="auch der ganze Entwurf")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if get_settings().llm_provider != "openai":
        print("Nur gegen OpenAI direkt (LLM_PROVIDER=openai).")
        return 2
    quote = asyncio.run(einbettung_allein())
    if args.entwurf:
        asyncio.run(ganzer_entwurf())
    return 0 if quote >= SOLL else 1


if __name__ == "__main__":
    sys.exit(main())
