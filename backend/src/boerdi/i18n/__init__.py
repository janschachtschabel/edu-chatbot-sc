"""Backend-side i18n: which language a request wants, and what it changes.

Three things live here: the language resolution (C1-e), the messages an editor
reads in the studio (C1-e), and what a German prompt needs in order to make the
bot answer in another language (C1-f).

The FastAPI dependency that turns the header into a ``Locale`` lives in
``api/deps.py`` — dependency injection is the API layer's job, and this package
must not import from it.
"""

from boerdi.i18n.bot_text import BOT_TEXT, bot_text
from boerdi.i18n.locale import (
    DEFAULT,
    SUPPORTED,
    Locale,
    pick_localized,
    resolve_locale,
)
from boerdi.i18n.messages import MESSAGES, msg
from boerdi.i18n.output_patterns import (
    CLAIM_WORDS,
    COLLECTION_WORD,
    DELIVERY_VERBS,
    DETERMINER_PREFIX,
    TOPIC_PAGE_WORD,
)
from boerdi.i18n.prompt_language import language_name, template_hint

__all__ = [
    "BOT_TEXT", "CLAIM_WORDS", "COLLECTION_WORD", "DEFAULT", "DELIVERY_VERBS",
    "DETERMINER_PREFIX", "MESSAGES", "SUPPORTED", "TOPIC_PAGE_WORD", "Locale",
    "bot_text", "language_name", "msg", "pick_localized", "resolve_locale",
    "template_hint",
]
