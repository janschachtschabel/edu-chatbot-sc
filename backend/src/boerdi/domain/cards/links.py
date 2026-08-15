"""Card link resolution (P5-4c) — byte-parity port of the link-building half of
ALT ``card_pipeline.py``.

Third sub-module of the ``domain/cards`` package: the single source of truth for a
card's final URL (``build_card_link`` — topic_page/collection/content lookup table +
guide-mode routing), plus allow-list validation (``validate_card_link``) and the
in-place ``link``-field annotator (``annotate_cards_with_link``).

Pure domain logic. Deps: the config read-fassade ``get_repo_base_url``, the repo-URL
builders + ``_infer_node_type`` from the sibling ``normalize`` module, and the guide-
mode allow-list (``host_matches_pattern`` top-level, ``host_is_allowed`` imported
lazily inside ``validate_card_link`` — verbatim ALT, keeps the body byte-identical).

Deviations from ALT: import roots (``app.`` → ``boerdi.``); the two
``setattr(obj, "<const>", …)`` calls keep a ``# noqa: B010`` (verbatim; rewriting to
attribute assignment would diverge the AST).

Ab 15.08.2026 nicht mehr byte-identisch — drei Stellen tragen den Sammlungs-
Zweitlink (``collection_link``): die node_type-Auflösung steht als
``_resolve_node_type`` heraus (``build_card_link`` ruft sie statt sie inline zu
führen), ``_set_link_field`` nimmt den Feldnamen als Parameter, und
``annotate_cards_with_link`` schreibt das zweite Feld. Alle drei sind durch
``tests/test_cards_links.py`` gepinnt.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from boerdi.domain.cards.normalize import (
    _infer_node_type,
    _repo_collection_browse_url,
    _repo_render_url,
    _repo_topic_page_url,
)
from boerdi.domain.guide_mode import host_matches_pattern
from boerdi.services.config_loader import get_repo_base_url

logger = logging.getLogger(__name__)


def _card_as_dict(card: Any) -> dict[str, Any] | None:
    """Zieht ein Card-Dict aus dict | Pydantic-Model | beliebigem Objekt.

    Returns None wenn nichts greifbares dabei ist — Caller können dann
    defensiv aufhören.
    """
    if isinstance(card, dict):
        return card
    if card is None:
        return None
    # Pydantic V2: model_dump()
    md = getattr(card, "model_dump", None)
    if callable(md):
        try:
            return md()
        except Exception:
            pass
    # Pydantic V1: dict()-Methode oder __dict__-Attribut
    d = getattr(card, "dict", None)
    if callable(d):
        try:
            return d()
        except Exception:
            pass
    # Letzter Versuch: __dict__ (für normale Klassen)
    raw = getattr(card, "__dict__", None)
    if isinstance(raw, dict):
        return dict(raw)
    return None


def _resolve_node_type(card: dict[str, Any]) -> str:
    """node_type der Card — vertraut dem von ``normalize_cards`` gesetzten
    Wert, fällt auf Inferenz zurück wenn die Card aus einem alten Pfad kommt.

    Eigene Funktion, seit auch der Sammlungs-Zweitlink (``collection_link``)
    dieselbe Einordnung braucht: zwei Abschriften derselben drei Zeilen wären
    zwei Wege, an denen eine Karte anders klassifiziert werden kann.
    """
    nt = card.get("node_type")
    if nt not in ("topic_page", "collection", "content"):
        return _infer_node_type(card)
    return str(nt)


def build_card_link(
    card: Any,
    *,
    guide_mode: bool = False,
    repo_base: str | None = None,
    search_query: str = "",
) -> str:
    """Single Source of Truth für die Card-URL.

    Liest aus der Card den ``node_type`` (vorher von :func:`normalize_cards`
    gesetzt) und liefert nach Lookup-Tabelle den Link. Es gibt kein Fallback
    auf "irgendein URL-Feld" mehr — wenn ein Feld fehlt, das die Tabelle
    erwartet, fallen wir auf den Repo-Link zurück (immer noch besser als
    eine leere Card).

    Args:
        card: Card-Dict ODER Pydantic-Model (z.B. ``WloCard``), idealerweise
            schon durch :func:`normalize_cards` gegangen.
        guide_mode: True wenn der User im Lotsen-Modus ist (Repo-Links für
            Einzelinhalte; Themenseiten → topic-pages-Renderer, Sammlungen → Browse-Link).
        repo_base: Override für die Repo-Base-URL. Default:
            ``get_repo_base_url()``.
        search_query: Optional. Wird an Sammlungs-Browse-URLs als ``&q=``
            angehängt für besseren Browse-Kontext.

    Returns:
        Vollständige URL (https://…). Leerer String nur, wenn die Card
        weder ``node_id`` noch ``url`` hat (sollte praktisch nie passieren —
        ein normalisierter Pool enthält keine solche Cards).
    """
    card = _card_as_dict(card)
    if not isinstance(card, dict):
        return ""
    repo = (repo_base or get_repo_base_url()).rstrip("/")
    node_id = str(card.get("node_id") or "").strip()
    nt = _resolve_node_type(card)

    # ── Themenseiten ───────────────────────────────────────────────────
    if nt == "topic_page":
        tp_url = str(card.get("topic_page_url") or "").strip()
        if tp_url:
            return tp_url
        # Fallback: die Card hat zwar node_type=topic_page (also topic_pages
        # befüllt), aber kein topic_page_url-Feld. Nimm die erste Variante.
        for tp in card.get("topic_pages") or []:
            if isinstance(tp, dict):
                u = str(tp.get("url") or "").strip()
                if u:
                    return u
        # Letzter Fallback: Themenseiten-Renderer aus der node_id bauen —
        # NICHT der Sammlungs-Browse-Link. Eine Themenseite (ccm:map mit
        # page_config_ref) soll immer als topic-page geöffnet werden, auch
        # wenn weder topic_page_url noch eine Variante eine URL mitliefert.
        if node_id:
            return _repo_topic_page_url(node_id, repo)
        return ""

    # ── Sammlungen ─────────────────────────────────────────────────────
    if nt == "collection":
        if node_id:
            return _repo_collection_browse_url(node_id, repo, search_query)
        # Keine node_id → defensiv: nimm ein vorhandenes URL-Feld.
        for f in ("wlo_url", "url", "content_url", "preview_url"):
            v = str(card.get(f) or "").strip()
            if v:
                return v
        return ""

    # ── Einzelinhalte ──────────────────────────────────────────────────
    # Normal-Modus: bevorzugt den externen Link (card.url, falls extern).
    # Lotsen-Modus: zwingt zum Repo-Render-Link (User bleibt im WLO-Tab).
    if guide_mode:
        if node_id:
            return _repo_render_url(node_id, repo)
        # Fallback: irgendein Repo-URL-Feld
        for f in ("wlo_url", "content_url", "preview_url"):
            v = str(card.get(f) or "").strip()
            if v:
                return v
        return ""

    # Normal-Modus content: externes URL bevorzugt
    ext = str(card.get("url") or "").strip()
    if ext:
        # Ist es bereits ein Repo-Render-Link? Dann ist das technisch in
        # Ordnung, aber wenn ein externer Provider-Link existiert, hätten
        # wir den genommen. card['url'] kommt vom MCP normalerweise als
        # externer Link (ccm:wwwurl) für Content-Nodes, also nehmen wir
        # ihn direkt.
        return ext
    # Kein externer Link → Repo-Render als sinnvoller Default
    if node_id:
        return _repo_render_url(node_id, repo)
    return ""


def _host_of(url: str) -> str:
    """Lowercased hostname ohne Port + ohne ``www.``-Präfix, oder Empty
    bei Parse-Fehler."""
    if not isinstance(url, str) or not url:
        return ""
    try:
        h = (urlparse(url.strip()).hostname or "").strip().lower()
    except Exception:
        return ""
    if ":" in h:
        h = h.split(":", 1)[0]
    if h.startswith("www."):
        h = h[4:]
    return h


def validate_card_link(
    link: str,
    *,
    allowed_hosts: list[str] | None = None,
) -> bool:
    """True, wenn ``link`` eine wohlgeformte http(s)-URL ist und ihr Host
    in der Allow-Liste steht.

    Wenn ``allowed_hosts`` nicht übergeben wird, ziehen wir die Liste aus
    der bestehenden ``guide-mode.yaml`` (über
    :func:`guide_mode_service.host_is_allowed`) — so bleibt Phase 3b
    rückwärts-kompatibel mit der heutigen Allow-Liste, ohne sie zu
    duplizieren. Eine eigene Allow-Liste in ``card-pipeline.yaml`` können
    wir später ergänzen, sobald wir sie wirklich brauchen.
    """
    if not isinstance(link, str) or not link:
        return False
    try:
        parsed = urlparse(link.strip())
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = _host_of(link)
    if not host:
        return False
    if allowed_hosts is None:
        # Fallback auf die guide-mode.yaml-Allow-Liste — wird auch im
        # Lotsen-Modus für die Frontend-Auswahl genutzt.
        from boerdi.domain.guide_mode import host_is_allowed
        return host_is_allowed(host)
    for pattern in allowed_hosts:
        if host_matches_pattern(host, pattern):
            return True
    return False


def _set_link_field(card: Any, link: str, *, field: str = "link") -> None:
    """Setzt ein Link-Feld auf einer Card — egal ob Dict oder Pydantic-Model.

    Bei Pydantic-Models nutzen wir ``setattr``; das funktioniert nur, wenn
    das Feld im Schema definiert ist (für ``WloCard`` ist das der Fall seit
    Phase 4a). Wenn nicht, fangen wir die Exception und loggen — dann ist
    ``card.<field>`` weiterhin der Default-Wert aus dem Schema.

    ``field`` ist seit dem Sammlungs-Zweitlink parametrierbar (Default
    unverändert ``link``); der Body ist bis auf den Feldnamen ALT.
    """
    if isinstance(card, dict):
        card[field] = link
        return
    try:
        setattr(card, field, link)  # noqa: B010 — verbatim ALT; Pydantic-Model-Pfad
    except (AttributeError, ValueError) as e:
        logger.debug(
            "annotate_cards_with_link: setattr(%s) failed for %s: %s",
            field, type(card).__name__, e,
        )


def _build_collection_link(card: dict[str, Any], repo: str, search_query: str) -> str:
    """Sammlungs-Adresse für Karten, deren ``link`` woanders hinzeigt.

    Nimmt das bereits gelesene Karten-Dict (siehe ``annotate_cards_with_link``),
    nicht die Karte in ihrer Originalform — der einzige Aufrufer hat es ohnehin.

    Eine Sammlung mit kuratierter Themenseite wird zu ``node_type
    "topic_page"``; ``build_card_link`` gibt ihr die Themenseiten-Adresse.
    Der Sammlungen-Kasten braucht daneben das Browse-Ziel, sonst bleibt die
    Sammlung unerreichbar (Live-Befund „Optik", 15.08.2026).

    Leer für alle anderen Karten, und zwar absichtlich: bei reinen Sammlungen
    ist ``link`` bereits der Browse-Link, bei Einzelinhalten gibt es keine
    Sammlung — und in der ZWEITEN Themenseiten-Darstellung
    (``node_type="collection"`` MIT ``topic_pages``, wie sie ``_build_cards``
    beim Zusammenführen zweier Treffer derselben node_id erzeugt) liefert der
    Sammlungs-Zweig oben ohnehin den Browse-Link. Das Frontend fällt dort auf
    ``link`` zurück; siehe ``getCardCollectionUrl``.
    """
    if _resolve_node_type(card) != "topic_page":
        return ""
    node_id = str(card.get("node_id") or "").strip()
    if not node_id:
        return ""
    return _repo_collection_browse_url(node_id, repo, search_query)


def _get_node_id(card: Any) -> str:
    """Hole ``node_id`` aus dict oder Pydantic-Model."""
    if isinstance(card, dict):
        return str(card.get("node_id") or "").strip()
    return str(getattr(card, "node_id", "") or "").strip()


def annotate_cards_with_link(
    cards: list[Any],
    *,
    guide_mode: bool = False,
    repo_base: str | None = None,
    search_query: str = "",
    require_allowed: bool = False,
    allowed_hosts: list[str] | None = None,
) -> list[Any]:
    """Schreibt für jede Card das ``link``-Feld via :func:`build_card_link`.

    Robust gegen beide Card-Typen — Dict und Pydantic-Model. Der Caller
    bekommt die gleiche Liste zurück, jede Card hat jetzt das ``link``-Feld.

    Wenn ``require_allowed=True`` und der gebaute Link nicht durch
    :func:`validate_card_link` kommt, wird auf den Repo-Render-Link
    zurückgefallen (immer noch ein gültiges Ziel, weil unser eigener Host).

    Args:
        cards: Liste von Card-Dicts oder Pydantic-Models (Mischbar).
        guide_mode: An build_card_link weitergereicht.
        repo_base: Override für Repo-URL.
        search_query: Wird an Sammlungs-Browse-Links angehängt.
        require_allowed: Wenn True, wird Validation gegen die Allow-Liste
            gemacht; Cards mit nicht-allow-listed Link bekommen den
            Repo-Render-Fallback.
        allowed_hosts: Optional. Wenn None und require_allowed=True,
            wird die Liste aus guide-mode.yaml gezogen.

    Returns:
        Die gleiche Liste, jede Card hat jetzt das ``link``-Feld gesetzt.
    """
    repo = (repo_base or get_repo_base_url()).rstrip("/")
    for c in cards or []:
        # EINMAL in ein Dict lesen und an beide Link-Bauer geben. Beide würden
        # sonst je ``_card_as_dict`` rufen, und das ist bei Pydantic-Karten ein
        # ``model_dump()`` — bei Dicts reicht es die Karte selbst durch, der
        # Pfad bleibt also für beide Kartenformen derselbe wie vorher.
        # Geschrieben wird weiterhin auf ``c``, nicht auf die Kopie.
        daten = _card_as_dict(c) or {}
        link = build_card_link(
            daten, guide_mode=guide_mode, repo_base=repo, search_query=search_query,
        )
        if require_allowed and link and not validate_card_link(
            link, allowed_hosts=allowed_hosts,
        ):
            nid = _get_node_id(c)
            if nid:
                fallback = _repo_render_url(nid, repo)
                logger.debug(
                    "annotate_cards_with_link: link %r not allow-listed -> "
                    "fallback to repo-render %r",
                    link, fallback,
                )
                link = fallback
            else:
                logger.debug(
                    "annotate_cards_with_link: link %r not allow-listed and "
                    "card has no node_id - leaving link empty.",
                    link,
                )
                link = ""
        _set_link_field(c, link)
        # Zweitziel für Sammlungen MIT Themenseite: dieselbe Karte steht in
        # zwei Kästen, und der Sammlungen-Kasten braucht die Sammlung statt
        # der Themenseite. Zeigt per Konstruktion aufs eigene Repo — deshalb
        # weder Allow-Listen-Prüfung noch Lotsen-Korrektur nötig.
        _set_link_field(
            c,
            _build_collection_link(daten, repo, search_query),
            field="collection_link",
        )
        # Welle C Sprint 6 Hotfix — Lotsen-URL-Konsistenz auf card.url.
        #
        # User-Bug-Report: Im Event-Inspector und in einigen Frontend-Pfaden
        # (z.B. canvas.component.html: ``c.url || c.wlo_url``,
        # card-utils.getCardPrimaryUrl-Fallback) wird ``card.url`` ausgelesen
        # — und das ist im Lotsen-Modus die externe Provider-URL (youtube.com
        # etc.). Das untergräbt die "in derselben Tab bleiben"-Garantie des
        # Lotsen-Modus.
        #
        # Fix: Im Lotsen-Modus auch ``card.url`` mit dem (gerade berechneten)
        # Repo-Link überschreiben, sobald wir einen Repo-Link haben. So zeigen
        # ALLE Frontend-URL-Pfade (link / url / wlo_url / guide_url) im
        # Lotsen-Modus aufs Repo. Im Normal-Modus bleibt ``card.url``
        # unverändert — dort soll der User absichtlich extern springen.
        if guide_mode and link:
            try:
                if isinstance(c, dict):
                    if c.get("url") and c["url"] != link:
                        c["url"] = link
                else:
                    if getattr(c, "url", "") and getattr(c, "url", "") != link:
                        setattr(c, "url", link)  # noqa: B010 — verbatim ALT; Lotsen-URL-Override
            except (AttributeError, ValueError):
                pass  # Defensiv — niemals den Annotations-Lauf wegen url-Override brechen
    return cards
