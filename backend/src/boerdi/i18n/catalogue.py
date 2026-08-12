"""How a catalogue entry becomes a sentence (C1-f2b).

Extracted from ``messages.py`` when the second catalogue arrived: the studio's
API messages and the bot's own sentences have different audiences and different
language sources, but the lookup and the substitution are the same problem, and
two copies of it would be two places to fix a formatting bug.

Nothing here decides WHICH catalogue — that is the caller's business.
"""

from typing import Final

from boerdi.i18n.locale import DEFAULT, Locale

Catalogue = dict[Locale, dict[str, str]]


class _Keep(dict[str, object]):
    """Leaves a placeholder standing instead of raising for a missing value."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(catalogue: Catalogue, locale: Locale, key: str, **params: object) -> str:
    """The entry for ``key`` in ``locale``, with ``params`` substituted.

    An unknown key returns the key itself, and a forgotten parameter leaves its
    placeholder standing. Both are programming errors — but a raise here would
    turn a message into a crash, and a message is the one thing that must still
    arrive when something has already gone wrong. The guards in
    ``tests/test_i18n_messages.py`` and ``tests/test_i18n_bot_text.py`` catch
    them before they ship.
    """
    template = catalogue.get(locale, catalogue[DEFAULT]).get(key)
    if template is None:
        return key
    return template.format_map(_Keep(params))


__all__: Final = ["Catalogue", "render"]
