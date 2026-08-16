"""Cross-Encoder Card-Auswahl + Relevanz-Gate (2026-06-01).

Ersetzt das bisherige LLM-``select_top_cards``: deterministische, schnelle
Auswahl der **tatsächlich angezeigten** Karten je Box-Typ über den vorhandenen
ONNX-Cross-Encoder (``rag_service``). Damit
  * sieht das Antwort-LLM GENAU die angezeigten Karten (kein größerer Pool),
  * werden off-topic Treffer (v.a. bei wenigen Themenseiten) per absoluter
    Relevanz-Schwelle weggelassen statt „best-of-schlecht" durchgereicht.

Empirisch kalibriert (siehe ``scripts/test_reranker_3types.py``): der
Cross-Encoder gibt rohe Logits; relevante Sammlungen/Themenseiten liegen klar
> 0, off-topic deutlich < 0 (z.B. Themenseite „Nachhaltigkeit (LTP)" bei
Query „Klimawandel" = −4,02). Einzelinhalte sind verrauschter → milderes Gate.

Schwellen (Logit), per ENV überschreibbar:
  * Sammlungen + Themenseiten : ``CARD_CE_GATE_COLLECTION``  (Default 0.0)
  * Einzelinhalte             : ``CARD_CE_GATE_CONTENT``     (Default −1.5)
Top-N je Box: ``CARD_CE_TOP_N`` (Default 3).

Arbeitet auf dem MCP-Envelope (``{total,count,results}``) — re-serialisiert die
``results`` auf die gerankte, gegatete Top-N-Auswahl; ``total`` (für die
Such-CTA) bleibt unangetastet.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


# Tool-Name → Gate-Schwelle. Sammlungen/Themenseiten streng (saubere CE-Trennung),
# Einzelinhalte mild (kurze Titel → verrauschter).
#
# Das Sammlungs-Tor stand bis 2026-08-16 auf 0.0 und war damit strenger als die
# Lage, gegen die es gebaut wurde. Live gemessen an der Anfrage „Optik":
#   +0.52  „Geometrische Optik"      — klarer Treffer
#   -0.27  „Optik"                   — die GESUCHTE Sammlung, fiel heraus
#   -2.46  thematisch verfehlt       — das Rauschen, gegen das 0.0 stand
#          (Regression 2026-06-02: generische Themenseiten ~ -2.4)
# Kuratierte Sammlungen tragen oft eine leere ``description`` — der CE urteilt
# dann über Titel + Stichworte und landet knapp negativ, ohne off-topic zu sein.
# -1.0 trennt Treffer von Rauschen und bleibt strenger als das Inhalts-Tor.
def threshold_for_tool(tool_name: str) -> float:
    name = (tool_name or "").strip()
    if name in ("search_wlo_collections", "search_wlo_topic_pages"):
        return _env_float("CARD_CE_GATE_COLLECTION", -1.0)
    # search_wlo_content, get_collection_contents, get_node_details, …
    return _env_float("CARD_CE_GATE_CONTENT", -1.5)


def _normalisiert(s: str) -> str:
    """Vergleichsform eines Namens: Groß/Klein und Leerraum egal."""
    return " ".join(str(s or "").split()).casefold()


def _ist_namensgleich(item: dict[str, Any], query_norm: str) -> bool:
    """Trägt dieser Treffer GENAU den gesuchten Namen?

    Nutzer-Vorgabe 2026-08-16: wer „Optik" sucht, muss die Sammlung „Optik"
    bekommen — auch wenn der Cross-Encoder sie schlechter bewertet als eine
    breiter beschriebene Nachbarsammlung. Bewusst nur Gleichheit, keine
    Teilstring-Suche: „Optik" in „Geometrische Optik" wäre kein Namensgleich,
    sondern ein zweiter, schwächerer Relevanzbegriff neben dem CE.
    """
    if not query_norm or not isinstance(item, dict):
        return False
    return _normalisiert(item.get("title") or "") == query_norm


def _doc_text(item: dict[str, Any]) -> str:
    """Repräsentativer Text eines MCP-Result-Items für das (query, doc)-Paar."""
    if not isinstance(item, dict):
        return ""
    t = str(item.get("title") or "").strip()
    d = str(item.get("description") or "").strip()
    kw = item.get("keywords") or item.get("general_keyword") or []
    if isinstance(kw, list | tuple):
        kw = " ".join(str(k) for k in kw)
    return f"{t}. {d} {kw}".strip()[:450]


def rerank_gate_envelope(
    query: str,
    result_text: str,
    *,
    tool_name: str,
    top_n: int | None = None,
    allow_soft_fallback: bool = True,
) -> tuple[str, dict[str, Any] | None]:
    """CE-rank + gate + Top-N auf einem MCP-Envelope-``result_text``.

    Returns ``(new_result_text, debug)``. Bei fehlendem Reranker / nicht
    parsebarem Envelope / leerer Query → deterministischer Fallback
    (Top-N nach MCP-Reihenfolge) bzw. unverändert.
    """
    if not result_text:
        return result_text, None
    eff_top = top_n if (top_n and top_n > 0) else _env_int("CARD_CE_TOP_N", 3)

    # Envelope parsen (tolerant: trailing _queryMeta etc.).
    env: Any = None
    try:
        env = json.loads(result_text)
    except (ValueError, TypeError):
        try:
            from boerdi.services.mcp.parsers import _first_json_object
            frag = _first_json_object(result_text)
            env = json.loads(frag) if frag else None
        except (ValueError, TypeError, ImportError):
            env = None
    if not isinstance(env, dict) or not isinstance(env.get("results"), list):
        return result_text, None
    results: list[dict] = [r for r in env["results"] if isinstance(r, dict)]
    if not results:
        return result_text, None

    threshold = threshold_for_tool(tool_name)

    # Vorschlags-/Fallback-Sets (Themenseiten 'global-fallback' bzw.
    # 'query-fallback' aus _topic_pages_with_warmup) NICHT hart auf 0 gaten —
    # ABER nur bei einer echten Browse-Anfrage ("zeige mir alle themenseiten",
    # allow_soft_fallback=True). Dann gibt es kein Thema, zu dem etwas relevant
    # sein müsste, also nur ranken + Top-N statt leeren.
    # Bei einer THEMEN-Anfrage ("Photosynthese", allow_soft_fallback=False)
    # bleibt das harte Gate aktiv: generische Staging-Themenseiten
    # ("Galeriemethode", Score ~ -2.4) sind off-topic und gehoeren NICHT in
    # die Trefferliste. (Regression 2026-06-02 / Folge-Fix.)
    soft_gate = allow_soft_fallback and bool(
        env.get("_global_fallback") or env.get("_query_fallback")
    )

    # Reranker holen (geht im Fallback ohne). V13-Seam: rag/rerank._get_reranker
    # liefert heute None (embedding-order Default) → fallback-no-ce, ohne das
    # frühere ImportError-Warning-Spam (der Import zeigte auf das nie gebaute
    # ALT-Namens-Modul rag_service).
    rr = None
    try:
        from boerdi.services.rag.rerank import _get_reranker
        from boerdi.settings import get_settings

        # W9: eigener Schalter. Das Karten-Gate kostet ein Achtel des
        # RAG-Reranks (gemessen bei 3 Threads: 227 ms fuer 25 Karten gegen
        # 1853 ms fuer 25 Chunks) und liefert das sichtbarste Stueck Qualitaet
        # — das Wegwerfen thematisch verfehlter Treffer. Wer den teuren Pfad
        # abschaltet, soll diesen nicht STILL mitverlieren.
        rr = _get_reranker() if get_settings().card_reranker_enabled else None
    except Exception as e:  # pragma: no cover
        logger.warning("card_reranker: reranker import failed: %s", e)

    if rr is None or not query:
        kept = results[:eff_top]
        env["results"] = kept
        env["count"] = len(kept)
        return json.dumps(env, ensure_ascii=False), {
            "tool": tool_name, "mode": "fallback-no-ce",
            "in": len(results), "out": len(kept),
        }

    pairs = [(query, _doc_text(r)) for r in results]
    try:
        scores = rr.predict(pairs)
    except Exception as e:  # pragma: no cover
        logger.warning("card_reranker: CE predict failed: %s", e)
        kept = results[:eff_top]
        env["results"] = kept
        env["count"] = len(kept)
        return json.dumps(env, ensure_ascii=False), {
            "tool": tool_name, "mode": "fallback-ce-error",
            "in": len(results), "out": len(kept),
        }

    # Namensgleichheit schlägt den CE-Wert: der Zuschlag geht in DIESELBE Zahl,
    # die auch das Tor prüft — der gleichnamige Treffer steht damit vorn UND
    # überlebt, statt beides getrennt regeln zu müssen.
    _q_norm = _normalisiert(query)
    _bonus = _env_float("CARD_CE_EXACT_BONUS", 2.0)
    scored = sorted(
        (
            (r, float(s) + (_bonus if _ist_namensgleich(r, _q_norm) else 0.0))
            for r, s in zip(results, scores)  # noqa: B905 (verbatim ALT)
        ),
        key=lambda x: x[1], reverse=True,
    )
    if soft_gate:
        # Vorschlags-Set: nur ranken (Reihenfolge), nie auf 0 gaten.
        kept = [r for r, _s in scored][:eff_top]
    else:
        kept = [r for r, s in scored if s >= threshold][:eff_top]
    env["results"] = kept
    env["count"] = len(kept)
    debug = {
        "tool": tool_name,
        "threshold": threshold,
        "soft_gate": soft_gate,
        "in": len(results),
        "out": len(kept),
        "top_scores": [round(s, 2) for _, s in scored[:6]],
        "dropped_by_gate": (0 if soft_gate else sum(1 for _, s in scored if s < threshold)),
    }
    logger.info(
        "card_reranker %s: %d→%d (gate=%.1f, dropped=%d) scores=%s",
        tool_name, len(results), len(kept), threshold,
        debug["dropped_by_gate"], debug["top_scores"],
    )
    return json.dumps(env, ensure_ascii=False), debug


__all__ = ["rerank_gate_envelope", "threshold_for_tool"]
