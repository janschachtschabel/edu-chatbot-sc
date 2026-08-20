"""Page-context enrichment node (P4-2 / R6).

Port of the page-context prep in ALT ``chat_turn_setup._setup_turn`` (lines 92-110):
inject the IDs the widget supplies (``node_id``/``collection_id``/slug/…) into
``session_state['entities']`` so downstream entity-matching sees them, then
best-effort resolve the host page's metadata via MCP. ``resolve_page_context``
caches the result on ``session_state['entities']['_page_metadata']`` — the cache
that ``context_greeting`` reads (Gate 3) and that ``respond``'s ``render_for_prompt``
will read (a later R6 slice).

Placement (why a dedicated node between ``tour`` and ``context_greeting``):

* AFTER tour — ALT returns from the tour branch (``chat_turn_setup:90``) BEFORE this
  block (:92), so a tour tick never pays the MCP-resolve latency. Running it in the
  pre-tour ``setup`` node would resolve on every tick.
* NOT inside ``context_greeting`` — the resolved cache is a shared prerequisite
  (``respond``'s prompt consumes it on every normal turn), so it stays its own node
  on the normal path rather than coupling to the greeting.

Second job, added with the Seitenkontext-Erweiterung: settle the page kind the URL
detector could not (``other``) from the hostname — our own site or somebody else's.
It happens here, before the resolve, so the MCP resolver, the greeting and the prompt
builders all read the same page kind. The decision itself is pure
(``domain/page_host``); this node only supplies the editorially maintained host list.

Never sets ``early_response`` (normal-path node). No session DI: ``resolve_page_context``
talks to MCP, not the DB. ``resolve_page_context`` is best-effort by contract (returns
None, never raises) but the call is still wrapped defensively — a resolver bug must not
break the turn (ALT wrapped it too). Tests patch ``resolve_page_context`` on this module.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from boerdi.domain.page_host import classify_page_host
from boerdi.graph.state import TurnContext
from boerdi.services.config_loader import load_context_actions
from boerdi.services.context_facts import (
    EMPTY_RETRY_SECONDS,
    collect_context_facts,
    empty_marker,
    retry_due,
)
from boerdi.services.page_context import get_cached, resolve_page_context

logger = logging.getLogger(__name__)

# Seitenarten, die überhaupt einen Bestand haben. Ein Einzelinhalt enthält keine
# Materialien und führt keine eigene Freigabeliste — ein Abruf dafür wäre ein
# Rundlauf ins Leere, und er kostet trotzdem Zeit. Themenseiten sind im Bestand
# Sammlungen und zählen deshalb mit.
_BESTANDS_KINDS = ("collection", "topic")

# Only these two are open questions the hostname may answer. Any other kind is a
# positive finding of the URL detector (path + query) and outranks the host: the
# staging collection "Geometrische Optik" sits on one of OUR hosts and would
# otherwise be relabelled ``home``, losing its metadata and its context pills.
_UNDECIDED_KINDS = ("", "other")

_PAGE_CONTEXT_ENTITY_KEYS = (
    "node_id",
    "collection_id",
    "search_query",
    "topic_page_slug",
    "subject_slug",
    "document_title",
    "page_type",
)


#: Die Felder des Seitenkontexts, die ab hier im Zug als Text gelesen werden.
#:
#: ``environment.page_context`` ist im Vertrag ``dict[str, Any]`` — Freiform,
#: damit ein Gastgeber eigene Felder mitgeben kann. Genau das macht die überall
#: übliche Lesart ``(wert or "").strip()`` zur Falle: sie hält jeden TRUTHY
#: Nicht-String für einen String und wirft ``AttributeError``. Falsy Werte
#: (``0``, ``""``, ``None``) waren nie betroffen — deshalb fiel es nie auf.
#:
#: Der gemessene Auslöser (Review 2026-08-20): ein Gastgeber mit numerischem
#: TypeScript-Enum (``enum PageKind { Content, Collection }`` → ``0``/``1``)
#: oder mit Zahl-IDs aus der eigenen Datenbank. Der Zug landete dann in der
#: Fehler-Blase des Endpunkts — nicht einmal, sondern bei JEDEM Zug dieser
#: Einbettung, solange sie so sendet.
#:
#: ``ip`` fehlt bewusst: das liest der ``setup``-Knoten VOR diesem, eine
#: Normalisierung hier käme zu spät — und dort wird es ohne Textoperation nur
#: weitergereicht.
_STRING_FIELDS = (
    "page_kind", "page_host", "page_url", "page_text", "detection_source",
    "node_id", "collection_id", "topic_page_slug", "subject_slug",
    "search_query", "document_title", "page_type",
    # EK8: ``title`` ist der Gastgeber-Alias für ``document_title`` — seit der
    # Resolver ihn liest, gehört er in dieselbe Härtung.
    "title",
)


def _normalize_strings(page_ctx: dict) -> None:
    """Truthy Nicht-Strings der bekannten Textfelder zu Text machen.

    An EINER Stelle statt an jeder Lesestelle, weil dieser Knoten der erste
    Leser dieser Felder im Zug ist: Begrüßung, Resolver und beide Prompt-Bauer
    lesen danach dasselbe Dict.

    ``str()`` statt Verwerfen, weil es den häufigsten Fall gleich mitheilt:
    aus ``collection_id: 4711`` wird die brauchbare Kennung ``"4711"``. Bleibt
    eine Zahl als Seitenart übrig (``"1"``), passt sie auf keine bekannte Art —
    der Bot bietet dann keine Kontext-Knöpfe an, statt zu raten.

    ``None`` bleibt ``None``: ``"None"`` wäre ein Titel, den nie jemand gesetzt
    hat, und würde so im Prompt stehen.
    """
    for key in _STRING_FIELDS:
        wert = page_ctx.get(key)
        if wert is not None and not isinstance(wert, str):
            page_ctx[key] = str(wert)


#: Der Prüftisch des Repositoriums (edu-sharing editorial-desk). Nur der PFAD
#: zählt — ein ``?next=…editorial-desk…`` in einer Login-Weiterleitung ist kein
#: Prüftisch.
_EDITORIAL_DESK_PATH = "/components/editorial-desk"


def _decide_editorial_kind(page_ctx: dict) -> None:
    """EK2 (2026-08-20, Live-Befund Staging): Erschließungs-Situation aus der URL.

    Die editorial-desk-Adresse mit konkretem Knoten fällt beim Erkenner in den
    generischen ``?node``-Zweig (``content``) — und ``content`` begrüßt nur mit
    aufgelöstem Titel, den es auf dem Prüftisch anonym nie gibt (403,
    unveröffentlicht). Anders als die Host-Einordnung darunter darf diese Regel
    eine POSITIVE Einstufung übersteuern: die URL benennt hier die Situation,
    und die ist das schärfere Indiz als der Objekttyp. Serverseitig wie
    ``home``/``external``, damit jeder Einbett-Weg (Repo-Rahmen, Plugin,
    eigenes Widget) den Fix ohne Host-Änderung bekommt. Ohne ``node_id`` bleibt
    alles unangetastet — das ist die Prüftisch-Übersicht, kein Einzelinhalt.
    """
    # ``str()`` bleibt als zweite Sicherung stehen, obwohl ``_normalize_strings``
    # im Knoten davor läuft: die Funktion soll auch für sich genommen halten.
    if not str(page_ctx.get("node_id") or "").strip():
        return
    try:
        path = urlsplit(str(page_ctx.get("page_url") or "")).path.lower()
    except ValueError:
        return
    if _EDITORIAL_DESK_PATH in path:
        page_ctx["page_kind"] = "editorial"


def _decide_host_kind(page_ctx: dict) -> None:
    """Turn an undecided page kind into ``home``/``external`` using the hostname.

    Mutates ``page_ctx`` in place so every later reader — the MCP resolver, the
    greeting, the prompt builders — sees one and the same page kind. Silent on
    every failure: an unreachable config store must not cost the turn, and a
    guessed kind is worse than the honest ``other`` it started with.
    """
    if (page_ctx.get("page_kind") or "").strip().lower() not in _UNDECIDED_KINDS:
        return
    try:
        own_hosts = load_context_actions().get("own_hosts") or []
    except Exception as err:
        logger.warning("own-host list unavailable, page kind left undecided: %s", err)
        return
    kind = classify_page_host(page_ctx.get("page_host"), own_hosts)
    if kind:
        page_ctx["page_kind"] = kind


async def _bestand_anhaengen(page_ctx: dict, session_state: dict) -> None:
    """Bestandszahlen + Skillkatalog an die aufgelösten Seiten-Metadaten hängen.

    Nutzer-Vorgabe 2026-08-14: beide Engines sollen das **aktiv** bekommen,
    sobald eine Sammlung oder Themenseite im Kontext steht. Hier ist der eine
    Ort dafür: dieser Knoten läuft vor der Begrüßung UND vor ``respond``
    (``setup → tour → page_context_enrich → context_greeting → … → respond``),
    also versorgt ein Abruf alle drei Verbraucher. Gerendert wird er in
    ``page_context.render_for_prompt``, das beide Prompt-Bauer lesen.

    An den Metadaten-Cache und nicht an den Zug: der Cache trägt Signatur und
    Ablauf. Wechselt die Seite, schreibt der Resolver ein neues Metaobjekt ohne
    Fakten — der nächste Zug holt sie dann von selbst neu.

    Wirft nicht und wartet nicht ewig: ``collect_context_facts`` deckelt jeden
    Abruf selbst. Fehlt der Bestand, fehlt eine Angabe — kein Zug.
    """
    if (page_ctx.get("page_kind") or "").strip().lower() not in _BESTANDS_KINDS:
        return
    meta = get_cached(session_state)
    if not isinstance(meta, dict) or not retry_due(meta.get("context_facts")):
        return
    collection_id = (page_ctx.get("collection_id") or "").strip() or (
        meta.get("node_id") or ""
    ).strip()
    if not collection_id:
        return
    try:
        fakten = await collect_context_facts(collection_id)
    except Exception as err:
        # ``collect_context_facts`` wirft laut Vertrag nicht — kommt hier doch
        # etwas an, ist es ein Fehler im Code und keine Eigenschaft der Seite.
        # Deshalb KEIN Leer-Vermerk: der Zug soll es erneut versuchen und jedes
        # Mal warnen, statt zwei Minuten lang still zu sein.
        logger.warning("Bestandsfakten nicht abrufbar: %s", err)
        return
    if fakten:
        meta["context_facts"] = fakten
        logger.info("Bestandsfakten geladen: %s Materialien, %s Skills",
                    fakten.get("materials", "?"), fakten.get("skills", "?"))
    else:
        # Datierter Vermerk statt gar nichts: sonst liefe der Abruf auf einer
        # Seite ohne Bestand bei JEDEM Zug erneut.
        meta["context_facts"] = empty_marker()
        logger.info("Kein Bestand zu %s — Wiederholung frühestens in %.0fs",
                    collection_id, EMPTY_RETRY_SECONDS)


async def page_context_enrich(ctx: TurnContext) -> TurnContext:
    """Inject page-context IDs into entities and best-effort resolve page metadata."""
    page_ctx = ctx.env.get("page_context") or {}
    _normalize_strings(page_ctx)
    _decide_editorial_kind(page_ctx)
    _decide_host_kind(page_ctx)
    entities = ctx.session_state.setdefault("entities", {})
    for key in _PAGE_CONTEXT_ENTITY_KEYS:
        if page_ctx.get(key):
            entities[key] = page_ctx[key]

    try:
        await resolve_page_context(page_ctx, ctx.session_state)
    except Exception as err:  # pragma: no cover — resolver bug must not break the turn
        logger.warning("page_context auto-resolve skipped: %s", err)

    await _bestand_anhaengen(page_ctx, ctx.session_state)
    return ctx
