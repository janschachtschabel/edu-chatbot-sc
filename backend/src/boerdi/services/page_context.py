"""Page-Context-Service — Resolve current page to structured metadata.

When the widget is embedded on a theme page (or on an edu-sharing render
URL), the frontend passes `page_context` with one or more of:

    - node_id         (edu-sharing uuid, e.g. 'a1b2c3d4-...')
    - collection_id   (same uuid, different semantic)
    - topic_page_slug (wirlernenonline.de/themenseite/<slug>)
    - subject_slug    (wirlernenonline.de/fachportal/<subject>/…)
    - search_query    (active search term on host page)
    - document_title  (fallback signal)

This service turns that opaque blob into a structured `PageMetadata`
dict that the system prompt can present semantically. The result is
cached on `session_state.entities._page_metadata` and TTL-guarded so
the MCP call happens at most once per session (unless the URL changes).

Design decisions:
  - Best-effort: every MCP failure degrades to "unresolved" — the chat
    keeps working, the LLM just sees less context.
  - Page-context is the source of truth for "where is the user?" —
    don't overwrite existing metadata if the node_id is the same.
  - No blocking: callers that can't await (e.g. the classifier prompt
    builder) should just use whatever's cached.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from boerdi.services.mcp.client import call_mcp_tool, is_mcp_error

logger = logging.getLogger(__name__)

# Cache key lives in session_state["entities"] under this name
_META_KEY = "_page_metadata"
_META_TTL_SECONDS = 60 * 30        # 30 min for successfully resolved pages
_UNRESOLVED_TTL_SECONDS = 60 * 2   # 2 min for unresolved/failed — retry soon


def _current_context_signature(page_context: dict[str, Any]) -> str:
    """Stable hash of the fields we resolve against, to detect URL changes."""
    keys = ("node_id", "collection_id", "topic_page_slug", "subject_slug")
    return "|".join(str(page_context.get(k) or "") for k in keys)


def _cached_is_fresh(
    session_state: dict[str, Any],
    signature: str,
) -> bool:
    cached = (session_state.get("entities") or {}).get(_META_KEY)
    if not isinstance(cached, dict):
        return False
    if cached.get("_signature") != signature:
        return False
    ts = cached.get("_resolved_at") or 0
    # Unresolved entries expire much faster so transient MCP outages don't
    # lock us out of context for half an hour. Successful resolutions keep
    # the long TTL (theme pages rarely change).
    ttl = (
        _UNRESOLVED_TTL_SECONDS if cached.get("unresolved")
        else _META_TTL_SECONDS
    )
    return (time.time() - ts) < ttl


def get_cached(session_state: dict[str, Any]) -> dict[str, Any] | None:
    """Return cached metadata (if any) without triggering a fetch."""
    cached = (session_state.get("entities") or {}).get(_META_KEY)
    if isinstance(cached, dict) and cached.get("title"):
        return cached
    return None


# ────────────────────────────────────────────────────────────────────
# Parsing helpers for MCP responses (they return plain text / JSON-ish
# bodies depending on the tool). We try JSON first, then fall back to
# regex-based extraction of the fields we care about.
# ────────────────────────────────────────────────────────────────────


def _safe_json(text: str) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_node_fields(raw: str) -> dict[str, Any]:
    """Pull title/description/keywords/disciplines/stufen from `get_node_details`.

    Accepts (in order of preference):
      1. The MCP v2+ `outputFormat="json"` shape — flat FormattedNode with
         label-resolved fields (`disciplines`, `educationalContexts`, …).
      2. The legacy edu-sharing JSON shape with `ccm:*` properties
         (kept as a fallback so old MCP servers still work).
      3. The "Key: Value" Markdown block (default `outputFormat="markdown"`).

    Missing fields degrade to empty strings/lists.
    """
    out: dict[str, Any] = {
        "title": "",
        "description": "",
        "keywords": [],
        "disciplines": [],
        "educational_contexts": [],
        "learning_resource_types": [],
        "url": "",
        "compendium_text": "",
        "text_content": "",
        "has_compendium": False,
    }
    if not raw:
        return out

    data = _safe_json(raw)
    if isinstance(data, dict):
        # 1. MCP v2+ shape: flat FormattedNode with camelCase keys and label
        #    arrays. We detect it via the presence of `nodeId` AND any of
        #    the camelCase label keys at the top level.
        if data.get("nodeId") and (
            "disciplines" in data
            or "educationalContexts" in data
            or "learningResourceTypes" in data
        ):
            def _str(k: str) -> str:
                v = data.get(k)
                return v if isinstance(v, str) else ""

            def _strlist(k: str) -> list[str]:
                v = data.get(k)
                if isinstance(v, list):
                    return [str(x) for x in v if x]
                if isinstance(v, str) and v:
                    return [v]
                return []

            out["title"] = _str("title")
            out["description"] = _str("description")
            out["keywords"] = _strlist("keywords")
            out["disciplines"] = _strlist("disciplines")
            out["educational_contexts"] = _strlist("educationalContexts")
            out["learning_resource_types"] = _strlist("learningResourceTypes")
            out["url"] = _str("url") or _str("renderUrl")
            # Compendium (collections) + full text (content) — only present on
            # the `-all-` detail path; absent in search/list JSON, so these
            # stay "" there. camelCase from formatNode → snake_case here.
            out["compendium_text"] = _str("compendiumText")
            out["text_content"] = _str("textContent")
            # Server 2026-08-20: die Detail-Antwort trägt den Text nicht mehr
            # inline, nur noch das Signal — der Aufrufer lädt dann nach.
            out["has_compendium"] = data.get("hasCompendium") is True
            if out["title"]:
                return out

        # 2. Legacy edu-sharing JSON: "properties" wrapper or top-level ccm:*
        props = (
            data.get("properties")
            or data.get("node", {}).get("properties")
            or data
        )
        if isinstance(props, dict):
            def _first(keys: list[str]) -> str:
                for k in keys:
                    v = props.get(k)
                    if isinstance(v, list) and v:
                        return str(v[0])
                    if isinstance(v, str) and v:
                        return v
                return ""

            def _list(keys: list[str]) -> list[str]:
                for k in keys:
                    v = props.get(k)
                    if isinstance(v, list) and v:
                        return [str(x) for x in v if x]
                    if isinstance(v, str) and v:
                        return [v]
                return []

            out["title"] = _first(["cm:title", "cm:name", "title", "name"])
            out["description"] = _first([
                "cclom:general_description", "description",
            ])
            out["keywords"] = _list(["cclom:general_keyword", "keywords"])
            out["disciplines"] = _list([
                "ccm:taxonid_DISPLAYNAME", "disciplines",
                "ccm:taxonid",
            ])
            out["educational_contexts"] = _list([
                "ccm:educationalcontext_DISPLAYNAME",
                "ccm:educationalcontext", "educational_contexts",
            ])
            out["learning_resource_types"] = _list([
                "ccm:oeh_lrt_aggregated_DISPLAYNAME",
                "ccm:oeh_lrt_aggregated", "learning_resource_types",
            ])
            out["url"] = _first(["wwwurl", "url", "ccm:wwwurl"])
            if out["title"]:
                return out

    # 3. Fallback: parse "Key: Value" text body (markdown output)
    def _grab(pattern: str) -> str:
        m = re.search(pattern, raw, re.IGNORECASE | re.MULTILINE)
        return (m.group(1) or "").strip() if m else ""

    def _grab_list(pattern: str) -> list[str]:
        txt = _grab(pattern)
        if not txt:
            return []
        # comma- or pipe-separated
        parts = re.split(r"[,;|]\s*", txt)
        return [p.strip() for p in parts if p.strip()]

    out["title"] = _grab(r"^Titel\s*[:\-]\s*(.+)$") or _grab(r"^Title\s*[:\-]\s*(.+)$")
    out["description"] = _grab(r"^Beschreibung\s*[:\-]\s*(.+)$") or _grab(
        r"^Description\s*[:\-]\s*(.+)$"
    )
    out["keywords"] = _grab_list(r"^(?:Keywords|Schlagworte)\s*[:\-]\s*(.+)$")
    out["disciplines"] = _grab_list(r"^(?:Fächer|Disciplines|Fach)\s*[:\-]\s*(.+)$")
    out["educational_contexts"] = _grab_list(
        r"^(?:Bildungsstufen?|Stufen?|Educational\s*Context)\s*[:\-]\s*(.+)$"
    )
    out["learning_resource_types"] = _grab_list(
        r"^(?:Materialtypen?|Resource\s*Types?|LRT)\s*[:\-]\s*(.+)$"
    )
    out["url"] = _grab(r"^URL\s*[:\-]\s*(\S+)$")
    return out


# ────────────────────────────────────────────────────────────────────
# Main resolve entry point
# ────────────────────────────────────────────────────────────────────


def _host_title(page_context: dict[str, Any]) -> str:
    """Der vom Gastgeber gelieferte Seitentitel — mit ``title`` als Alias.

    ``document_title`` setzt nur das Widget aus seiner EIGENEN Erkennung
    (``chat-api.extractPageContext``); Gastgeber-Rahmen senden den Tab-Titel
    naheliegend als ``title`` (EK8, Live-Befund Prüftisch 2026-08-21). Ohne den
    Alias fiel er durch, und Gruß wie Prompt zitierten den Z2-Platzhalter
    „Seite mit nicht auflösbarem Inhalt" als wäre er der Seitenname. Das
    ausdrücklich benannte Feld gewinnt.
    """
    return str(
        page_context.get("document_title") or page_context.get("title") or ""
    ).strip()


async def resolve_page_context(
    page_context: dict[str, Any],
    session_state: dict[str, Any],
    *,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    """Resolve the host page's metadata via MCP and cache it on session_state.

    Returns the resolved metadata dict, or None if nothing was resolvable.
    Never raises — on any failure, returns None and logs.

    Strategy:
      1. If `node_id` / `collection_id` is present → call `get_node_details`.
      2. Else if `topic_page_slug` is present → call `search_wlo_topic_pages`
         with the slug as query and take the top hit's nodeId, then node_details.
      3. Else: cache a minimal {"title": document_title, "unresolved": True}
         so the prompt can at least show the page title.
      4. TTL-cached per (node_id|collection_id|slug) signature.
    """
    if not isinstance(page_context, dict) or not page_context:
        return None

    signature = _current_context_signature(page_context)
    if not signature.strip("|"):
        # No addressable context — only titles/search_query — minimal fallback
        title = _host_title(page_context)
        if not title:
            return None
        meta = {
            "title": title,
            "description": "",
            "keywords": [],
            "disciplines": [],
            "educational_contexts": [],
            "learning_resource_types": [],
            "url": "",
            "source": "document_title_only",
            "unresolved": True,
            "_signature": signature,
            "_resolved_at": time.time(),
        }
        session_state.setdefault("entities", {})[_META_KEY] = meta
        return meta

    if not force_refresh and _cached_is_fresh(session_state, signature):
        return (session_state.get("entities") or {}).get(_META_KEY)

    node_id = (page_context.get("node_id") or "").strip()
    collection_id = (page_context.get("collection_id") or "").strip()
    slug = (page_context.get("topic_page_slug") or "").strip()
    page_kind = (page_context.get("page_kind") or "").strip().lower()

    meta: dict[str, Any] | None = None

    try:
        # Path 1: direct node_id / collection_id → get_node_details (JSON)
        # JSON output gives us label-resolved disciplines/educationalContexts
        # without further URI-→-label cache lookups in Boerdi.
        target_id = node_id or collection_id
        if target_id:
            # Full text is only meaningful for single content items and costs
            # one extra edu-sharing GET MCP-side — request it only there, not
            # for collections/topic pages.
            args: dict[str, Any] = {"nodeId": target_id, "outputFormat": "json"}
            if page_kind in ("content", "editorial"):
                args["includeTextContent"] = True
            raw = await call_mcp_tool("get_node_details", args)
            if raw and not is_mcp_error(raw):
                fields = _extract_node_fields(raw)
                if fields.get("title"):
                    meta = {
                        **fields,
                        "node_id": target_id,
                        "source": "get_node_details",
                        "unresolved": False,
                    }

        # Path 2: topic page slug → search_wlo_topic_pages → node_details
        if meta is None and slug:
            query = slug.replace("-", " ").replace("_", " ")
            raw = await call_mcp_tool(
                "search_wlo_topic_pages",
                {"query": query, "maxResults": 1},
            )
            if raw and not is_mcp_error(raw):
                # Try to extract a nodeId out of the response text.
                m = re.search(
                    r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
                    raw,
                )
                if m:
                    found_id = m.group(0)
                    raw2 = await call_mcp_tool(
                        "get_node_details",
                        {"nodeId": found_id, "outputFormat": "json"},
                    )
                    if raw2 and not is_mcp_error(raw2):
                        fields = _extract_node_fields(raw2)
                        if fields.get("title"):
                            meta = {
                                **fields,
                                "node_id": found_id,
                                "source": "topic_page_slug",
                                "unresolved": False,
                            }

        # Seit dem MCP-Deploy 2026-08-20 kommt der Kompendiumstext nur noch
        # über get_compendium_text; die Detail-Antwort signalisiert ihn bloß.
        # Bewusst ohne ``query``: der Seitenkontext braucht den Überblick
        # (Inhaltsverzeichnis + gekappte Abschnitte), keine Passagen zu einer
        # Frage — die stellt erst das Modell, mit eigenem Aufruf.
        if meta is not None and meta.get("has_compendium") and not meta.get("compendium_text"):
            raw3 = await call_mcp_tool("get_compendium_text", {"nodeId": meta["node_id"]})
            if raw3 and not is_mcp_error(raw3):
                meta["compendium_text"] = raw3

    except Exception as e:
        logger.warning("page_context resolve failed: %s", e)
        meta = None

    if meta is None:
        # Final fallback: document_title as placeholder so LLM has *something*.
        # Z2 (2026-08-20): eine ADRESSIERBARE ID überlebt auch ohne Titel —
        # vorher verschwand der ganze Block, und das Modell fragte den Nutzer
        # nach der Node-ID, die die Seite längst geliefert hatte (Live-Befund
        # edu-sharing Prüftisch: anonymer Bot, unveröffentlichter Knoten, 403).
        title = _host_title(page_context) or slug or ""
        target_id = node_id or collection_id
        if not title and not target_id:
            return None
        meta = {
            "title": title or "Seite mit nicht auflösbarem Inhalt",
            "description": "",
            "keywords": [],
            "disciplines": [],
            "educational_contexts": [],
            "learning_resource_types": [],
            "url": "",
            "source": "fallback_title" if title else "unresolved_node",
            "unresolved": True,
        }
        if node_id:
            meta["node_id"] = node_id

    meta["_signature"] = signature
    meta["_resolved_at"] = time.time()
    session_state.setdefault("entities", {})[_META_KEY] = meta
    logger.info(
        "page_context resolved: title=%r source=%s disciplines=%s",
        meta.get("title"), meta.get("source"), meta.get("disciplines"),
    )
    return meta


# ────────────────────────────────────────────────────────────────────
# Prompt rendering — turn metadata into a semantic block for the LLM
# ────────────────────────────────────────────────────────────────────


def _trim_text(text: str, budget: int) -> str:
    """Trim to a character budget on a word boundary, adding an ellipsis
    marker. Used for the compendium / full-text prompt blocks so a very long
    editorial text can't blow the prompt budget."""
    text = text.strip()
    if len(text) <= budget:
        return text
    return text[: budget - 1].rsplit(" ", 1)[0] + "…"


#: Wie viele Anleitungen die Übersicht höchstens nennt (Nutzer-Vorgabe
#: 2026-08-14: „die registry bitte vollständig rein geben — kann man ab 100
#: kappen — bis dahin aber keine einschränkung").
#:
#: Öffentlich, weil ``services/context_facts`` denselben Deckel schon beim
#: Sammeln anlegt: was hier nie erscheint, muss auch nicht je Zug als jsonb
#: mitgeschrieben werden. Eine Konstante statt zweier gleicher Zahlen.
MAX_SKILL_ENTRIES = 100

#: Zeichenbudget der Skill-Übersicht — die A4-Seite als Zusicherung, nicht als
#: Erwartung (Nutzer-Vorgabe 2026-08-14: „nicht mehr als eine A4 Seite").
#:
#: Der Eintragsdeckel allein genügt dafür nicht: 100 Titel sind an der echten
#: Registry gemessen 3 361 Zeichen (Schnitt 30,6), aber Titellängen sind
#: redaktionell und niemand hat sie zugesagt. Was zuerst greift, greift —
#: der Rest wird als „… und N weitere" benannt, nie stillschweigend.
#: 3 500 Zeichen ≈ eine A4-Seite Fließtext.
MAX_SKILL_CHARS = 3500

#: Platz, den :func:`_bestands_zeilen` für die „… und N weitere"-Zeile plus die
#: beiden Leerzeilen zurücklegt. Sie entsteht erst NACH der Titel-Schleife, muss
#: aber vorher bezahlt sein — sonst reisst genau der Fall das Budget, für den
#: der Deckel da ist. Gemessen sind es 76 Zeichen; 120 lassen Luft für eine
#: umformulierte Zeile.
_REST_ZEILE_RESERVE = 120


def _bestands_zeilen(fakten: Any) -> list[str]:
    """Der Bestandsabschnitt: Zahlen + Skill-Übersicht — oder gar nichts.

    Nutzer-Vorgabe 2026-08-14: „Inhaltsanzahl und Skillregistry muss man in
    beiden Modi aktiv rein geben — pattern und agent loop". Beide Engines lesen
    ihren Seitenblock über :func:`render_for_prompt`, also steht es hier ein
    einziges Mal statt zweimal an ihren getrennten Prompt-Bauern.

    **Nur Titel, keine Inhalte und keine IDs** (Nutzer-Vorgabe: „nicht die
    vollen Skillinhalte … nur die Übersicht … nicht mehr als eine A4 Seite").
    Die beiden Zahlen der Vorgabe — vollständig bis 100, höchstens eine
    A4-Seite — gehen nur so zusammen; an der echten Registry nachgemessen
    (28 Einträge, Titel im Schnitt 30,6 Zeichen): 100 Titel sind 3 361 Zeichen
    (eine Seite), 100 Titel mit ``nodeId`` wären 7 161 (gut zwei).

    Der Preis ist ein Aufruf mehr: ohne ID muss das Modell
    ``get_skill_registry`` voranstellen — mit der Sammlungs-ID, die derselbe
    Block wenige Zeilen weiter unten nennt. Das ist ohnehin der Weg, den die
    Werkzeugbeschreibung vorgibt („der zweite Schritt nach
    get_skill_registry") — deshalb nennt der Block beide.

    **Bis 2026-08-15 stand hier ``search_skill``**, und das war ein Verweis ins
    Leere: das Werkzeug ist seit dem 2026-08-13 aus jedem Pfad genommen
    (``agent_tools.AUS_DEM_KATALOG``, ``_NICHT_UEBER_PATTERN``), dieser Block
    entstand einen Tag später. Der Agent-Lauf merkte nichts davon, weil
    ``respond_agent`` die Registry vorab in die Kette holt; der Mustermodus hat
    keinen Vorabruf, und für ihn endete der Weg damit vor dem ersten Schritt.
    Gepinnt von ``test_der_block_nennt_den_weg_den_das_modell_auch_gehen_kann``.

    **Der Rang der Anleitungen steht seit 2026-08-16 im Hinweis** (Nutzer-Regel:
    „skills stehen dabei über den mustern die der chatbot von haus aus
    mitbringt"). Vorher nannte der Block den Weg zur Anleitung, aber nicht ihren
    Vorrang — im selben Prompt stand die mitgelieferte Muster-Vorlage, und keine
    Regel sagte, welche gewinnt. Der Befund: der Bot nahm seine eigene. Der
    Hinweis wächst dadurch, das Titel-Budget schrumpft entsprechend — die
    A4-Zusage rechnet ihn ab (``budget`` unten), sie bricht also nicht.

    Der Routing-Teil derselben Regel wohnt in ``domain/skill_precedence``: er
    nimmt die Schnellwege aus dem Weg, damit dieser Block überhaupt gelesen
    wird. Ein Schnellweg baut nie einen Antwort-Prompt.

    Ohne Fakten eine leere Liste: eine Überschrift ohne Inhalt liest sich für
    das Modell wie ein Ausfall und lädt zum Erfinden ein.
    """
    if not isinstance(fakten, dict) or not fakten:
        return []

    zeilen: list[str] = []
    materialien = fakten.get("materials")
    unter = fakten.get("sub_collections")
    if isinstance(materialien, int):
        satz = f"Bestand dieser Sammlung: {materialien} Materialien"
        if isinstance(unter, int) and unter:
            satz += f", {unter} Untersammlungen"
        zeilen.append(satz)

    skills = fakten.get("skills")
    titel = [t for t in (fakten.get("skill_titles") or []) if isinstance(t, str) and t]
    if not isinstance(skills, int) or not skills:
        return zeilen

    ueberschrift = f"### Freigegebene Skills dieser Sammlung — {skills}"
    hinweis = (
        "Diese Skills sind für GENAU diese Sammlung freigegeben und gehen "
        "deinen mitgelieferten Vorlagen VOR: Deckt einer von ihnen die Frage ab, "
        "arbeite nach ihm — auch dann, wenn du für dieselbe Ausgabe eine eigene "
        "Vorlage hättest. Dies ist "
        "die Teil-Registry dieser Seite: Titel, ohne IDs und ohne Inhalt. Passt "
        "einer zur Frage, geh die zwei Stufen weiter — ``get_skill_registry`` mit "
        "der unten genannten Sammlungs-ID nennt zu jedem Titel die ``nodeId`` "
        "samt Verwendungshinweis der Redaktion, dann liefert ``get_skill`` mit "
        "dieser ``nodeId`` den Wortlaut — und arbeite danach, statt den Ablauf "
        "selbst zu erfinden."
    )
    # Das Budget gilt dem ABSCHNITT, nicht nur der Liste — es ist die Zusage
    # „höchstens eine A4-Seite". Überschrift, Hinweis und die Rest-Zeile stehen
    # fest, also gehen sie vorweg ab; was bleibt, ist für Titel.
    budget = (MAX_SKILL_CHARS - len(ueberschrift) - len(hinweis)
              - _REST_ZEILE_RESERVE)
    gezeigt: list[str] = []
    for t in titel[:MAX_SKILL_ENTRIES]:
        budget -= len(t) + 3          # „- " plus Zeilenumbruch
        if budget < 0:
            break
        gezeigt.append(t)

    zeilen.append("")
    zeilen.append(ueberschrift)
    zeilen.extend(f"- {t}" for t in gezeigt)
    if skills > len(gezeigt):
        zeilen.append(
            f"- … und {skills - len(gezeigt)} weitere — die vollständige Liste "
            f"liefert ``get_skill_registry``.")
    zeilen.append(hinweis)
    zeilen.append("")
    return zeilen


def render_for_prompt(
    meta: dict[str, Any] | None,
    page_context: dict[str, Any] | None = None,
    *,
    include_stock: bool = True,
) -> str:
    """Human-readable block for the system prompt.

    Returns empty string if no usable metadata. Otherwise returns a
    German-language block the LLM can reference directly.

    ``page_context`` (optional, passed-through from the widget) liefert
    Page-Kind und URL-Query-Filter (``search_query``) — Infos die das
    MCP-resolved ``meta`` nicht hat. Wenn vorhanden, generiert die
    Funktion eine Sammlungs-spezifische Überschrift + nennt Filter
    und IDs explizit, damit das LLM ``get_collection_contents`` mit
    der richtigen ``collection_id`` aufrufen kann.

    ``meta['context_facts']`` (optional, von ``page_context_enrich``
    angehängt) trägt Bestandszahlen und Skillkatalog; :func:`_bestands_zeilen`
    rendert sie.

    ``include_stock=False`` lässt genau diesen Abschnitt weg. Diese Funktion
    speist DREI Prompts: Muster-Engine, Agent-Schleife — und den Klassifikator.
    Der wählt ein Muster und ruft keine Skills auf; der Katalog kostete ihn
    gemessene 2 232 Zeichen je Zug und veränderte seinen Prompt, wofür der Plan
    einen Golden-Lauf verlangt. Vorgabe bleibt AN, damit die zwei gewollten
    Verbraucher nichts tun müssen.
    """
    if not isinstance(meta, dict):
        return ""
    title = (meta.get("title") or "").strip()
    if not title:
        return ""

    pc = page_context if isinstance(page_context, dict) else {}
    page_kind = (pc.get("page_kind") or "").lower()
    collection_id = (pc.get("collection_id") or "").strip()
    node_id = (pc.get("node_id") or "").strip() or (meta.get("node_id") or "").strip()
    search_query = (pc.get("search_query") or "").strip()

    # Seitentyp-Label — Sammlung ist NICHT Themenseite. Vorher hatten wir
    # immer "## Aktuelle Themenseite" was bei Collection-Pages irreführend
    # war (Bot dachte er sei auf einer Themenseite und antwortete generisch).
    heading_map = {
        "topic": "Themenseite",
        "collection": "Sammlung (edu-sharing)",
        "content": "Inhaltsseite (Einzelmaterial)",
        "subject": "Fachportal",
        "search": "Such-Ergebnisseite",
        # EK2: der Prüftisch des Repositoriums — die Person ERSCHLIESST den
        # Inhalt gerade, sie schaut ihn nicht an.
        "editorial": "Erschließung eines Einzelinhalts (Prüftisch/Redaktion)",
    }
    heading = heading_map.get(page_kind, "Aktuelle Seite")
    lines: list[str] = [f"## Aktuelle Seite — {heading}"]
    lines.append(f"Titel: {title}")

    desc = (meta.get("description") or "").strip()
    if desc:
        if len(desc) > 400:
            desc = desc[:397].rsplit(" ", 1)[0] + "…"
        lines.append(f"Beschreibung: {desc}")

    # Kompendialer Text — die redaktionelle Soll-Beschreibung einer Sammlung,
    # sachrichtigste Quelle für die Zusammenfassung. Eigenes Budget (4000),
    # damit ein langer Text den Prompt nicht sprengt.
    compendium = (meta.get("compendium_text") or "").strip()
    if compendium:
        lines.append("")
        lines.append("### Kompendialer Text der Sammlung (redaktionelle Soll-Beschreibung)")
        lines.append(_trim_text(compendium, 4000))
        lines.append("")

    # Volltext — nur bei Einzelinhalten (content) abgerufen. Eigenes Budget (3000).
    text_content = (meta.get("text_content") or "").strip()
    if text_content:
        lines.append("")
        lines.append("### Volltext der Seite (gespeicherter Inhalt)")
        lines.append(_trim_text(text_content, 3000))
        lines.append("")

    disc = meta.get("disciplines") or []
    if disc:
        lines.append(f"Fächer: {', '.join(disc[:5])}")

    ctx = meta.get("educational_contexts") or []
    if ctx:
        lines.append(f"Bildungsstufen: {', '.join(ctx[:5])}")

    kw = meta.get("keywords") or []
    if kw:
        lines.append(f"Schlagworte: {', '.join(kw[:8])}")

    lrt = meta.get("learning_resource_types") or []
    if lrt:
        lines.append(f"Materialtypen auf der Seite: {', '.join(lrt[:6])}")

    if include_stock:
        lines.extend(_bestands_zeilen(meta.get("context_facts")))

    # IDs für direkte MCP-Tool-Calls. ``collection_id`` ist die Sammlungs-
    # Node-ID auf edu-sharing — das LLM kann ``get_collection_contents``
    # damit direkt aufrufen statt blind zu suchen.
    if collection_id:
        lines.append(f"Sammlungs-ID (collection_id): {collection_id}")
    elif node_id:
        lines.append(f"Node-ID: {node_id}")

    # Gescheiterte Auflösung, ZWEI voneinander unabhängige Regeln (EK3,
    # 2026-08-20). Sie standen bis dahin ineinander verschachtelt, und das war
    # der Fehler: der Seitentext hing an einer Bedingung, mit der er nichts zu
    # tun hat.
    #
    # (1) Rechte-Note — nur MIT ID (Z2). Ohne diese Zeilen fragte das Modell den
    #     Nutzer nach genau der ID, die im Block steht, oder suchte chancenlos
    #     nach dem Titel (der Index kennt nur Öffentliches). Auf einer Seite
    #     OHNE ID wäre sie sachlich falsch — dort fehlen keine Leserechte, die
    #     Seite ist schlicht kein WLO-Objekt.
    # (2) Sichtbarer Seitentext — sobald er da ist. Seit Z2 ist der unaufgelöste
    #     Block nie mehr leer, also griff der ``or``-Rückfall auf
    #     ``render_raw_for_prompt`` (der einzige Renderer, der ``page_text``
    #     kannte) in den drei Verbrauchern nicht mehr. Mit ID war das der
    #     Prüftisch-Befund (EK1); ohne ID trifft es fast jede fremde Seite, wo
    #     der Browser-Harvest die einzige Textquelle ist — hinter Login-Wänden
    #     und in Schul-Intranets erreicht ``get_url_text`` die Seite nie.
    _unaufgeloest = bool(meta.get("unresolved"))
    _seitentext = (pc.get("page_text") or "").strip() if _unaufgeloest else ""

    if _unaufgeloest and (collection_id or node_id):
        lines.append(
            "Hinweis: Die Metadaten dieser Seite konnten NICHT aus dem Bestand "
            "aufgelöst werden — vermutlich fehlen dem (anonymen) Zugriff die "
            "Leserechte, z. B. bei unveröffentlichtem Material. Die ID oben "
            "liegt bereits vor: NICHT beim Nutzer danach fragen, und keine "
            "Titelsuche versuchen (der Suchindex kennt nur Öffentliches). "
            + (
                "Der sichtbare Text der Seite steht unten in diesem Block — "
                "arbeite damit, statt nach dem Inhalt zu fragen."
                if _seitentext else
                "Wird der Inhalt gebraucht, bitte um den Text bzw. das "
                "Transkript oder verweise auf die Anmeldung, damit der "
                "Zugriff mit Rechten läuft."
            )
        )

    if _seitentext:
        lines.append("")
        lines.append("### Sichtbarer Text der Seite (aus dem Widget)")
        # 3000 wie beim gespeicherten Volltext: der Seitentext ist hier die
        # EINZIGE Inhaltsquelle, und auf dem Prüftisch liegen vor dem
        # Metadaten-Formular ~1800 Zeichen Listen-Harvest — das knappere
        # Rohblock-Budget (1500) schnitte genau das Wertvolle ab.
        lines.append(_trim_text(_seitentext, 3000))
        lines.append("")

    # Aktive URL-Filter (?q=…) — auf Sammlungs-Browse-Seiten der Filter
    # innerhalb der Sammlung. Bot soll diesen Filter weitergeben wenn er
    # innerhalb der Sammlung sucht.
    if search_query:
        lines.append(f"Aktiver Filter / Suchbegriff in der URL: {search_query}")

    # Bezugsquellen-Filter aus der URL (edu-sharing ?filters=…publisher…) —
    # bei Folgesuchen als publisher weiterreichen.
    publisher = (pc.get("search_filters") or {}).get("publisher") or []
    if publisher:
        lines.append(
            f"Aktiver Bezugsquellen-Filter: {', '.join(str(x) for x in publisher)} "
            f"(bei Folgesuchen als publisher weiterreichen)"
        )

    if meta.get("url"):
        lines.append(f"URL: {meta['url']}")

    if meta.get("unresolved"):
        lines.append(
            "(Hinweis: vollständige Seitenmetadaten konnten nicht geladen "
            "werden — nur Seitentitel ist sicher.)"
        )

    lines.append("")
    lines.append(
        "Der Nutzer ist auf dieser Seite eingebettet. Regeln:"
    )
    lines.append(
        "- Bei Fragen wie 'Auf welcher Seite bin ich?', 'Wo bin ich?', "
        "'Worum geht es hier?', 'Was ist das?', 'In welcher Sammlung?' "
        "-> beziehe dich direkt + KONKRET auf Titel + Seitentyp ('Du bist "
        f"hier in der {heading.split()[0]} \"{title}\"'). Nutze den "
        "Sammlungstitel namentlich, NICHT generische WLO-Floskeln."
    )
    if collection_id:
        lines.append(
            f"- Wenn der Nutzer nach 'Materialien hier', 'was ist in dieser "
            f"Sammlung' fragt -> rufe ``get_collection_contents`` mit "
            f"``nodeId={collection_id}`` auf, NICHT eine offene Suche."
        )
    if compendium:
        lines.append(
            "- Der kompendiale Text beschreibt das inhaltliche SOLL der Sammlung. "
            "Wenn der Nutzer fragt, was noch FEHLT / ob die Sammlung vollständig "
            "ist / was man kuratieren sollte -> vergleiche das Soll (Kompendium) "
            "mit dem Ist (``get_collection_contents``) und nenne konkrete Lücken "
            "samt Suchvorschlägen."
        )
    if search_query:
        lines.append(
            f"- Aktueller URL-Filter ist '{search_query}'. Wenn der Nutzer "
            f"'mehr dazu' / 'weiter' / 'andere Treffer' sagt, suche INNERHALB "
            f"der Sammlung mit diesem Filter."
        )
    lines.append(
        "- Bei Create-Anfragen ohne eigenes Thema ('Erstelle mir ein "
        "Arbeitsblatt dazu', 'Mach ein Quiz hierzu') -> nimm den Seitentitel "
        "als Thema."
    )
    lines.append(
        "- Bei 'mehr Material dazu', 'weitere Inhalte', 'andere Materialtypen' "
        "-> Suche mit Titel/Schlagworten starten, passend zu den Bildungsstufen."
    )
    if page_kind == "editorial":
        lines.append(
            "- Die Person ERSCHLIESST diesen Inhalt gerade redaktionell "
            "(Prüftisch): gib auf Wunsch Hinweise zum Inhalt (aus dem "
            "sichtbaren Seitentext bzw. den Metadaten), schlage passende "
            "Sammlungen vor (suche danach mit dem Kernbegriff des Inhalts, "
            "statt zu raten) und hilf bei Metadaten-Feldern wie Fach, Stufe, "
            "Materialtyp oder Beschreibung."
        )
    return "\n".join(lines)


def prompt_block(
    session_state: dict[str, Any], page_context: dict[str, Any] | None
) -> str:
    """Der Seitenblock für einen Prompt — aufgelöst, sonst heuristisch, sonst "".

    Die zweistufige Auflösung stand bis P4 als Handkopie an zwei Stellen
    (``response_prompt_builder``, ``classify_prompt``). Der Agent-Modus im Chat
    ist der dritte Verbraucher; eine dritte Kopie hätte die Regel „MCP-Auflösung
    schlägt DOM-Heuristik" an drei Orten gehalten. Sie wohnt jetzt hier — bei
    den beiden Renderern, die sie in Beziehung setzt.

    Wirft nicht: ein Fehler im Seitenblock darf keinen Zug kosten. Er ist
    Zusatzwissen, nicht die Aufgabe.

    Aber laut: faellt er aus, ist der Agent wieder blind fuer die Seite —
    Befund B-2, gegen den P4 gebaut wurde —, und der Rueckfall sieht von aussen
    aus wie „diese Seite hat eben keinen Kontext". Deshalb WARNING, wie beim
    Vorabruf nebenan; auf ``debug`` liefe der Rueckschritt unbemerkt mit.
    """
    try:
        block = render_for_prompt(get_cached(session_state), page_context)
        return block or render_raw_for_prompt(page_context)
    except Exception:  # noqa: BLE001 — siehe Docstring
        logger.warning("page-context prompt block failed", exc_info=True)
        return ""


def render_raw_for_prompt(page_context: dict[str, Any] | None) -> str:
    """Fallback block when no MCP-resolved metadata is available, but the
    widget's DOM-detector extracted visible page text + heuristic fields.

    This keeps the LLM grounded on pages where the widget can SEE the
    content (most third-party WLO embeddings) but the URL doesn't match
    a known platform pattern that the MCP-resolver could deepen.

    Returns an empty string if no usable raw text is present.
    """
    if not isinstance(page_context, dict):
        return ""
    text = (page_context.get("page_text") or "").strip()
    if not text:
        return ""

    kind = (page_context.get("page_kind") or "other").lower()
    detection = page_context.get("detection_source") or ""

    lines: list[str] = ["## Inhalt der aktuellen Seite (Heuristik)"]
    if kind != "other":
        kind_labels = {
            "topic": "Themenseite",
            "collection": "Sammlung",
            "content": "Inhaltsseite (einzelnes Material)",
            "subject": "Fachportal",
            "search": "Such-Ergebnisseite",
            "editorial": "Erschließung eines Einzelinhalts (Prüftisch)",
        }
        lines.append(f"Seitentyp: {kind_labels.get(kind, kind)}")

    if page_context.get("topic_page_slug"):
        lines.append(f"Themenseite-Slug: {page_context['topic_page_slug']}")
    if page_context.get("subject_slug"):
        lines.append(f"Fach-Slug: {page_context['subject_slug']}")
    if page_context.get("search_query"):
        lines.append(f"Aktiver Suchbegriff: {page_context['search_query']}")
    if detection:
        lines.append(f"Erkennungs-Quelle: {detection}")

    # Cap snippet length — the prompt budget is finite.
    snippet = text if len(text) <= 1500 else text[:1497] + "…"
    lines.append("")
    lines.append("Sichtbarer Text der Seite (gekürzt):")
    lines.append(snippet)
    lines.append("")
    lines.append(
        "Regeln: Wenn der Nutzer mit 'hier', 'auf dieser Seite', 'das "
        "Thema', 'dazu' o.ä. referenziert, beziehe dich auf diese Inhalte. "
        "Sprich vom 'Seiteninhalt', NICHT von 'Auszug' oder 'Heuristik' — "
        "das sind interne Begriffe."
    )
    return "\n".join(lines)
