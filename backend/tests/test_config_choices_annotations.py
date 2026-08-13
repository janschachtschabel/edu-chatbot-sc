"""S2: die Auszeichnung der Felder, die eine Auswahl statt Freitext verdienen.

Zwei Arten, bewusst getrennt (siehe ``config_models/_shared.py``):

* ``x-choices`` — geschlossener Wertevorrat, im Schema selbst aufgezählt.
* ``x-catalog`` — Name eines Katalogs aus dem laufenden Betrieb, den
  ``GET /api/config/choices`` füllt.

Die Auszeichnung ändert **keinen Typ**. Ein ``Literal`` würde jeden
Bestandswert außerhalb der Liste ab sofort mit 422 abweisen und könnte einen
Bereich unspeicherbar machen — das ist eine Bedienhilfe, keine Verschärfung.
Damit sie trotzdem nicht lügt, prüft ``test_keine_auswahlliste_luegt…`` jede
Liste gegen den ganzen ausgelieferten Seed-Baum.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from boerdi.api.config_choices import CATALOG_NAMES
from boerdi.domain.config_models import AREA_MODELS, model_for
from boerdi.domain.config_models.base_governance import SafetyConfigArea
from boerdi.domain.config_models.patterns import PatternArea

_SEEDS = Path(__file__).resolve().parents[1] / "seeds"


# ── die beiden Arten stehen im ausgelieferten Schema ───────────────────────

def test_geschlossene_auswahl_steht_im_schema() -> None:
    schema = SafetyConfigArea.model_json_schema()
    block = schema["$defs"]["EscalationBlock"]
    assert block["properties"]["mode"]["x-choices"] == ["off", "smart", "always"]
    assert block["properties"]["provider"]["x-choices"] == ["openai", "none"]


def test_verweis_steht_am_listeneintrag_nicht_an_der_liste() -> None:
    """Gewählt wird ein Eintrag, nicht die Liste — das Studio bindet die
    Vorschläge deshalb an die Zeile, in die getippt wird."""
    props = PatternArea.model_json_schema()["$defs"]["PatternFrontmatter"]["properties"]
    array = next(v for v in props["rag_areas"]["anyOf"] if v.get("type") == "array")
    assert array["items"]["x-catalog"] == "rag_areas"
    assert "x-catalog" not in props["rag_areas"]


def test_annotation_ist_keine_neue_speichersperre() -> None:
    """Ein Bestandswert außerhalb der Liste bleibt speicherbar.

    Genau hier hätte ein ``Literal`` zugeschlagen: ein einziger Altwert in
    einem Bereich, und das Studio könnte ihn nicht mehr speichern — auch nicht,
    um ihn zu korrigieren."""
    SafetyConfigArea.model_validate(
        {"escalation": {"mode": "irgendwas-aus-2024", "provider": "eigenbau"}})


def test_gleicher_schluessel_zwei_bedeutungen_bleibt_getrennt() -> None:
    """``pattern`` heißt in ``classify-overrides`` eine Muster-ID und in
    ``guide-rules`` ein Regex. Eine Zuordnung nach Schlüsselnamen würde dem
    Regex-Feld Muster-IDs vorschlagen — deshalb hängt die Auszeichnung am
    Modellfeld."""
    from boerdi.domain.config_models.base_governance import ClassifyOverridesArea
    from boerdi.domain.config_models.knowledge import GuideRulesArea

    beispiel = ClassifyOverridesArea.model_json_schema()["$defs"]["FewShotExample"]
    assert beispiel["properties"]["pattern"]["x-catalog"] == "patterns"

    regel = GuideRulesArea.model_json_schema()["$defs"]["MessageRule"]
    assert "x-catalog" not in regel["properties"]["pattern"]


# ── Wächter: keine Auszeichnung darf über den Bestand lügen ────────────────

def _resolve(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any] | None:
    """``$ref`` folgen und ein ``| None`` abstreifen — wie im Studio-Mapper."""
    for _ in range(10):
        ref = node.get("$ref")
        if not ref:
            break
        node = root.get("$defs", {}).get(ref.rsplit("/", 1)[-1], {})
    optionen = [o for o in node.get("anyOf", ()) if o.get("type") != "null"]
    if len(optionen) == 1:
        return _resolve(optionen[0], root)
    return node if not node.get("anyOf") else None


def _walk(node: Any, doc: Any, root: dict, pfad: str, treffer: list) -> None:
    """Schema und Dokument im Gleichschritt; sammelt jeden Wert außerhalb
    seiner ``x-choices``-Liste."""
    schema = _resolve(node, root) if isinstance(node, dict) else None
    if not schema:
        return
    erlaubt = schema.get("x-choices")
    if erlaubt is not None and isinstance(doc, str) and doc and doc not in erlaubt:
        treffer.append(f"{pfad} = {doc!r} (erlaubt: {erlaubt})")

    if isinstance(doc, dict):
        for schluessel, unter in (schema.get("properties") or {}).items():
            if schluessel in doc:
                _walk(unter, doc[schluessel], root, f"{pfad}.{schluessel}", treffer)
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            for schluessel, wert in doc.items():
                _walk(extra, wert, root, f"{pfad}.{schluessel}", treffer)
    elif isinstance(doc, list) and isinstance(schema.get("items"), dict):
        for i, wert in enumerate(doc):
            _walk(schema["items"], wert, root, f"{pfad}[{i}]", treffer)


def _seed_dokumente() -> list[tuple[str, dict[str, Any]]]:
    """``(Bereichsschlüssel, Dokument)`` für jede Seed-Datei mit einem Modell."""
    out: list[tuple[str, dict[str, Any]]] = []
    for datei in sorted(_SEEDS.rglob("*")):
        if not datei.is_file() or datei.suffix not in (".yaml", ".yml", ".md"):
            continue
        key = datei.relative_to(_SEEDS).with_suffix("").as_posix()
        if model_for(key) is None:
            continue
        text = datei.read_text(encoding="utf-8")
        if datei.suffix == ".md":
            kopf = re.match(r"^---\n(.*?)\n---\n", text, re.S)
            doc = {"frontmatter": yaml.safe_load(kopf.group(1)) or {}} if kopf else {}
        else:
            doc = yaml.safe_load(text) or {}
        if isinstance(doc, dict):
            out.append((key, doc))
    return out


def test_seed_dokumente_werden_ueberhaupt_gefunden() -> None:
    """Ohne diese Zusicherung wäre der Wächter darunter still grün, sobald der
    Baum-Durchlauf ins Leere liefe."""
    dokumente = _seed_dokumente()
    schluessel = {k for k, _ in dokumente}
    assert len(dokumente) >= 40
    assert "01-base/safety-config" in schluessel
    assert any(k.startswith("03-patterns/") for k in schluessel)


def test_keine_auswahlliste_luegt_ueber_den_seed_bestand() -> None:
    """Jeder ausgelieferte Wert eines ``x-choices``-Feldes muss in seiner Liste
    stehen. Sonst wäre die Auswahl schlimmer als Freitext: sie böte dem
    Redakteur genau den Wert nicht an, der dort schon steht."""
    treffer: list[str] = []
    for key, doc in _seed_dokumente():
        modell = model_for(key)
        assert modell is not None
        schema = modell.model_json_schema()
        _walk(schema, doc, schema, key, treffer)
    assert treffer == [], "Seed-Werte außerhalb ihrer Auswahlliste:\n  " + "\n  ".join(treffer)


def _katalognamen_im_schema() -> set[str]:
    namen: set[str] = set()

    def sammle(knoten: Any) -> None:
        if isinstance(knoten, dict):
            if isinstance(knoten.get("x-catalog"), str):
                namen.add(knoten["x-catalog"])
            for wert in knoten.values():
                sammle(wert)
        elif isinstance(knoten, list):
            for wert in knoten:
                sammle(wert)

    for modell in set(AREA_MODELS.values()):
        sammle(modell.model_json_schema())
    return namen


def test_jeder_genannte_katalog_wird_auch_geliefert() -> None:
    """Ein vertippter Katalogname bliebe sonst still: das Feld sähe aus wie
    immer, nur ohne Vorschläge."""
    unbekannt = sorted(_katalognamen_im_schema() - set(CATALOG_NAMES))
    assert unbekannt == [], f"Kataloge ohne Quelle in /api/config/choices: {unbekannt}"


@pytest.mark.parametrize("name", ["patterns", "rag_areas", "tools"])
def test_die_gemeldeten_faelle_sind_verdrahtet(name: str) -> None:
    """Die drei Kataloge aus der Nutzer-Meldung — ohne sie wäre der ganze
    Mechanismus gebaut, aber am Anlass vorbei."""
    assert name in _katalognamen_im_schema()
