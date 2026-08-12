"""Wikipedia-DE-Kurzinfo fuer die Material-Erzeugung.

Liefert zu einem Thema Titel, Lead-Absatz und URL. ``canvas_service`` reichert
damit KI-generierte Bildungsmaterialien mit einer belegten Kurzinfo an.

**Transport: das MCP-Werkzeug ``get_wikipedia_summary``, nicht mehr die
MediaWiki-REST-API direkt** (Nutzer-Entscheid 2026-08-01). Der Grund ist
Pflegeaufwand: die Anbindung an einen fremden Dienst — zwei Endpunkte, eigener
User-Agent, eigenes Timeout, eigene Weiterleitungs-Behandlung — lag hier im
Chatbot, obwohl der MCP-Server sie ohnehin unterhaelt. Der Lead-Absatz ist
derselbe (354 Zeichen bei „Photosynthese", vorher wie nachher); zusaetzlich
kann das Werkzeug ``language`` und ``sections``.

Erkauft ist das mit Laufzeit: ~850 ms statt ~570 ms Ende zu Ende, weil das
MCP-SDK pro Aufruf eine frische Sitzung oeffnet. Im Material-Pfad, der ohnehin
Sekunden LLM-Zeit braucht, ist das vertretbar — ein Gewinn ist es nicht.

**Der Relevanz-Filter bleibt — er wird durch den Wechsel wichtiger, nicht
ueberfluessig.** Live gemessen (2026-08-01) beantwortet das Werkzeug
„Stadt Berlin" mit dem Artikel *Bern* und „Dreiecke" mit *Dreiecker* (einem
Berg). Der Server loest Weiterleitungen sauber auf, aber er prueft nicht, ob
der Treffer zum Thema gehoert. Ohne ``_is_relevant`` landete die falsche
Sache samt CC-BY-SA-Quellenangabe in einem Unterrichtsmaterial. Passt der
Artikel nicht, ist das Ergebnis ``None`` und das LLM arbeitet mit seinem
eigenen Fachwissen weiter.

Bekannte Grenze (unveraendert aus ALT uebernommen): der Filter ist an den
Raendern zu streng — „Bruchrechnen" → *Bruchrechnung* verwirft er. Die
Heuristik selbst ist byte-genau die ALT-Fassung; sie hier zu veraendern waere
ein eigener Schritt mit eigener Absicherung.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from boerdi.services.mcp.client import call_mcp_tool
from boerdi.services.mcp.parsers import parse_wikipedia_summary

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    """Lowercase, strip diacritics + non-alnum, collapse whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9äöüß ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


_STOP = {
    "und", "oder", "der", "die", "das", "den", "dem", "des",
    "ein", "eine", "einer", "einem", "eines", "für", "fuer",
    "klasse", "schule", "stufe", "sek", "kl",
    "stadt", "land", "ort",  # generic location words — don't let them alone match
}


def _word_match(word: str, normalized_text: str) -> bool:
    """Whole-word match in a whitespace-normalized text.

    Uses padded substring check ('\\s+word\\s+' in '\\s+text\\s+') instead
    of raw `word in text`, because plain substring would accept
    'berlin' in 'ueberlingen' (b-e-r-l-i-n is a substring of ueb-erlin-gen).
    """
    if not word or not normalized_text:
        return False
    return f" {word} " in f" {normalized_text} "


def _is_relevant(topic: str, title: str, extract: str) -> bool:
    """True if the article looks genuinely about `topic`.

    Strategie (von stark nach schwach):
      1. Direkte Enthaltenheit: Topic == Title, Topic ⊂ Title, Title ⊂ Topic
      2. Multi-Word-Topic (≥2 Original-Tokens): das laengste Content-Word
         muss als GANZES Wort im Titel auftreten. Verhindert:
           - "Stadt Berlin" → "Stadtbergen"     ('berlin' ∉ 'stadtbergen')
           - "Stadt Berlin" → "Stadt Ueberlingen" ('berlin' ∉ Wortgrenze)
      3. Single-Word-Topic: Word-Match in Title oder Extract ODER
         bidirektionaler Prefix ≥ 5 Zeichen (fängt "Bruchrechnung" ↔
         "Bruch (Mathematik)", "Feinoptik" ↔ "Feinoptiker").
    """
    t = _normalize(topic)
    nt = _normalize(title)
    ne = _normalize(extract[:300])
    if not t:
        return False

    # 1. Direct containment (rare but strong)
    if t == nt or t in nt or nt in t:
        return True

    original_tokens = t.split()
    content_words = [w for w in original_tokens if len(w) >= 4 and w not in _STOP]
    if not content_words:
        return False

    # 2. Multi-word topic: longest content word must appear as a whole word
    #    in the title.
    if len(original_tokens) >= 2:
        longest = max(content_words, key=len)
        return _word_match(longest, nt)

    # 3. Single-word topic.
    word = content_words[0]
    if _word_match(word, nt) or _word_match(word, ne):
        return True
    # Morphological relatives: "Bruchrechnung" ↔ "Bruch", "Feinoptik" ↔
    # "Feinoptiker". Word must share a common prefix of at least 5 chars
    # with a full word in the title.
    #
    # Sprint 7 (2026-05-19) Bug-Fix: vorher hat die Regel jeden gemeinsamen
    # Prefix akzeptiert — das hat false positives wie "Dreiecke" (Topic
    # Mathematik) → "Dreiecker" (Bergname) ergeben, weil "dreiecker"
    # "dreiecke" als Prefix enthielt. Die 1-Char-Erweiterung kann ein
    # völlig anderer Begriff sein (Dreieck-er, -e, -s …). Daher:
    #   - Wenn das Title-Wort LÄNGER ist als das Topic → der Suffix muss
    #     ein typischer ≥2-Char-Morphologie-Suffix sein (Inflektion oder
    #     Wortbildung). 1-Char-Suffixe sind verboten (außer pluralisches
    #     "-n" nach Konsonant — verhindern Edge-Cases zu hart).
    #   - Wenn das Topic LÄNGER ist → klare Compound-Beziehung, weiter
    #     ohne zusätzliche Suffix-Prüfung erlauben (z.B. "Bruchrechnung"
    #     enthält "Bruch" am Wortanfang).
    _SAFE_SUFFIXES = (
        # Wortbildungs-Suffixe (klar abgeleiteter Begriff)
        "ung", "heit", "keit", "schaft", "tum", "lich", "bar", "isch",
        "iker", "iger", "isch", "haft", "lein", "chen",
        # Klassische Inflektion (Plural / Genus)
        "en", "es", "em", "ern", "ens", "eln",
        # 2-Char-Endungen die professions-/zugehörigkeits-Suffixe sind
        "er",
    )
    for tw in nt.split():
        if len(tw) < 5:
            continue
        # Topic-länger: Compound mit Title-Wort am Anfang (z.B.
        # "bruchrechnung".startsWith("bruch")) — sicher.
        if len(word) > len(tw) and word.startswith(tw):
            return True
        # Title-länger: nur erlauben wenn der Anhang eine erkannte
        # ≥2-Char-Morphologie ist.
        if len(tw) > len(word) and tw.startswith(word):
            suffix = tw[len(word):]
            if len(suffix) >= 2 and any(suffix == s for s in _SAFE_SUFFIXES):
                return True
            # Suffix ist 1 Char oder unerkannt → wahrscheinlich anderer
            # Begriff (z.B. "Dreiecker" für "Dreiecke") → ABLEHNEN.

    return False


async def fetch_wikipedia_summary(topic: str) -> dict[str, Any] | None:
    """Resolve a topic to a Wikipedia article summary, if relevant.

    Returns a dict with keys {title, extract, url}, or None when the tool found
    nothing, the hit failed the relevance check, or the call itself failed.
    Never raises — the caller falls back to LLM-only knowledge.

    ``description`` (the one-line Wikidata subtitle) is gone with the transport
    swap: the MCP tool does not carry it. No caller read it.

    ``outputFormat="json"`` is set centrally in ``call_mcp_tool``
    (``_JSON_CAPABLE_TOOLS``), so it is not repeated here.
    """
    q = (topic or "").strip()
    if not q:
        return None

    try:
        raw = await call_mcp_tool("get_wikipedia_summary", {"query": q})
    except Exception as e:  # noqa: BLE001 — Anreicherung ist optional, nie fatal
        logger.info("wiki lookup failed for %r: %s", q, e)
        return None

    hit = parse_wikipedia_summary(raw)
    extract = (hit.get("extract") or "").strip()
    title = (hit.get("title") or "").strip()
    if not extract or not title:
        logger.info("wiki: no hit for %r", q)
        return None

    if not _is_relevant(q, title, extract):
        logger.info("wiki reject irrelevant hit for %r: %r", q, title)
        return None

    return {"title": title, "extract": extract, "url": hit.get("url") or ""}
