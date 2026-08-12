"""Webseiten-Tour in der Sprache des Zuges (C1-g2d).

Die Tour-Config trägt ihre englischen Fassungen als Geschwister-Schlüssel
(``label`` neben ``label_en``, C1-g1a). Gewählt wird hier — EINMAL, an der
Knoten-Grenze — statt an den rund fünfzehn Lesestellen in ``domain/tour``:

* ``domain/tour`` ist ein 1:1-Port der ALT-Zustandsmaschine und bleibt dadurch
  unberührt; die Sprache ist eine neue Sorge und wohnt in einer neuen Datei.
* Der Prozess-Cache des Config-Loaders ist sprachunabhängig, ein Zug nicht —
  dieselbe Begründung wie bei ``_COMPILED`` im Lotsen (C1-g2a).

Was NICHT übersetzt wird, und warum:

* **Pfade, IDs, ``base_host``** — sie tragen den Ankunfts-Vergleich der
  Zustandsmaschine. Ein übersetzter Pfad wäre eine kaputte Tour.
* **``synonyms``** — die Freitext-Treffer der Gruppenwahl bleiben deutsch. Das
  ist Absicht und macht das Matching zur VEREINIGUNG: der englische Chip trifft
  über die (jetzt englische) Beschriftung, deutsch Getipptes weiterhin über die
  Synonyme. Dieselbe Entscheidung wie beim Sicherheits-Gate (C1-f2c-a): ein
  Erkenner darf die Sprache nicht kennen.
* **``trigger_phrases``** — aus demselben Grund eine Vereinigung, gepflegt im
  Seed statt hier im Code.
* **``flows``** — reine Studio-Dokumentation, erreicht nie einen Chat.
* **``start_label``** — hat weder in NEU noch in ALT einen Leser; die Tour
  startet über ``tour_reply`` aus der Begrüßungs-Config (C1-g1a/b).
"""

from __future__ import annotations

from typing import Any

from boerdi.i18n import DEFAULT, Locale, pick_localized

_SUFFIX = "_en"


def _localized(block: dict[str, Any], lang: Locale) -> dict[str, Any]:
    """Jeden Text eines flachen Blocks durch die gepflegte Fassung ersetzen.

    Ein Schlüssel ohne ``_en``-Partner bleibt unverändert — ``pick_localized``
    liest die fehlende Fassung als „nicht gepflegt" und gibt den deutschen Text
    zurück. Nicht-Texte (Pfade sind Texte, aber ohne Partner; Listen, Zahlen,
    Wahrheitswerte) fasst die Schleife gar nicht erst an.
    """
    out = dict(block)
    for key, value in block.items():
        if key.endswith(_SUFFIX) or not isinstance(value, str):
            continue
        out[key] = pick_localized(value, str(block.get(key + _SUFFIX) or ""), lang)
    return out


def _localized_list(items: Any, lang: Locale) -> Any:
    """Liste von ``{label, path}``-Einträgen (Sublinks, Kontakt, Angebote)."""
    if not isinstance(items, list):
        return items
    return [_localized(i, lang) if isinstance(i, dict) else i for i in items]


def _localized_group(group: dict[str, Any], lang: Locale) -> dict[str, Any]:
    out = _localized(group, lang)
    if "angebote" in group:
        out["angebote"] = _localized_list(group.get("angebote"), lang)
    return out


def localize(cfg: dict[str, Any], lang: Locale) -> dict[str, Any]:
    """Tour-Config für einen Zug in ``lang``.

    Deutsch gibt dieselbe Instanz zurück, nicht bloß denselben Inhalt: der
    Regelfall soll weder Bytes noch Kopien kosten. Für jede andere Sprache
    entsteht eine flache Kopie je Ebene — das Original bleibt unberührt, weil
    der Config-Cache es an jeden weiteren Zug ausliefert.
    """
    if lang == DEFAULT:
        return cfg

    out = _localized(cfg, lang)
    if isinstance(cfg.get("entry"), dict):
        out["entry"] = _localized(cfg["entry"], lang)
    if isinstance(cfg.get("steps"), dict):
        out["steps"] = {
            name: _localized(step, lang) if isinstance(step, dict) else step
            for name, step in cfg["steps"].items()
        }
    if isinstance(cfg.get("groups"), list):
        out["groups"] = [
            _localized_group(g, lang) if isinstance(g, dict) else g
            for g in cfg["groups"]
        ]
    for key in ("content_sublinks", "contact_links"):
        if key in cfg:
            out[key] = _localized_list(cfg[key], lang)
    return out
