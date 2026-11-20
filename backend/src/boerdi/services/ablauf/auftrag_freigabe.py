"""Paket N4 (Plan 2026-11-19): die Freigabe-Box vor dem Start eines schreibenden Auftrags.

Ein ``auftrag``-Schritt mit ``repo_schreibt`` über den MCP startet nicht mehr im selben Zug wie
die Rückfrage davor (Paket K, Entscheid 1), sondern legt vor:

- :func:`vorlegen` holt die Vorschau des MCP **je Teil** (``aufteilen``, höchstens 50 Dateien je
  Job). Ein Datensatz mit Problem lässt beim MCP die ganze Vorschau scheitern — er fällt heraus,
  die übrigen werden einmal neu vorgelegt; die Probleme zeigt die Box getrennt.
- Gemerkt wird (:func:`merken`) nur in ``entities`` der Sitzung unter :data:`KEY`: Schlüssel und
  Frist des **ersten** Teils, gebunden an Lauf, Schritt, Vorlage (``id``) und Aufrufer
  (``aufrufer_kennung``). Nie im Vorgang, nie im Text, nie im Log; ``_``-Schlüssel gehen nicht in
  Debug und Verlauf.
- Die Box ist die Vorschau-Box von Paket S (``ui_inhaltsrahmen``, Art ``schreib_vorschau``), um die
  Liste erweitert (``freigabe``) — ohne nodeIds.

Spätere Teile eines Stapels holen ihren Schlüssel beim Start neu (``mcp_starter.starten``), ohne
neue Freigabe: die Person hat die ganze Liste freigegeben, und ein Schlüssel gilt nur zehn Minuten —
länger als ein Teil braucht. Prüft der MCP dabei neu und lehnt ab, scheitert nur dieser Teil.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Final

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain.config_models.kestra_flows import METADATEN_FLOW
from boerdi.domain.ui_bloecke import neuer_block
from boerdi.i18n import bot_text
from boerdi.services.ablauf import auftrag_teile
from boerdi.services.auftraege import mcp_vorschau
from boerdi.services.auftraege.client import AuftragFehler
from boerdi.services.mcp.auth import aufrufer_kennung

#: Die offene Freigabe in ``entities`` (``_``: nie in Debug, Verlauf oder Kennzeile).
KEY: Final = "_auftrag_freigabe"
#: Die Liste, deren Knoten aufgeteilt werden, wenn der Schritt nichts anderes sagt.
_LISTE: Final = auftrag_teile.KNOTEN_LISTE
_TITEL_ZEICHEN: Final = 120
#: Review N4 (4): Probleme, die ein neuer Versuch nicht heilt — nur sie fallen heraus.
ENDGUELTIG: Final = frozenset({"not_found", "not_readable", "not_a_record", "is_reference",
                               "not_writable"})
_TEXT_EINTRAEGE: Final = 10


@dataclass
class AuftragVorlage:
    """Ergebnis von :func:`vorlegen`. ``ausfall``: ``None`` (Box zeigen), ``voruebergehend`` (gleich
    noch einmal) oder ``abgelehnt`` (Ersatzweg); ``fehler`` trägt den Grund für den Satz."""

    ausfall: str | None = None
    fehler: AuftragFehler | None = None
    #: Die freigegebenen Argumente (ohne Datensätze mit Problem) — für alle Teile.
    args: dict[str, Any] = field(default_factory=dict)
    #: Die Argumente, an die :attr:`token` gebunden ist (der erste Teil).
    erst: dict[str, Any] = field(default_factory=dict)
    token: str = ""
    laeuft_ab: float = 0.0
    eintraege: list[tuple[str, str]] = field(default_factory=list)
    probleme: list[tuple[str, str]] = field(default_factory=list)


def _stuecke(args: dict[str, Any], aufteilen: Any) -> tuple[str | None, list[dict[str, Any]]]:
    if aufteilen is None:
        return (_LISTE if isinstance(args.get(_LISTE), list) else None), [args]
    return aufteilen.argument, auftrag_teile.teilen(args, aufteilen.argument, aufteilen.hoechstens)


def _ausfall(fehler: AuftragFehler) -> AuftragVorlage:
    """Vorübergehend (gleich noch einmal, zurück an die Rückfrage) oder abgelehnt."""
    if isinstance(fehler, mcp_vorschau.VorschauFehler) and any(
            p not in ENDGUELTIG for _k, p in fehler.probleme):
        # Review N4 (4): ein ungeprüfter Datensatz ist kein Urteil — gleich noch einmal
        fehler = AuftragFehler("nicht_verfuegbar")          # das Repository antwortete nicht
    vorlaeufig = fehler.grund in ("nicht_verfuegbar", "voll")
    return AuftragVorlage(ausfall="voruebergehend" if vorlaeufig else "abgelehnt", fehler=fehler)


async def _teil(flow: str, stueck: dict[str, Any], liste: str | None
                ) -> tuple[mcp_vorschau.Vorschau | None, dict[str, Any], list[tuple[str, str]]]:
    """Vorschau eines Teils; ein Datensatz mit endgültigem Problem fällt heraus, die übrigen
    einmal neu. Ist einer nur ungeprüft (``unchecked``), bleibt der Fehler — vorübergehend."""
    try:
        return await mcp_vorschau.vorschau(flow, stueck), stueck, []
    except mcp_vorschau.VorschauFehler as fehler:
        if (liste is None or fehler.grund != "eingaben" or not fehler.probleme
                or any(p not in ENDGUELTIG for _k, p in fehler.probleme)):
            raise
        weg = {k for k, _p in fehler.probleme}
        rest = [n for n in stueck.get(liste) or [] if n not in weg]
        if not rest:
            return None, {**stueck, liste: []}, fehler.probleme
        neu = {**stueck, liste: rest}
        return await mcp_vorschau.vorschau(flow, neu), neu, fehler.probleme


async def vorlegen(flow: str, args: dict[str, Any], aufteilen: Any) -> AuftragVorlage:
    """Die Vorschau des MCP für alle Teile — eine Vorlage für EINE Box."""
    liste, stuecke = _stuecke(args, aufteilen)
    eintraege: list[tuple[str, str]] = []
    probleme: list[tuple[str, str]] = []
    gebunden: tuple[dict[str, Any], mcp_vorschau.Vorschau] | None = None
    try:
        for stueck in stuecke:
            vorschau, geprueft, weg = await _teil(flow, stueck, liste)
            probleme.extend(weg)
            if vorschau is None:
                continue
            ids = geprueft.get(liste) if liste else None
            eintraege.extend((k, vorschau.titel.get(k, "")) for k in ids or [])
            if not ids:
                eintraege.extend(vorschau.titel.items())      # ein Flow ohne Liste
            gebunden = gebunden or (geprueft, vorschau)
        if gebunden is None:
            return AuftragVorlage(ausfall="abgelehnt", probleme=probleme)
        frei = {**args, liste: [k for k, _t in eintraege]} if liste else args
        _l, neu_geteilt = _stuecke(frei, aufteilen)
        erst, vorschau = gebunden
        if neu_geteilt[0] != erst:
            # Datensätze fielen heraus, die Teile schneiden jetzt anders — der Schlüssel muss zu
            # genau den Argumenten des ersten Teils passen
            erst, vorschau = neu_geteilt[0], await mcp_vorschau.vorschau(flow, neu_geteilt[0])
    except AuftragFehler as fehler:
        return _ausfall(fehler)
    return AuftragVorlage(args=frei, erst=erst, token=vorschau.token,
                          laeuft_ab=vorschau.laeuft_ab, eintraege=eintraege, probleme=probleme)


def _ordner(ablage: Any) -> dict[str, str]:
    """nodeId → Ordner (Pfad im Dateinamen, sonst der Ordner der Ablage) — für die Gruppen."""
    if not isinstance(ablage, dict):
        return {}
    wurzel = str(ablage.get("ordner") or "")
    aus: dict[str, str] = {}
    for e in [*(ablage.get("inhalte") or []), *(ablage.get("frueher") or [])]:
        if isinstance(e, dict) and isinstance(e.get("node_id"), str):
            name = str(e.get("name") or "").replace("\\", "/")
            aus[e["node_id"]] = name.rsplit("/", 1)[0] if "/" in name else wurzel
    return aus


def _titel_aus(ablage: Any) -> dict[str, str]:
    if not isinstance(ablage, dict):
        return {}
    # Review N4 (NIT): auch die früher abgelegten Einträge (``frueher``) kennen einen Titel
    eintraege = [*(ablage.get("frueher") or []), *(ablage.get("inhalte") or [])]
    return {e["node_id"]: str(e.get("titel") or e.get("name") or "")
            for e in eintraege if isinstance(e, dict) and isinstance(e.get("node_id"), str)}


def box_daten(freigabe: dict[str, Any], ablauf_id: str, ablage: Any) -> dict[str, Any]:
    """Die Daten der Liste für die Box — Titel, Ordner, Probleme; ohne nodeIds und Schlüssel."""
    ordner, titel = _ordner(ablage), _titel_aus(ablage)
    flow = str(freigabe.get("flow") or "")
    return {
        "ablauf": ablauf_id, "id": str(freigabe["id"]), "anzahl": len(freigabe["eintraege"]),
        # Review N4 (7): Kopf und Satz zu den Feldern nur beim Metadaten-Flow
        "flow": flow[:200], "metadaten": flow == METADATEN_FLOW,
        "eintraege": [{"titel": (t or titel.get(k) or "—")[:_TITEL_ZEICHEN],
                       "ordner": ordner.get(k, "")[:_TITEL_ZEICHEN]}
                      for k, t in freigabe["eintraege"]],
        "probleme": [{"titel": (titel.get(k) or "—")[:_TITEL_ZEICHEN], "grund": p}
                     for k, p in freigabe["probleme"]],
    }


def _n(lang: str, schluessel: str, n: int) -> str:
    """Review N4 (NIT): „1 Material“ — die Einzahl hat einen eigenen Schlüssel (``…1``)."""
    return bot_text(lang, schluessel + ("1" if n == 1 else ""), n=n)


def kopf(daten: dict[str, Any], lang: str) -> str:
    """Kopfzeile: beim Metadaten-Flow „N Materialien werden erschlossen“, sonst neutral mit dem
    Flow — die Zahl nur, wenn es Einträge gibt."""
    if daten["metadaten"]:
        return _n(lang, "action.ablauf.auftragFreigabeKopf", daten["anzahl"])
    text = bot_text(lang, "action.ablauf.auftragFreigabeKopfFlow", flow=daten["flow"])
    if daten["anzahl"]:
        text += " " + _n(lang, "action.ablauf.auftragFreigabeAnzahl", daten["anzahl"])
    return text


def _text(daten: dict[str, Any], lang: str) -> str:
    """Die Textfassung (älteres Widget, Druck): Kopf, Satz, Probleme, die ersten Einträge."""
    zeilen = [f"**{kopf(daten, lang)}**"]
    if daten["metadaten"]:
        zeilen += ["", bot_text(lang, "action.ablauf.auftragFreigabeSatz")]
    if daten["probleme"]:
        zeilen += ["", _n(lang, "action.ablauf.auftragFreigabeProbleme",
                          len(daten["probleme"]))]
        zeilen += [f"- {p['titel']}" for p in daten["probleme"][:_TEXT_EINTRAEGE]]
    zeilen += [""] + [f"- {e['titel']}" for e in daten["eintraege"][:_TEXT_EINTRAEGE]]
    if (rest := len(daten["eintraege"]) - _TEXT_EINTRAEGE) > 0:
        zeilen.append(bot_text(lang, "action.ablauf.auftragFreigabeWeitere", n=rest))
    return "\n".join([*zeilen, "", bot_text(lang, "action.ablauf.auftragFreigabeKnoepfe")])


def merken(entities: dict[str, Any], freigabe: dict[str, Any], ablauf_id: str, lang: str,
           ablage: Any = None) -> UiBlock:
    """Die vorgelegte Freigabe merken (Schlüssel nur hier) und die Box bauen."""
    from boerdi.domain.inline_documents import _manifest
    from boerdi.ui_module.namen import INHALTSRAHMEN

    entities[KEY] = {
        "marke": {"ablauf": ablauf_id, "schritt": str(freigabe["schritt"]),
                  "id": str(freigabe["id"])},
        "caller": aufrufer_kennung(), "flow": str(freigabe["flow"]),
        "args": dict(freigabe["erst"]), "token": str(freigabe["token"]),
        "laeuft_ab": float(freigabe["laeuft_ab"]),
    }
    liste = box_daten(freigabe, ablauf_id, ablage)
    text = _text(liste, lang)
    daten = {"titel": bot_text(lang, "action.ablauf.auftragFreigabeTitel"),
             "art": "schreib_vorschau", "markdown": text, "freigabe": liste}
    return neuer_block(INHALTSRAHMEN, _manifest()["version"], "anzeigen", daten, text)


def offen(entities: dict[str, Any], ablauf_id: str | None = None) -> dict[str, Any] | None:
    """Die offene Freigabe dieses Aufrufers (und Ablaufs) — ``None`` ohne oder für jemand anderen
    (Muster ``caller_fingerprint``: eine andere Anmeldung löst nicht ein)."""
    roh = entities.get(KEY)
    if not isinstance(roh, dict) or roh.get("caller") != aufrufer_kennung():
        return None
    marke = roh.get("marke") if isinstance(roh.get("marke"), dict) else {}
    if ablauf_id is not None and marke.get("ablauf") != ablauf_id:
        return None
    return roh


def abgelaufen(roh: dict[str, Any], jetzt: float | None = None) -> bool:
    return float(roh.get("laeuft_ab") or 0) <= (time.time() if jetzt is None else jetzt)
