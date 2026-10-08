"""Paket 4c, B2: ``x-vorgabe`` — Listen, bei denen „nicht gesetzt“ nicht „leer“ heißt.

``sources`` ohne Angabe ist ``["mcp"]`` (``PatternDef``); ``rag_areas`` ohne
Angabe sind alle Bereiche, wenn ``rag`` unter den Quellen steht. Eine leere
Liste heißt jeweils „keine“. Im Formular sahen beide Fälle gleich aus, und wer
den letzten Eintrag entfernte, schaltete die Vorgabe ab, ohne es zu sehen
(Paket 4, C6). Das Studio zeigt an diesen Feldern, ob die Vorgabe gilt.

Bei den übrigen Listen heißt ein fehlender Schlüssel dasselbe wie ``[]`` (etwa
``tools``) — dort wäre der Hinweis Rauschen. Der Wächter hält die Liste eng.
``null`` liest die Laufzeit wie einen fehlenden Schlüssel
(``pattern_engine._pattern_from_dict``); das Studio stellt die Vorgabe wieder
her, indem es den Schlüssel entfernt.
"""

from typing import Any

from boerdi.domain.config_models import AREA_MODELS

#: Modell → Listen, deren „nicht gesetzt“ eine eigene Bedeutung hat.
ERWARTET = {
    ("PatternFrontmatter", "sources"),
    ("PatternFrontmatter", "rag_areas"),
}


def _markiert() -> dict[tuple[str, str], dict[str, Any]]:
    treffer: dict[tuple[str, str], dict[str, Any]] = {}
    for model in set(AREA_MODELS.values()):
        schema = model.model_json_schema()
        objekte = [schema, *(schema.get("$defs") or {}).values()]
        for objekt in objekte:
            for key, prop in (objekt.get("properties") or {}).items():
                if prop.get("x-vorgabe"):
                    treffer[(objekt["title"], key)] = prop
    return treffer


def test_genau_diese_listen_tragen_den_vorgabe_hinweis() -> None:
    assert set(_markiert()) == ERWARTET


def test_der_hinweis_laesst_den_katalog_am_eintrag_stehen() -> None:
    # Zwei Field()-Hinweise: der Vorgabe-Hinweis gehört an die Liste, der
    # Katalog an den Eintrag — keiner darf den anderen verdrängen.
    prop = _markiert()[("PatternFrontmatter", "rag_areas")]
    liste = next(option for option in prop["anyOf"] if option.get("type") == "array")
    assert liste["items"].get("x-catalog") == "rag_areas"
