#!/usr/bin/env python
"""Messlauf zu Paket N3 (Plan 2026-11-19): ordnet die Einbettung Materialien richtig zu?

* **Einbettung allein** (Vorgabe): Punkte und Materialien des Beispielsatzes
  (``tests/zuordnung_beispiel``) in EINEM Aufruf einbetten, je Material den ähnlichsten Punkt
  nehmen (ab der Schwelle des Modells, ``strukturentwurf_naehe.SCHWELLEN``) und mit der
  erwarteten Zuordnung vergleichen. Dazu die Quote für andere
  Schwellen und die Ähnlichkeiten richtiger und fachfremder Paare. Soll: ≥ 80 % richtig.
* **Ganzer Entwurf** (``--entwurf``): ``aus_inhalten`` mit echtem Modell (obere Ebene und
  Unterpunkte, ohne Moderation — der Satz ist fest) und danach die Zuordnung. Gezählt wird, wie
  viele das Modell zuordnet, wie viele die Einbettung, wie viele übrig bleiben, und wie rein die
  Punkte sind (Anteil des häufigsten erwarteten Themas je Punkt).

Nur gegen OpenAI direkt (``LLM_PROVIDER=openai``, Nutzer-Vorgabe) — nie gegen die b-api. Kosten:
ein Einbettungsaufruf (rund 1 000 Token); mit ``--entwurf`` dazu rund fünf Modellaufrufe.

    uv run python scripts/zuordnung_messen.py [--entwurf]

Rückgabe: 0 = Soll erreicht · 1 = verfehlt · 2 = falscher Anbieter.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # ``tests`` als Paket

from tests import zuordnung_beispiel as bsp  # noqa: E402

from boerdi.obs.usage import new_accumulator  # noqa: E402
from boerdi.services import llm_einbettungen  # noqa: E402
from boerdi.services import strukturentwurf_zuordnung as zu  # noqa: E402
from boerdi.services.llm_models import get_embed_model  # noqa: E402
from boerdi.settings import get_settings  # noqa: E402

logging.basicConfig(level=logging.WARNING)
SOLL: float = 0.80
_SCHWELLEN = (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50)


def _einbetten(acc: dict) -> zu.Einbetten:
    async def rufe(texte: list[str]) -> list[list[float]]:
        return await llm_einbettungen.einbettungen(texte, usage_acc=acc, phase="zuordnung")

    return rufe


def _quote(beste: dict[str, tuple[str, float]], schwelle: float) -> float:
    richtig = 0
    for kennung, erwartet in bsp.ERWARTET.items():
        punkt, wert = beste[kennung]
        gewaehlt = punkt if wert >= schwelle else None
        richtig += gewaehlt == erwartet
    return richtig / len(bsp.ERWARTET)


async def einbettung_allein() -> float:
    acc = new_accumulator()
    mats = zu.materialien(bsp.teil())
    texte = [zu.punkt_text(p) for p in bsp.PUNKTE] + [m.text for m in mats]
    vektoren = await _einbetten(acc)(texte)
    punkte = vektoren[:len(bsp.PUNKTE)]
    beste: dict[str, tuple[str, float]] = {}
    grenze = zu.schwelle(get_embed_model()) or 0.0
    print(f"Modell {get_embed_model()}, Schwelle {grenze}, {acc['prompt_tokens']} Token\n")
    for m, v in zip(mats, vektoren[len(bsp.PUNKTE):], strict=True):
        aehnlich = {p["id"]: zu.kosinus(v, pv) for p, pv in zip(bsp.PUNKTE, punkte, strict=True)}
        punkt = max(aehnlich, key=aehnlich.__getitem__)
        beste[m.kennung] = (punkt, aehnlich[punkt])
        erwartet = bsp.ERWARTET[m.kennung]
        zweit = sorted(aehnlich.values())[-2]
        gewaehlt = punkt if aehnlich[punkt] >= grenze else None
        marke = "ok " if gewaehlt == erwartet else "FALSCH"
        print(f"{marke} {m.kennung:>4} {m.eintrag['name'][:44]:<44} → {punkt} "
              f"{aehnlich[punkt]:.3f} (2. {zweit:.3f}, erwartet {erwartet})")
    richtig = [beste[k][1] for k, e in bsp.ERWARTET.items() if e and beste[k][0] == e]
    fremd = [beste[k][1] for k, e in bsp.ERWARTET.items() if e is None]
    print(f"\nrichtige Paare: min {min(richtig):.3f}, max {max(richtig):.3f}; "
          f"fachfremd höchstens {max(fremd):.3f}")
    for s in _SCHWELLEN:
        print(f"Schwelle {s:.2f}: {_quote(beste, s):.0%} richtig")
    quote = _quote(beste, grenze)
    print(f"\nQuote bei der Schwelle {grenze}: {quote:.0%} (Soll {SOLL:.0%})")
    return quote


async def ganzer_entwurf() -> None:
    from boerdi.services import strukturentwurf_dienst as dienst
    from boerdi.services.ablauf import metadaten

    teil = bsp.teil()
    acc = new_accumulator()
    frist = asyncio.get_running_loop().time() + 120
    erzeugt = await dienst.erzeugen(
        dienst.Auftrag(thema="Erdkunde", anzahl_oben=6, tiefe=2), llm=dienst.llm_json(acc),
        frist_ende=frist, dokument=metadaten.als_dokument(teil))
    if erzeugt.daten is None:
        print(f"\nKein Entwurf: {erzeugt.grund}")
        return
    erg = await zu.zuordnen(erzeugt.daten, teil, einbetten=_einbetten(acc))
    print(f"\nEntwurf „{erg.daten['titel']}“: Modell {erg.modell}, Einbettung {erg.einbettung}, "
          f"übrig {erg.uebrig} (von {len(bsp.ERWARTET)})")
    rein = gesamt = 0
    for k in erg.daten["knoten"]:
        themen = [bsp.ERWARTET[f"a{e['i'] + 1}"] for e in k.get("inhalte") or []]
        haeufig = Counter(themen).most_common(1)
        rein += haeufig[0][1] if haeufig else 0
        gesamt += len(themen)
        print(f"- {k['titel']}: {len(themen)} ({', '.join(str(t) for t in themen)})")
    print(f"nicht zugeordnet: {[e['name'] for e in erg.daten.get('nicht_zugeordnet') or []]}")
    if gesamt:
        print(f"Reinheit der Punkte: {rein / gesamt:.0%}")
    await _gegenprobe(erzeugt.daten, erg.daten, teil, acc)
    print(f"Verbrauch: {acc['prompt_tokens']} + {acc['completion_tokens']} Token, "
          f"{acc['calls']} Aufrufe")


def _punkt_je_material(daten: dict) -> dict[int, set[str]]:
    aus: dict[int, set[str]] = {}
    for k in daten["knoten"]:
        for e in k.get("inhalte") or []:
            aus.setdefault(e["i"], set()).add(k["id"])
    return aus


async def _gegenprobe(roh: dict, mit_modell: dict, teil: dict, acc: dict) -> None:
    """Dieselben Punkte (vom Modell benannt), aber ohne seine ``abschnitte``: ordnet die
    Einbettung allein jedes Material einem Punkt zu, den auch das Modell wählte?"""
    ohne = {**roh, "knoten": [{f: w for f, w in k.items() if f != "abschnitte"}
                               for k in roh["knoten"]]}
    erg = await zu.zuordnen(ohne, teil, einbetten=_einbetten(acc))
    modell, einbettung = _punkt_je_material(mit_modell), _punkt_je_material(erg.daten)
    gleich = sum(1 for i, punkte in modell.items() if einbettung.get(i, set()) & punkte)
    fremd = {i for i, e in enumerate(bsp.ERWARTET.values()) if e is None}
    rest = {e["i"] for e in erg.daten.get("nicht_zugeordnet") or []}
    print(f"Gegenprobe (nur Einbettung, Punkte des Modells): {gleich} von {len(modell)} wie das "
          f"Modell, {erg.uebrig} übrig, fachfremde übrig: {fremd <= rest}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--entwurf", action="store_true", help="auch der ganze Entwurf")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")   # Windows-Konsole: Pfeile und Anführungszeichen
    if get_settings().llm_provider != "openai":
        print("Nur gegen OpenAI direkt (LLM_PROVIDER=openai).")
        return 2
    quote = asyncio.run(einbettung_allein())
    if args.entwurf:
        asyncio.run(ganzer_entwurf())
    return 0 if quote >= SOLL else 1


if __name__ == "__main__":
    sys.exit(main())
