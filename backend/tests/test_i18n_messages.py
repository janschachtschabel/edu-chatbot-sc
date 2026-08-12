"""Der Backend-Katalog und die Sprachauflösung (C1-e).

Dieselben Prüfungen wie im Frontend (`en.spec.ts`), aus demselben Grund: den
Wortlaut kann ein Test nicht beurteilen, das still Schiefgehende schon — eine
fehlende Sprache, ein verlorener Platzhalter, ein Schlüssel, den niemand
übersetzt hat.

Dazu eine Prüfung, die es im Frontend so nicht gibt: **jeder Schlüssel, den
`api/` liest, muss im Katalog stehen.** Fehlt er, zeigt der Endpunkt den
Schlüssel selbst als Fehlermeldung — sichtbar, aber erst im Betrieb.
"""

import ast
import pathlib

import pytest

from boerdi.i18n import MESSAGES, msg, pick_localized, resolve_locale

API_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "boerdi" / "api"


# ── Sprachauflösung ────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "de"),
        ("", "de"),
        ("en", "en"),
        ("de", "de"),
        # Untertags zählen nicht: `en-GB` ist Englisch.
        ("en-GB,en;q=0.9,de;q=0.8", "en"),
        ("de-DE,de;q=0.9,en;q=0.8", "de"),
        # Nicht unterstützte Sprachen fallen durch, nicht auf.
        ("fr-FR,fr;q=0.9", "de"),
        ("fr,en;q=0.5", "en"),
        # Die Gewichtung entscheidet, nicht die Reihenfolge.
        ("en;q=0.3,de;q=0.7", "de"),
        ("de;q=0.2,en;q=0.9", "en"),
        # `q=0` heisst ausdrücklich „nicht akzeptabel".
        ("en;q=0", "de"),
        # Ein Platzhalter ist keine Sprachwahl.
        ("*", "de"),
        # Kaputte Gewichte werden übergangen, nicht geraten.
        ("en;q=viel", "de"),
        ("   EN   ", "en"),
    ],
)
def test_resolve_locale(header: str | None, expected: str) -> None:
    assert resolve_locale(header) == expected


# ── Die gepflegte Fassung wählen (C1-g2) ───────────────────────────────────
# Backend-Zwilling von `pickLocalized` im Widget: dieselbe Regel, andere Seite.
# Die Studio-Config trägt beide Fassungen je Schlüssel, und wer den Wert
# BENUTZT, wählt — deshalb steht die Wahl hier und nicht im Loader.
@pytest.mark.parametrize(
    ("de", "en", "lang", "expected"),
    [
        ("Über WLO", "About WLO", "en", "About WLO"),
        # Leer heißt „nicht gepflegt", nicht „leerer Knopftext".
        ("Über WLO", "", "en", "Über WLO"),
        ("Über WLO", "   ", "en", "Über WLO"),
        ("Über WLO", "About WLO", "de", "Über WLO"),
    ],
)
def test_pick_localized(de: str, en: str, lang: str, expected: str) -> None:
    assert pick_localized(de, en, lang) == expected


# ── Katalog ────────────────────────────────────────────────────────────────
def test_beide_sprachen_tragen_dieselben_schluessel() -> None:
    fehlen_en = set(MESSAGES["de"]) - set(MESSAGES["en"])
    fehlen_de = set(MESSAGES["en"]) - set(MESSAGES["de"])
    assert not fehlen_en, f"ohne englische Fassung: {sorted(fehlen_en)}"
    assert not fehlen_de, f"ohne deutsche Fassung: {sorted(fehlen_de)}"


def test_platzhalter_stimmen_je_schluessel_ueberein() -> None:
    def platzhalter(text: str) -> set[str]:
        return {teil.split("}")[0] for teil in text.split("{")[1:] if "}" in teil}

    for key, de in MESSAGES["de"].items():
        assert platzhalter(MESSAGES["en"][key]) == platzhalter(de), f"Platzhalter: {key}"


def test_kein_text_ist_unuebersetzt_stehengeblieben() -> None:
    for key, de in MESSAGES["de"].items():
        assert MESSAGES["en"][key] != de, f"unübersetzt aus DE kopiert: {key}"


def test_kein_umlaut_in_der_englischen_fassung() -> None:
    for key, text in MESSAGES["en"].items():
        assert not set(text) & set("äöüÄÖÜß"), f"deutscher Rest in {key}: {text}"


# ── Einsetzen ──────────────────────────────────────────────────────────────
def test_msg_setzt_platzhalter_in_beiden_sprachen() -> None:
    assert msg("de", "field.empty", field="greeting") == "greeting darf nicht leer sein"
    assert msg("en", "field.empty", field="greeting") == "greeting must not be empty"


def test_unbekannter_schluessel_zeigt_sich_statt_zu_stuerzen() -> None:
    # Sichtbar falsch ist besser als ein 500 im Fehlerpfad — und besser als ein
    # stiller deutscher Rückfall, den niemand bemerkt.
    assert msg("en", "gibt.es.nicht") == "gibt.es.nicht"


def test_fehlender_platzhalter_bleibt_stehen_statt_zu_stuerzen() -> None:
    # Ein vergessener Parameter ist ein Programmierfehler; er darf aber nicht
    # aus einer 400 eine 500 machen.
    assert msg("de", "field.empty") == "{field} darf nicht leer sein"


# ── Wächter: kein Schlüssel ohne Katalog-Eintrag ───────────────────────────
def _keys_used_in_api() -> set[str]:
    """Jeder `msg(..., "key", ...)`-Aufruf in `api/`, Schlüssel als Literal."""
    used: set[str] = set()
    for path in sorted(API_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name != "msg" or len(node.args) < 2:
                continue
            key = node.args[1]
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                used.add(key.value)
    return used


def test_jeder_in_api_gelesene_schluessel_steht_im_katalog() -> None:
    fehlen = _keys_used_in_api() - set(MESSAGES["de"])
    assert not fehlen, f"gelesen, aber nicht im Katalog: {sorted(fehlen)}"


# ── Wächter: keine Meldung am Katalog vorbei ───────────────────────────────
#: Jede ``HTTPException``-Meldung in ``api/``, die NICHT durch ``msg()`` geht,
#: mit dem Grund, warum sie einsprachig bleiben darf. Der Wächter läuft in die
#: Gegenrichtung zu ``test_jeder_in_api_gelesene_schluessel_steht_im_katalog``:
#: der eine findet den Schlüssel ohne Text, dieser den Text ohne Schlüssel.
#:
#: Er ersetzt das Suchmuster über Prosa, mit dem C1-e zweimal untergezählt hat
#: — zuletzt fehlte ``quality.py`` ganz, weil der Satz weder Umlaut noch eines
#: der gesuchten Wörter trug. Eine neue Meldung bricht diesen Test, und die
#: Entscheidung „übersetzen oder eintragen" fällt dann bewusst.
# Was hier steht, ist NICHT „klingt technisch“ — sondern gemessen: der Studio
# zeigt diesen Text nie an. Entweder bildet er ihn per Status-Code oder Praefix
# auf einen eigenen Katalog-Text ab, oder er ruft den Endpunkt gar nicht auf,
# oder er gehoert dem Widget, das Fehler-`detail` verwirft (C1-e3).
BEWUSST_EINSPRACHIG: dict[str, dict[str, str]] = {
    "config.py": {
        "'File not found'": "404 — der Studio zeigt `error.noSuchArea`",
        "'Invalid path'": "Protokoll-Marker: `area-doc-editor` bildet den 400er "
                            "per Präfix auf `error.badAreaKey` ab",
        "f'unknown config area: {area}'": "404 — wie `File not found`",
    },
    "config_areas.py": {
        "f'Duplicate id: {mt.id}'": "kein Studio-Aufrufer: die schmale "
                                    "material-types-Route ruft niemand",
        (
            'f"Invalid category \'{mt.category}\' for id \'{mt.id}\' '
            '(must be one of {sorted(valid_categories)})"'
        ): "dito — kein Studio-Aufrufer",
    },
    "config_elements.py": {
        "f'{label} IDs must be unique.'": "kein Studio-Aufrufer: die "
                                          "Element-PUT-Routen ruft niemand",
    },
    "deps.py": {
        "'Studio API key required'": "Betreiber-Meldung, kein Redaktions-Text",
        "'Admin endpoints are disabled: STUDIO_API_KEY is not configured. "
        "Set it, or set BOERDI_ALLOW_OPEN_ADMIN=1 for local development.'": "dito",
        "f'not implemented yet (arrives with {package})'": "Vertrags-Stub, kein Betrieb",
    },
    "sessions.py": {
        "'Invalid session id'": "nur der öffentliche Widget-Endpunkt; "
                                "`loadHistory` macht `if (!resp.ok) return []`",
    },
    "speech.py": {
        "'Spracherkennung fehlgeschlagen.'": "nur Widget — verwirft `detail` (C1-e2)",
        "'Sprachsynthese fehlgeschlagen.'": "dito",
        "f'Audio zu groß (max {MAX_AUDIO_BYTES // (1024 * 1024)} MB).'": "dito",
        "f'Text zu lang (max {MAX_TTS_CHARS} Zeichen).'": "dito",
    },
    "studio_bff.py": {
        "'Wrong password'": "der Login bildet per STATUS-Code auf "
                            "`login.error.wrongPassword` ab",
    },
    "widget.py": {
        "'invalid path'": "Auslieferung von Dateien, kein Redaktions-Text",
        "f'asset not found: {asset_name}'": "dito",
        "'Widget bundle not built yet. "
        "Run `cd frontend && npm run build:widget` first.'": "Bau-Hinweis für Entwickler",
    },
}


def _detail_of(call: ast.Call) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == "detail":
            return kw.value
    return call.args[1] if len(call.args) >= 2 else None


def _traegt_freien_text(node: ast.AST) -> bool:
    """Steckt in ``node`` ein Text-Literal ausserhalb eines ``msg()``-Aufrufs?

    Nachschlage-Schlüssel zählen nicht — weder als Wörterbuch-Schlüssel noch
    als Index. Die Pydantic-Fehlerliste in ``config.py`` baut ihre Einträge aus
    ``err['loc']``/``err['msg']``/``err['type']``: das ist Struktur, kein Satz.
    """
    stapel = [node]
    while stapel:
        cur = stapel.pop()
        if isinstance(cur, ast.Call) and isinstance(cur.func, ast.Name) and cur.func.id == "msg":
            continue
        if isinstance(cur, ast.Constant) and isinstance(cur.value, str) and cur.value.strip():
            return True
        if isinstance(cur, ast.Dict):
            stapel.extend(v for v in cur.values if v is not None)
            continue
        if isinstance(cur, ast.Subscript):
            stapel.append(cur.value)
            continue
        stapel.extend(ast.iter_child_nodes(cur))
    return False


def _freie_meldungen() -> dict[str, set[str]]:
    gefunden: dict[str, set[str]] = {}
    for path in sorted(API_DIR.rglob("*.py")):
        texte: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "HTTPException":
                continue
            detail = _detail_of(node)
            if detail is not None and _traegt_freien_text(detail):
                texte.add(ast.unparse(detail))
        if texte:
            gefunden[path.name] = texte
    return gefunden


def test_jede_meldung_geht_durch_den_katalog_oder_steht_hier() -> None:
    gefunden = _freie_meldungen()
    erwartet = {name: set(eintraege) for name, eintraege in BEWUSST_EINSPRACHIG.items()}
    neu = {n: sorted(t - erwartet.get(n, set())) for n, t in gefunden.items()}
    assert not any(neu.values()), (
        "Meldung weder übersetzt noch als bewusst einsprachig eingetragen: "
        f"{ {n: t for n, t in neu.items() if t} }"
    )
    weg = {n: sorted(t - gefunden.get(n, set())) for n, t in erwartet.items()}
    assert not any(weg.values()), (
        f"steht in BEWUSST_EINSPRACHIG, existiert aber nicht mehr: "
        f"{ {n: t for n, t in weg.items() if t} }"
    )


# ── C1-e3: die vier Meldungen, die ein Redakteur ROH liest ─────────────────
# Gemessen, nicht geschätzt: von 17 einsprachigen Meldungen zeigt der Studio
# genau diese drei unverändert an (`describeApiError`/`ActionState`). Die
# übrigen vierzehn bildet er über Status-Code oder Präfix auf eigene
# Katalog-Texte ab oder ruft ihren Endpunkt nie auf — sie bleiben englisch,
# begründet in `BEWUSST_EINSPRACHIG`.
@pytest.mark.parametrize(
    ("key", "de_fragment", "en_fragment"),
    [
        ("mcp.urlRequired", "URL", "URL"),
        ("snapshots.notFound", "Snapshot nicht gefunden", "Snapshot not found"),
        ("quality.logNotFound", "Log nicht gefunden", "Log not found"),
    ],
)
def test_e3_messages_are_bilingual(key: str, de_fragment: str, en_fragment: str) -> None:
    assert de_fragment in msg("de", key)
    assert en_fragment in msg("en", key)
    assert msg("de", key) != msg("en", key)
