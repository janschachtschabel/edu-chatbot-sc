"""Eine Wendung an einer wartenden Frage (Durchtest Paket K, 19.11.; drittes Review).

Damals übernahm angemeldet eine neue Sitzung den jüngsten offenen Vorgang (``arbeitsstand.
auffrischen``; seit Plan 2026-11-20, Entscheid E-F, nicht mehr — eine Frage gilt nur ihrem
Gespräch, ``wahl_zug._fortsetzen``). Dort wurde „Themenbaum aus meinen Dateien“ still die
Freitext-Antwort ``zweck`` des fremden Laufs. An einer offenen Frage im eigenen Gespräch gilt:

- :func:`wendung_trifft`: eine Nachricht an einer offenen Frage ist eine Wendung, wenn sie **im
  Wesentlichen** die Wendung ist (``ausloeser.per_text_genau``: gleich, mit der Wendung vorn und
  höchstens drei Wörtern danach, oder höchstens 15 Zeichen länger; nur ganze Wörter). Eine
  Beschriftung oder ein Synonym der Frage bleibt die Wahl. Kommt derselbe Text an derselben Frage
  ein zweites Mal, ist er die Antwort — die Person kommt immer heraus. Ausnahme (Plan 2026-11-20,
  G2b): in einem Ablauf mit ``endet_bei_text`` ist die eigene Wendung an einer Frage ohne
  Freitext getippter Text — wie in der Tour.
- :func:`wendung_beantworten`: speichert nichts am Lauf. Derselbe Ablauf: die offene Frage erneut
  mit „Du bist schon mitten in …“, ihren Chips und „Neu starten“ (gebunden an diesen Lauf). Ein
  anderer Ablauf: die Ersetzen-Rückfrage samt „Hier weitermachen“; wer sie übergeht, hat den
  anderen Ablauf abgelehnt (``zug_basis.ausstieg_merken``) — keine Schleife.
- :func:`hier_weiter`: „Hier weitermachen“ (Direktaktion ``ablauf_wahl`` mit der Wahl
  :data:`HIER`) zeigt die offene Frage wieder mit ihren Chips.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services import arbeitsstand, vorgaenge
from boerdi.services.ablauf import ausloeser, platzhalter, treiber
from boerdi.services.ablauf import zug_basis as basis
from boerdi.services.ablauf.ausloeser import laden
from boerdi.services.ablauf.pruefung import mit_wahl
from boerdi.services.ablauf.wahl_zug import AKTION, knoepfe, wahl_aus_text, wartende_frage

#: Die Wahl „Hier weitermachen“ — keine Option kann so heißen (Kennungen beginnen mit a–z).
HIER: Final = "_hier"
#: Wo die Wendung schon einmal stand: Vorgang, Schritt und ein Prüfwert des Textes (nie der Text).
MARKE_KEY: Final = "_ablauf_wendung_an_frage"


def _marke(entities: dict[str, Any], session_id: str, schritt: Schritt, text: str | None) -> str:
    vw = arbeitsstand.verweis(entities, arbeitsstand.aufrufer_fuer(session_id)) or {}
    pruef = hashlib.sha256(" ".join(ausloeser.woerter(text)).encode()).hexdigest()[:16]
    return f"{vw.get('id')}:{schritt.id}:{pruef}"


def wendung_trifft(session_id: str, session_state: dict[str, Any], text: str | None,
                   sprache: str | None = None, ohne: str | None = None) -> AblaufArea | None:
    """Der Ablauf, dessen Wendung ``text`` im Wesentlichen ist, während ein Lauf dieser Person an
    einer Frage wartet — ``None`` sonst. Ein fremder Ablauf nur mit erfüllten Voraussetzungen und
    nie ``ohne`` (der eben abgelehnte), wie ``zug.text_ausloeser``. Nur aus dem Verweis."""
    if (treffer := wartende_frage(session_id, session_state)) is None:
        return None
    _lauf, ablauf, schritt = treffer
    if wahl_aus_text(schritt, text, sprache) is not None:
        return None
    entities = session_state.get("entities") or {}
    if entities.get(MARKE_KEY) == _marke(entities, session_id, schritt, text):
        return None                       # zum zweiten Mal: die Antwort
    ziel = ausloeser.per_text_genau(text)
    if ziel is None or (ziel.id != ablauf.id and (ziel.id == ohne
                                                  or not ausloeser.erfuellt(ziel))):
        return None
    if ziel.id == ablauf.id and ablauf.endet_bei_text and schritt.freitext is None:
        # Plan 2026-11-20, G2b: in einem Ablauf mit ``endet_bei_text`` ist die eigene Wendung an
        # der Frage getippter Text (Hinweis, dann Ende) — wie die Tour im Gruppen-Schritt; ohne
        # Freitext wird sie nie still die Antwort
        return None
    return ziel


def _hier_knopf(lang: str, ablauf_id: str, schritt_id: str) -> str:
    label = bot_text(lang, "action.ablauf.hierWeiter").replace("|", "/")
    return f"__action__|{label}|{AKTION}|" + json.dumps(
        {"ablauf": ablauf_id, "schritt": schritt_id, "wahl": HIER}, ensure_ascii=False)


async def _frage(session: Any, req: ChatRequest, entities: dict[str, Any], ablauf: AblaufArea,
                 schritt: Schritt) -> str:
    """Der Text der offenen Frage, mit Wahl- und Teil-Platzhaltern."""
    lang = resolve_locale(req.environment.locale)
    frage = ((schritt.text or {}).get(lang) or (schritt.text or {}).get("de") or "").strip()
    teile = basis.umgebung(session, req, entities, ()).teile
    frage, _fremd = await treiber.wahl_einsetzen(frage, ablauf, lang, teile)
    return await platzhalter.einsetzen(frage, teile)


async def wendung_beantworten(session: Any, req: ChatRequest, session_state: dict,
                              ziel: AblaufArea) -> ChatResponse | None:
    """Die Antwort zu :func:`wendung_trifft` (siehe oben). ``None``: der Lauf wartet nicht mehr an
    einer Frage — der Zug geht den gewöhnlichen Weg."""
    from boerdi.services.ablauf import zug  # zyklenfrei erst zur Laufzeit

    entities = session_state.setdefault("entities", {})
    aufrufer = arbeitsstand.aufrufer_fuer(req.session_id)
    vw = arbeitsstand.verweis(entities, aufrufer)
    v = await vorgaenge.lesen(session, vw["id"], aufrufer) if vw else None
    lauf = (v.akte or {}).get("lauf") if v is not None else None
    ablauf = laden(lauf.get("ablauf")) if isinstance(lauf, dict) else None
    schritt = (next((s for s in ablauf.schritte if s.id == lauf.get("schritt")), None)
               if isinstance(lauf, dict) and ablauf is not None else None)
    if (not isinstance(lauf, dict) or lauf.get("status") != treiber.WARTET_WAHL
            or not treiber.gilt(ablauf, lauf) or schritt is None or not mit_wahl(schritt)):
        basis.verweis_auffrischen(entities, v, aufrufer)
        return None
    lang = resolve_locale(req.environment.locale)
    entities[MARKE_KEY] = _marke(entities, req.session_id, schritt, req.message)
    if ziel.id != ablauf.id:
        basis.ausstieg_merken(session_state, ziel.id)
        await basis.update_session(session, req.session_id, entities=entities)
        antwort = await zug.ersetzen_fragen(session, req, ziel, None, v, lauf)
        return antwort.model_copy(update={"quick_replies": [
            *antwort.quick_replies, _hier_knopf(lang, ablauf.id, schritt.id)]})
    titel = (ablauf.titel.get(lang) or ablauf.titel.get("de") or ablauf.id).strip()
    satz = bot_text(lang, "action.ablauf.schonMitten", titel=titel)
    frage = await _frage(session, req, entities, ablauf, schritt)
    return await basis.fester_text(session, req, f"{satz}\n\n{frage}".strip(), entities, [
        *knoepfe(ablauf.id, treiber.wahl_angebot(schritt, lang)),
        zug.neu_starten_knopf(lang, ablauf.id, v, lauf)])


async def hier_weiter(session: Any, req: ChatRequest, session_state: dict) -> ChatResponse | None:
    """„Hier weitermachen“: die offene Frage mit ihren Chips, wenn der Lauf noch an genau diesem
    Schritt wartet — sonst ``None`` (dann „gilt nicht mehr“, ``wahl_zug.waehlen``)."""
    params = req.action_params or {}
    if (treffer := wartende_frage(req.session_id, session_state)) is None:
        return None
    _lauf, ablauf, schritt = treffer
    if params.get("ablauf") != ablauf.id or params.get("schritt") != schritt.id:
        return None
    entities = session_state.setdefault("entities", {})
    lang = resolve_locale(req.environment.locale)
    return await basis.fester_text(session, req, await _frage(session, req, entities, ablauf,
                                                              schritt), entities,
                                   knoepfe(ablauf.id, treiber.wahl_angebot(schritt, lang)))
