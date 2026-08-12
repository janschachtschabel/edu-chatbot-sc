"""Which language a request wants (C1-e).

``Accept-Language`` and not a body field: the messages this decides are error
details from a dozen endpoints, and a header costs no change to the frozen
OpenAPI contract. The chat turn carries its language explicitly (C1-f) because
there the language is part of the conversation, not of the transport.

Two languages, same set as the interfaces: German is the default, English the
alternative. An unsupported language falls through to German rather than
failing the request — a wrong language is a nuisance, a rejected request is an
outage.
"""

from typing import Final, Literal, get_args

Locale = Literal["de", "en"]

SUPPORTED: Final[tuple[str, ...]] = get_args(Locale)
DEFAULT: Final[Locale] = "de"


def resolve_locale(accept_language: str | None) -> Locale:
    """The best supported language in an ``Accept-Language`` header.

    Follows RFC 9110 §12.5.4 in the parts that matter here: entries are
    comma-separated, an optional ``;q=`` weights them, ``q=0`` means "not
    acceptable", and a tag matches on its primary subtag (``en-GB`` is
    English). The weight decides, not the order in which the browser wrote it.

    Malformed entries are skipped rather than guessed at: a header we cannot
    read is not a language preference.
    """
    if not accept_language:
        return DEFAULT

    best: tuple[float, Locale] | None = None
    for raw in accept_language.split(","):
        parts = [p.strip() for p in raw.split(";")]
        tag = parts[0].lower()
        if not tag:
            continue
        primary = tag.split("-")[0]
        if primary not in SUPPORTED:
            continue

        quality = 1.0
        for param in parts[1:]:
            if not param.lower().startswith("q="):
                continue
            try:
                quality = float(param[2:])
            except ValueError:
                quality = -1.0  # unlesbar → dieser Eintrag zählt nicht
        if quality <= 0:
            continue

        if best is None or quality > best[0]:
            best = (quality, primary)  # type: ignore[assignment]

    return best[1] if best else DEFAULT


def pick_localized(de: str, en: str, lang: Locale) -> str:
    """The maintained version of a config value, in ``lang``.

    The studio config carries both versions per key (C1-g1a: ``label`` next to
    ``label_en``). The server does not resolve them at load time — the process
    cache is language-agnostic, while a turn is not — so whoever *uses* a value
    picks it, and this is the one rule they all share.

    An empty English field means "not maintained", never "empty text": showing
    an unlabelled button to an English reader is worse than showing a German
    one. Same rule as ``pickLocalized`` in the widget, for the same reason.
    """
    if lang != "en":
        return de
    return en if en.strip() else de
