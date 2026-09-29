"""ST-2f: wer Fließtext trägt, sagt es im Modell — ``Textarea()``.

Bis ST-2f entschied eine Namensliste im Studio (``MULTILINE_KEYS``), welches
Feld eine Textfläche bekommt; gepflegt per Hand-Messung über den Seed-Baum, und
wo die Messung fehlte, plättete ein einzeiliges Feld mehrzeilige Kernregeln
(SF-2). Dieser Wächter IST die Messung: jeder String im ausgelieferten Seed mit
mehr als 120 Zeichen oder Zeilenumbruch — und jede so lange Vorgabe im Modell —
steht in einem Feld mit ``x-widget: textarea``.
"""

from pathlib import Path
from typing import Any

import yaml

from boerdi.domain.config_models import AREA_MODELS, model_for

SEEDS = Path(__file__).resolve().parents[1] / "seeds"
LANG = 120


def _fliesstext(wert: object) -> bool:
    return isinstance(wert, str) and (len(wert) > LANG or "\n" in wert.strip())


def _deref(node: dict, root: dict) -> dict:
    for _ in range(10):
        ref = node.get("$ref")
        if not ref:
            return node
        cur: Any = root
        for seg in ref.split("#/")[1].split("/"):
            cur = cur[seg]
        node = cur
    return node


def _nicht_null(node: dict, root: dict) -> dict:
    node = _deref(node, root)
    zweige = [o for o in node.get("anyOf", []) if o.get("type") != "null"]
    return _deref(zweige[0], root) if len(zweige) == 1 else node


def _textflaeche(prop: dict, root: dict) -> bool:
    """Der Hinweis steht an der Eigenschaft oder (bei ``| None``) im Zweig."""
    zweig = _nicht_null(prop, root)
    return "textarea" in (prop.get("x-widget"), zweig.get("x-widget"))


def _fehlende(wert: Any, prop: dict, root: dict, pfad: str, out: set[str]) -> None:
    """Geht Dokument und Schema gemeinsam ab; merkt Fließtext ohne Hinweis."""
    node = _nicht_null(prop, root)
    if isinstance(wert, str):
        if _fliesstext(wert) and not _textflaeche(prop, root):
            out.add(pfad)
    elif isinstance(wert, dict):
        props = node.get("properties") or {}
        extra = node.get("additionalProperties")
        for k, v in wert.items():
            if k in props:
                _fehlende(v, props[k], root, f"{pfad}.{k}" if pfad else k, out)
            elif isinstance(extra, dict):
                _fehlende(v, extra, root, f"{pfad}.*" if pfad else "*", out)
    elif isinstance(wert, list) and isinstance(node.get("items"), dict):
        for v in wert:
            _fehlende(v, node["items"], root, f"{pfad}[]", out)


def _dokumente():
    for datei in sorted(SEEDS.rglob("*")):
        if datei.suffix not in (".yaml", ".md") or datei.parent == SEEDS:
            continue
        schluessel = f"{datei.parent.name}/{datei.stem}"
        modell = model_for(schluessel)
        if modell is None:
            continue
        text = datei.read_text(encoding="utf-8")
        if datei.suffix == ".md":
            _, kopf, rumpf = text.split("---", 2)
            yield schluessel, modell, {"frontmatter": yaml.safe_load(kopf) or {}, "body": rumpf}
        else:
            yield schluessel, modell, yaml.safe_load(text) or {}


def test_jeder_fliesstext_im_seed_hat_eine_textflaeche() -> None:
    fehlend: set[str] = set()
    for schluessel, modell, doc in _dokumente():
        schema = modell.model_json_schema()
        pfade: set[str] = set()
        _fehlende(doc, schema, schema, "", pfade)
        fehlend |= {f"{modell.__name__}: {p}  ({schluessel})" for p in pfade}
    assert sorted(fehlend) == []


def test_jede_lange_vorgabe_im_modell_hat_eine_textflaeche() -> None:
    """Die Rolle des Agenten und der Krisentext stehen lang im MODELL, nicht im
    Seed — die Seed-Messung sähe sie nicht."""
    fehlend: set[str] = set()
    for modell in set(AREA_MODELS.values()):
        schema = modell.model_json_schema()
        objekte = [schema, *(schema.get("$defs") or {}).values()]
        for objekt in objekte:
            for key, prop in (objekt.get("properties") or {}).items():
                if _fliesstext(prop.get("default")) and not _textflaeche(prop, schema):
                    fehlend.add(f"{objekt.get('title')}.{key}")
    assert sorted(fehlend) == []
