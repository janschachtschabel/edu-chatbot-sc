"""Context-greeting node — proactive on-load greeting dispatcher (P4-2d, R6).

Port of ALT ``chat_context_greeting.py::maybe_context_greeting`` (Seitenkontext-
Feature, 2026-07-10). When the widget opens/continues on a recognised WLO page it
sends a turn with ``environment.page_event == 'context_open'``. This node builds a
short greeting + action pills from ``01-base/context-actions`` — LLM-free — and
sets ``ctx.early_response`` so the graph short-circuits (like tour/preflight).

Contract:
  * an unknown ``page_event`` → ``early_response`` stays None (normal flow).
  * ``page_event ∈ {'context_open', 'context_open_initial'}`` → ALWAYS an answer: a
    greeting when every gate passes, else ``content == ""`` (the frontend renders
    empty content as nothing).

Gates (all AND): non-empty history — but only for ``context_open``, see below;
page kind ∈ ``_GREETABLE_KINDS``; the greeting has a subject (``_greeting_fields``);
page not greeted before (signature ∉ ``_greeted_pages``); greetings switched on.

Two deliberate deviations from the ALT contract, both from the Seitenkontext-
Erweiterung (2026-08-11):

* **Three more page kinds** — ``search``, ``home``, ``external``. None of them is a
  WLO object, so the "resolved metadata" gate was generalised into
  ``_greeting_fields``: the subject is the search term resp. the hostname.
* **The first load greets too** (``context_open_initial``). ALT stayed silent on an
  empty history because the widget shows its own configured greeting there and two
  messages would appear. The widget now holds that greeting back until this ping
  answers, so exactly one message is rendered either way.

Why it runs BEFORE ``persist_user`` in the graph: a ``context_open`` ping is not a
user message. Short-circuiting here means the ping is never persisted or classified.
Because the terminal persist node does not run on an early exit, the greeting
persists its own assistant message + dedup marker inline (like the tour node).

DI (Regel 3): ``session`` is injected by the graph-build (P4-6). NEU deviations over
ALT, both from the SQLite→Postgres move: ``update_session``/``save_message`` take the
session first, and ``entities`` is written as a native jsonb dict (ALT wrapped it in
``json.dumps``) — identical to the tour node's ``tour_state`` handling. Tests patch
the two DB writes on THIS module; ``page_context`` + ``load_context_actions`` run for
real.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.domain.quick_reply_policy import CONTEXT_GREETING_MARKER
from boerdi.graph.state import TurnContext
from boerdi.i18n import DEFAULT, Locale, pick_localized, resolve_locale
from boerdi.i18n.bot_text import bot_text
from boerdi.services import page_context
from boerdi.services.config_loader import get_repo_base_url, load_context_actions
from boerdi.services.db_sessions import save_message, update_session
from boerdi.services.page_duplicate import find_existing_by_url

logger = logging.getLogger(__name__)

# Page kinds that ARE a WLO object: a node exists, so the greeting's subject is
# its resolved title.
_OBJECT_KINDS = ("collection", "content", "topic")
# Everything the node may greet. Must stay in step with the loader's
# ``_CONTEXT_ACTIONS_PAGE_KINDS`` — what the loader drops never reaches here.
_GREETABLE_KINDS = (*_OBJECT_KINDS, "search", "home", "external")
_GREETED_KEY = "_greeted_pages"
_GREETED_CAP = 20

# The widget names WHICH case it is. ``context_open`` continues a conversation;
# ``context_open_initial`` is the very first load, where an empty history is the
# normal state rather than the sign of a stray ping — so only the first of the
# two is subject to the history gate. Both are plain strings in a free-form
# contract field, so neither costs an OpenAPI change.
_EVENT_CONTINUE = "context_open"
_EVENT_INITIAL = "context_open_initial"
_CONTEXT_EVENTS = (_EVENT_CONTINUE, _EVENT_INITIAL)


def _empty_response(session_id: str) -> ChatResponse:
    """Empty context answer — the frontend renders empty content as nothing."""
    return ChatResponse(
        session_id=session_id,
        content="",
        follow_up="none",
        debug=DebugInfo(
            pattern=f"{CONTEXT_GREETING_MARKER}skipped",
            tools_called=["context_greeting"],
        ),
    )


def _greeting_fields(
    page_kind: str, page_ctx: dict[str, Any], session_state: dict[str, Any],
) -> dict[str, str] | None:
    """Placeholder values for the greeting text — ``None`` when there is nothing
    to say, which silences the greeting.

    This is the generalised form of the original "resolved metadata" gate. It
    only held for pages that ARE a WLO object; the three kinds added with the
    Seitenkontext-Erweiterung have no node to resolve, so their subject comes
    from the page context itself: the search term, resp. the hostname.

    Every kind also yields ``title`` — the pill labels and the action params
    substitute it, and they must not end up with an empty name.
    """
    if page_kind in _OBJECT_KINDS:
        meta = page_context.get_cached(session_state)
        if not isinstance(meta, dict):
            return None
        title = (meta.get("title") or "").strip()
        if not title or meta.get("unresolved"):
            return None
        return {"title": title}

    if page_kind == "search":
        # A search page without a term has no subject — an empty result list is
        # not something to announce.
        query = (page_ctx.get("search_query") or "").strip()
        return {"query": query, "title": query} if query else None

    host = (page_ctx.get("page_host") or "").strip()
    return {"host": host, "title": host} if host else None


#: Seitenarten, deren Gegenstand die ADRESSE ist und nicht der Host.
#:
#: Auf einer fremden Seite lautet das Angebot „ich kann DIESE Seite ansehen und
#: für den Bestand vorschlagen" — es gilt pro Adresse. ``home`` steht bewusst
#: nicht dabei: dort sagt die Meldung etwas über die Site, und sie auf jeder
#: Unterseite zu wiederholen wäre Lärm.
_ADRESS_KINDS = ("external",)


def _page_address(page_kind: str, page_ctx: dict[str, Any]) -> str:
    """Die Adresse als Teil des Dedup-Schlüssels — nur für fremde Seiten.

    Ohne Anker: ein Sprung in einen Abschnitt ist keine neue Seite, sonst
    begrüßte jeder Klick im Inhaltsverzeichnis erneut.

    Leer, wenn die Adresse fehlt (älteres Widget-Bündel schickt nur den Host).
    Dann gilt weiter das bisherige, hostweite Verhalten — ein leerer Zusatz
    ändert am Schlüssel nichts.
    """
    if page_kind not in _ADRESS_KINDS:
        return ""
    return (page_ctx.get("page_url") or "").strip().split("#", 1)[0]


def _greeting_signature(
    page_kind: str, page_ctx: dict[str, Any], fields: dict[str, str],
) -> str:
    """Dedup key for "this page has been greeted already".

    Deliberately NOT ``page_context._current_context_signature``, which answers a
    different question ("is the cached metadata still valid?") and reads node IDs
    and slugs only. Those are all empty for search/home/external, so every such
    page would share one key: greet one search, and no other search — nor any
    foreign page — would ever announce itself again in that session.

    Two pages are the same page here when they are the same kind ABOUT the same
    subject, so the subject (``fields``) joins the IDs in the key.

    **Die Adresse kommt für fremde Seiten dazu** (Befund der Plugin-Entwickler,
    2026-08-17). Dort sind alle vier ID-Felder leer und der Suchbegriff auch —
    übrig blieb der Hostname, und damit galten ALLE Seiten eines Hosts als
    dieselbe: der zweite Wikipedia-Artikel einer Sitzung bekam eine leere
    Antwort statt Begrüßung samt Knöpfen. Für WLO-Objekte bleibt die Kennung der
    Schlüssel — zwei Adressen auf dieselbe Sammlung sind dieselbe Seite, sonst
    begrüßte ein angehängter Zählparameter erneut (:func:`_page_address`).

    Der Schlüssel ändert sich damit für fremde Seiten. Laufende Sitzungen tragen
    noch die alten Einträge; die betroffene Seite meldet sich einmalig ein
    zweites Mal. Das ist der ganze Übergang.
    """
    return "|".join((
        page_kind,
        page_context._current_context_signature(page_ctx),
        fields.get("query", ""),
        fields.get("host", ""),
        _page_address(page_kind, page_ctx),
    ))


def _build_quick_replies(
    cfg: dict[str, Any],
    page_kind: str,
    page_ctx: dict[str, Any],
    meta: dict[str, Any],
    title: str,
    lang: Locale = DEFAULT,
) -> list[str]:
    """Serialise the configured pills for this page kind into quick-reply strings:
      * text   → the plain label (sent as a normal message on click)
      * action → ``__action__|<label>|<action>|<params-json>`` (Direct-Action)
      * report → ``__guide__|<label>|<url>`` (existing guide-link encoding)
    IDs are injected at runtime: collection/topic actions carry the collection_id;
    the report link carries the node_id (content) resp. collection_id (else).

    ``lang`` picks the maintained label (C1-g2b). It matters most for ``text``
    pills: their label IS the message the click sends, so a German label would
    put German text in an English user's mouth — and in front of the classifier.
    """
    collection_id = (page_ctx.get("collection_id") or "").strip() or (
        meta.get("node_id") or ""
    ).strip()
    node_id = (page_ctx.get("node_id") or "").strip() or (meta.get("node_id") or "").strip()
    report_id = node_id if page_kind == "content" else collection_id
    action_id = collection_id or node_id

    report_url = (
        str(cfg.get("report_url") or "")
        .replace("{node_id}", report_id)
        .replace("{collection_id}", collection_id)
    )

    out: list[str] = []
    for pill in cfg.get("pills", {}).get(page_kind, []):
        label = pick_localized(
            str(pill.get("label") or ""), str(pill.get("label_en") or ""), lang,
        ).replace("{title}", title)
        kind = pill.get("kind")
        if not label or not kind:
            continue
        if kind == "text":
            out.append(label)
        elif kind == "action":
            action = str(pill.get("action") or "").strip()
            if not action:
                continue
            # ``node_id`` seit P7 (2026-08-13): ``show_content_text`` liest genau
            # dieses Feld. Bis dahin ging nur ``collection_id`` mit — der
            # Volltext-Knopf einer Inhaltsseite wäre also stumm im Fehlerzweig
            # gelandet („Ich brauche die ID des Inhalts"). Die drei
            # Sammlungs-Aktionen ignorieren das zusätzliche Feld.
            params = {"collection_id": action_id, "node_id": node_id, "title": title}
            out.append(f"__action__|{label}|{action}|{json.dumps(params, ensure_ascii=False)}")
        elif kind == "report":
            if report_url:
                out.append(f"__guide__|{label}|{report_url}")
    return out


def _known_page_pills(
    cfg: dict[str, Any], known: dict[str, str], lang: Locale = DEFAULT,
) -> list[str]:
    """One chip: open the record we already have. Uses the existing
    ``__guide__|Label|URL`` encoding, so no frontend change is needed."""
    node_id = (known.get("node_id") or "").strip()
    label = pick_localized(
        str(cfg.get("duplicate_pill_label") or ""),
        str(cfg.get("duplicate_pill_label_en") or ""), lang,
    )
    if not node_id or not label:
        return []
    url = f"{get_repo_base_url()}/edu-sharing/components/render/{node_id}"
    return [f"__guide__|{label}|{url}"]


async def _known_page(page_kind: str, page_ctx: dict[str, Any]) -> dict[str, str] | None:
    """The WLO record for this foreign page, if the holdings already hold one.

    M20 makes this check a precondition of every new record ("Vor JEDER
    Neuanlage"), because a second record for the same address is the most
    frequent avoidable pollution of the holdings. Running it HERE means the
    offer to add the page never appears when the page is already in — rather
    than relying on the model to follow M20 once the person has clicked.

    ``None`` covers two cases on purpose: nothing found, and could not ask. The
    greeting they share claims nothing about duplicates ("I can look at the page
    and suggest it"), so both are the same honest statement — a separate error
    text would be a distinction without a difference.
    """
    if page_kind != "external":
        return None
    url = (page_ctx.get("page_url") or "").strip()
    if not url:
        # Only the hostname available (older widget bundle): a check on the bare
        # host would answer about a different page than the one in front of us.
        return None
    try:
        return await find_existing_by_url(url, (page_ctx.get("document_title") or "").strip())
    except Exception as err:  # find_existing_by_url is best-effort by contract
        logger.warning("duplicate check skipped: %s", err)
        return None


#: Welcher Satz zu welcher Ausbeute passt — Schlüssel ist ``(Materialien?,
#: Skills?)``. Fehlen beide, gibt es keinen Eintrag und damit keinen Satz.
_STOCK_KEYS = {
    (True, True): "context.stock.both",
    (True, False): "context.stock.materials",
    (False, True): "context.stock.skills",
}


def _stock_sentence(meta: dict[str, Any], lang: Locale) -> str:
    """Die Kontext-Bestätigung in Zahlen — oder "" (Nutzer-Vorgabe 2026-08-14).

    „Ich sehe 35 Materialien und 28 freigegebene Anleitungen dazu." macht
    sichtbar, dass der Kontext WIRKLICH angekommen ist, statt es zu behaupten.
    Der Satz kommt mit führendem Abstand, damit er im Vorlagentext direkt hinter
    dem Punkt stehen kann (``…„{title}".{bestand} Womit…``) und bei Ausfall
    keine doppelte Lücke hinterlässt.

    **Liest nur, ruft nicht ab.** Die Zahlen stehen am Metadaten-Cache, den
    ``page_context_enrich`` einen Knoten vorher füllt.

    Das macht den Zug NICHT schneller — der Abruf liegt weiterhin davor, nur in
    einem anderen Knoten. Es macht ihn EINMALIG: dieselben Zahlen tragen jetzt
    auch den Seitenblock beider Engines. Vorher zahlte die Begrüßung 4–7 s
    (kalt) für eine Angabe, die sonst niemand zu sehen bekam; warm kostet der
    Abruf 0.00 s, und der Cache hält 30 Minuten.

    Ohne Fakten "": auf einer Inhaltsseite gibt es keinen Bestand, und ein
    ausgefallener Abruf soll sich nicht zeigen.
    """
    fakten = meta.get("context_facts")
    if not isinstance(fakten, dict):
        return ""
    schluessel = _STOCK_KEYS.get(("materials" in fakten, "skills" in fakten))
    if not schluessel:
        return ""
    return " " + bot_text(
        lang, schluessel,
        materials=fakten.get("materials", ""), skills=fakten.get("skills", ""),
    )


async def maybe_context_greeting(
    session: AsyncSession,
    req: ChatRequest,
    env: dict[str, Any],
    session_state: dict[str, Any],
    history: list[Any],
) -> ChatResponse | None:
    """See the module docstring. Returns ``None`` only without a ``context_open``
    signal; otherwise always a ChatResponse (greeting or empty)."""
    event = (env.get("page_event") or "").strip().lower()
    if event not in _CONTEXT_EVENTS:
        return None  # no context signal → normal flow

    # From here on: always return a ChatResponse (never None).
    page_ctx = env.get("page_context") or {}
    page_kind = (page_ctx.get("page_kind") or "").strip().lower()

    # Gate 1: on a CONTINUED conversation only (session existence is not enough
    # — IDs are created eagerly; the discriminator is a non-empty history). The
    # first load says so with its own event and is exempt: there the widget
    # holds its own greeting back and renders this one instead, so the person
    # still sees exactly one message.
    if event == _EVENT_CONTINUE and not history:
        return _empty_response(req.session_id)

    # Gate 2: greetable page kind.
    if page_kind not in _GREETABLE_KINDS:
        return _empty_response(req.session_id)

    # Gate 3: the greeting has a subject — a resolved title for a WLO object,
    # else the search term resp. the hostname.
    fields = _greeting_fields(page_kind, page_ctx, session_state)
    if fields is None:
        return _empty_response(req.session_id)
    title = fields["title"]
    meta = page_context.get_cached(session_state) or {}

    # Gate 4: page not greeted before (dedup over the greeting signature).
    signature = _greeting_signature(page_kind, page_ctx, fields)
    entities = session_state.setdefault("entities", {})
    greeted = entities.get(_GREETED_KEY)
    if not isinstance(greeted, list):
        greeted = []
    if signature in greeted:
        return _empty_response(req.session_id)

    cfg = load_context_actions()
    if not cfg.get("enabled", True):
        return _empty_response(req.session_id)

    lang = resolve_locale(env.get("locale"))
    fields = {**fields, "bestand": _stock_sentence(meta, lang)}
    known = await _known_page(page_kind, page_ctx)
    if known:
        # The page is already a WLO record — say which one and point at it,
        # instead of offering to add it a second time.
        fields = {**fields, "title": known.get("title") or title}
        raw_greeting = pick_localized(
            str(cfg.get("duplicate_greeting") or ""),
            str(cfg.get("duplicate_greeting_en") or ""), lang,
        )
        marker = f"{page_kind}:bekannt"
    else:
        raw_greeting = pick_localized(
            str(cfg.get("greetings", {}).get(page_kind) or ""),
            str(cfg.get("greetings_en", {}).get(page_kind) or ""), lang,
        )
        marker = page_kind

    greeting = raw_greeting
    for name, value in fields.items():
        greeting = greeting.replace("{" + name + "}", value)
    if not greeting.strip():
        return _empty_response(req.session_id)

    if known:
        quick_replies = _known_page_pills(cfg, known, lang)
    else:
        quick_replies = _build_quick_replies(cfg, page_kind, page_ctx, meta, title, lang)

    # Record the dedup marker (FIFO cap — a list, because entities is jsonb-
    # persisted) and persist it explicitly on the short-circuit path.
    greeted.append(signature)
    if len(greeted) > _GREETED_CAP:
        greeted = greeted[-_GREETED_CAP:]
    entities[_GREETED_KEY] = greeted

    try:
        await update_session(session, req.session_id, entities=entities)
        await save_message(
            session, req.session_id, "assistant", greeting,
            debug={"pattern": f"{CONTEXT_GREETING_MARKER}{marker}"},
        )
    except Exception as exc:  # pragma: no cover — persistence must not break the turn
        logger.warning("context greeting persist failed: %s", exc)

    logger.info("context_greeting fired page_kind=%s sig=%s", page_kind, signature)
    return ChatResponse(
        session_id=req.session_id,
        content=greeting,
        quick_replies=quick_replies,
        follow_up="none",
        debug=DebugInfo(
            pattern=f"{CONTEXT_GREETING_MARKER}{marker}",
            tools_called=["context_greeting"],
        ),
    )


async def context_greeting(ctx: TurnContext, session: AsyncSession) -> TurnContext:
    """Node adapter: dispatch the greeting, short-circuit the turn on a hit.

    Sets ``ctx.early_response`` when ``maybe_context_greeting`` returns a response
    (greeting or empty) so a ``context_open`` ping never reaches persist/assess.
    Wrapped defensively (ALT wrapped the call-site the same way): a greeting bug
    must never break the turn — on error the turn falls through to the normal flow.
    """
    try:
        resp = await maybe_context_greeting(
            session, ctx.req, ctx.env, ctx.session_state, ctx.history
        )
    except Exception as err:
        logger.warning("context greeting skipped: %s", err)
        resp = None
    if resp is not None:
        ctx.early_response = resp
    return ctx
