"""Der ausgelieferte Config-Seed-Baum (W6).

Nutzer-Entscheid 2026-07-30: eine frische Installation muss den Chatbot starten
können, **ohne** dass der ALT-Baum (`../badboerdi`) daneben liegt. Der letzte
Redaktionsstand wird deshalb als versionierter Seed mitgeliefert; das Studio
bleibt der Weg für spätere Änderungen (die DB ist danach die Quelle der
Wahrheit, `boerdi export-config` schreibt sie wieder heraus).

Diese Tests sind ein Vollständigkeits-Wächter: fehlt eine Seed-Datei, fällt das
hier auf und nicht erst bei einer stillen halb-leeren Installation. Sie pinnen
bewusst **keine** exakte Dateizahl — Pattern und Bereiche dürfen wachsen.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.settings import get_settings

_SEEDS = Path(__file__).resolve().parents[1] / "seeds"


def test_kein_seed_schluessel_wird_als_boolean_gelesen() -> None:
    """YAML 1.1 liest ``off``/``on``/``yes``/``no`` als Boolean — auch als SCHLÜSSEL.

    Befund 2026-08-13: ``presets:`` in ``01-base/safety-config.yaml`` hatte den
    Schlüssel ``off:``. PyYAML lieferte dafür ``False``. Folge: die
    Sicherheitsstufe „off" fand ihr Preset nie (das Studio meldete „kein Preset
    hinterlegt") und zeigte stattdessen einen Geister-Eintrag namens ``false``.
    Ein Speichern über die Oberfläche hätte daraus die Zeichenkette ``"false"``
    gemacht — weder das eine noch das andere.

    Geprüft wird der ganze Baum, nicht die eine Datei: die Falle schnappt bei
    jedem neuen ``off:``/``no:``/``yes:``-Schlüssel wieder zu, und sie ist beim
    Lesen unsichtbar — im Editor steht da ein Wort, im Speicher ein Boolean.
    """
    treffer: list[str] = []

    def pruefe(knoten: Any, pfad: str) -> None:
        if isinstance(knoten, dict):
            for schluessel, wert in knoten.items():
                if not isinstance(schluessel, str):
                    treffer.append(
                        f"{pfad}: {schluessel!r} ({type(schluessel).__name__})")
                pruefe(wert, f"{pfad}/{schluessel}")
        elif isinstance(knoten, list):
            for i, wert in enumerate(knoten):
                pruefe(wert, f"{pfad}[{i}]")

    for datei in sorted(_SEEDS.rglob("*.yaml")):
        pruefe(yaml.safe_load(datei.read_text(encoding="utf-8")), datei.name)

    assert not treffer, (
        "Seed-Schlüssel wird nicht als Zeichenkette gelesen — in "
        'Anführungszeichen setzen ("off:"): ' + "; ".join(treffer))


def _pattern_frontmatter() -> dict[str, dict[str, Any]]:
    """``{Pattern-ID: Frontmatter}`` aller Seed-Antwortmuster."""
    out: dict[str, dict[str, Any]] = {}
    for md in sorted((_SEEDS / "03-patterns").glob("m*.md")):
        head = re.match(r"^---\n(.*?)\n---\n", md.read_text(encoding="utf-8"), re.S)
        assert head, f"{md.name}: kein YAML-Frontmatter"
        fm = yaml.safe_load(head.group(1)) or {}
        out[str(fm.get("id") or md.stem)] = fm
    return out

# Die Bereichsgruppen, aus denen der Bot besteht. Fehlt eine, fehlt eine ganze
# Fähigkeit — z.B. ohne ``03-patterns`` gäbe es keine Antwortmuster.
_ERWARTETE_GRUPPEN = (
    "01-base", "02-domain", "03-patterns", "04-entities", "04-intents",
    "04-personas", "04-signals", "04-states", "05-canvas", "05-knowledge",
)


def test_seed_baum_wird_mit_ausgeliefert():
    assert _SEEDS.is_dir(), (
        "Ohne backend/seeds startet eine frische Installation ohne Konfiguration."
    )


def test_seed_baum_deckt_alle_bereichsgruppen_ab():
    fehlend = [g for g in _ERWARTETE_GRUPPEN if not (_SEEDS / g).is_dir()]
    assert not fehlend, f"Seed-Gruppen fehlen: {fehlend}"


def test_seed_baum_traegt_die_antwortmuster():
    # M01-M16 kamen aus dem alten Chatbot; neue dürfen dazukommen, keines darf
    # verschwinden, ohne dass es hier auffällt.
    muster = sorted(p.stem.split("-")[0] for p in (_SEEDS / "03-patterns").glob("m*.md"))
    assert len(muster) >= 16, f"nur {len(muster)} Antwortmuster im Seed: {muster}"


def test_seed_baum_traegt_die_basis_konfiguration():
    # Stichproben quer durch die Gruppen — jede steht für einen Pfad, der ohne
    # sie stumm ausfiele (Begrüßung, Safety, Personas, Zustände).
    for rel in (
        "01-base/welcome-config.yaml",
        "01-base/safety-config.yaml",
        "01-base/policy.yaml",
        "04-personas",
        "04-states",
    ):
        assert (_SEEDS / rel).exists(), f"Seed fehlt: {rel}"


def test_prod_image_liefert_den_seed_baum_mit():
    # „Ausgeliefert" heißt: auch im Container. Ohne diese COPY-Zeile zeigte
    # CONFIG_SEED_DIR=seeds in einer frischen Docker-Installation auf ein
    # Verzeichnis, das es dort nicht gibt — der Import liefe ins Leere und der
    # Bot startete ohne Konfiguration.
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    assert dockerfile.is_file()
    inhalt = dockerfile.read_text(encoding="utf-8")
    assert "backend/seeds" in inhalt, "Dockerfile kopiert backend/seeds nicht"


def test_jeder_im_pattern_genannte_tool_name_existiert():
    # ``_select_active_tools`` filtert TOOL_DEFINITIONS gegen diese Liste. Ein
    # Name, den es dort nicht gibt, verschwindet **still** — das Pattern sieht
    # dann weniger Werkzeuge als sein Autor glaubt, ohne Fehlermeldung.
    #
    # A-Kuration (2026-08-10): der KURATIERENDE Katalog gehört dazu. Er fehlte,
    # solange kein Muster ihn nennen konnte — und hätte das erste, das es tut,
    # als Tippfehler abgewiesen. ``_nameable_tools`` prüft beide Kataloge; ein
    # Wächter, der nur einen kennt, urteilt über eine andere Wirklichkeit als
    # der Code, den er absichert.
    from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
    bekannt = {
        t["function"]["name"]
        for t in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS)
    }
    unbekannt = {
        pid: [t for t in (fm.get("tools") or []) if t not in bekannt]
        for pid, fm in _pattern_frontmatter().items()
        if [t for t in (fm.get("tools") or []) if t not in bekannt]
    }
    assert not unbekannt, f"Pattern nennen Tools, die es nicht gibt: {unbekannt}"


# Werkzeuge, die BEWUSST in keinem Pattern stehen. Jeder Eintrag braucht einen
# Grund — die Liste ist der Ort, an dem „unerreichbar" eine Entscheidung ist
# statt eines Versehens.
_NICHT_UEBER_PATTERN = {
    # Betriebs-Sonde. Ein Modell, das sie im Gespräch aufruft, verbrennt einen
    # Zug für eine Auskunft, die den Nutzer nichts angeht.
    "wlo_health_check",
    # Sammel-Metadaten (Bulk-Variante zu ``get_node_details``). Mit W10
    # (2026-08-01) entschieden, vorher offen: bleibt draußen. Es stammt aus ALT
    # und war dort ebenso in keinem Muster; der Prompt-Block
    # ``render_tools_block`` nennt es zwar namentlich, aber der Block ist
    # STATISCH — er zählt alle zehn MCP-Werkzeuge auf, unabhängig von der aktiven
    # Tool-Liste des Musters, und trifft ``wlo_health_check`` genauso. Ein Muster
    # nur zu verdrahten, damit dieser Wächter schweigt, hieße einen Verbraucher
    # zu erfinden: die Karten-Pipeline holt ihre Metadaten aus den Suchtreffern
    # selbst, ein Bulk-Nachschlag für >3 Knoten kommt in keinem Pfad vor.
    "get_nodes_details",
}


def test_jedes_angebotene_werkzeug_ist_aus_einem_pattern_erreichbar():
    """Verallgemeinert den M17-Einzelfall zur Klassen-Prüfung.

    Befund 2026-07-31: ``get_wlo_content_text`` stand in TOOL_DEFINITIONS, aber
    in KEINEM Pattern — und Pattern mit ``tools:`` schneiden die Liste auf ihre
    eigenen Namen zu. Das Werkzeug war für das Modell unerreichbar: gebaut, ohne
    Verbraucher. Gemessen 2026-08-01: **kein einziges** Pattern nutzt
    ``sources: [mcp]`` ohne eigene ``tools:``-Liste, der Zweig in
    ``_select_active_tools``, der alle Werkzeuge anbietet, wird also nie
    betreten. Eine Ergänzung in TOOL_DEFINITIONS allein bleibt damit **immer**
    wirkungslos. Dieser Wächter macht genau das laut.
    """
    angeboten = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    erreichbar = {
        t for fm in _pattern_frontmatter().values() for t in (fm.get("tools") or [])
    }
    verwaist = sorted(angeboten - erreichbar - _NICHT_UEBER_PATTERN)
    assert not verwaist, (
        "Diese Werkzeuge bietet der Katalog dem Modell an, aber kein Pattern "
        f"nennt sie — sie sind unerreichbar: {verwaist}. Entweder in ein "
        "Pattern aufnehmen oder mit Begründung in _NICHT_UEBER_PATTERN."
    )


def test_die_server_registry_kennt_jedes_werkzeug_das_dem_modell_angeboten_wird():
    """W7b: jeder TOOL_DEFINITIONS-Name muss in der MCP-Server-Registry stehen.

    ``_get_server_url_for_tool`` (services/mcp/client.py) sucht den Namen in der
    Registry und fällt sonst **still** auf die Default-URL zurück. Live gemessen
    2026-07-31: die Registry listete zehn Werkzeuge, das Modell bekam dreizehn
    angeboten — darunter ``get_wlo_content_text``, das der damals konfigurierte
    Server gar nicht hatte. M17 rief also ins Leere, ohne dass irgendwo etwas
    aufgefallen wäre. Dieser Wächter macht genau diese Lücke laut.
    """
    import yaml

    roh = yaml.safe_load(
        (_SEEDS / "05-knowledge" / "mcp-servers.yaml").read_text(encoding="utf-8")
    )
    registriert = {
        name
        for server in (roh.get("servers") or [])
        for name in (server.get("tools") or [])
    }
    angeboten = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    fehlend = sorted(angeboten - registriert)
    assert not fehlend, f"Registry kennt diese angebotenen Werkzeuge nicht: {fehlend}"


def test_die_server_registry_nennt_kein_werkzeug_zweimal():
    """R4 (2026-08-11): der Wächter darüber liest in ein SET — eine doppelte
    Zeile fällt ihm nicht auf. Gemessen: ``get_url_text`` stand zweimal drin,
    weil die H5-Runde es eintrug, ohne zu sehen, dass die A1-Runde es beim
    Abholen vom Server schon aufgenommen hatte. Betrieblich folgenlos, aber wer
    später eine der beiden Zeilen entfernt, weiß nicht, welche gemeint war.
    """
    import collections

    import yaml

    roh = yaml.safe_load(
        (_SEEDS / "05-knowledge" / "mcp-servers.yaml").read_text(encoding="utf-8")
    )
    for server in roh.get("servers") or []:
        namen = list(server.get("tools") or [])
        doppelt = sorted(n for n, k in collections.Counter(namen).items() if k > 1)
        assert not doppelt, f"Server {server.get('id')!r} nennt doppelt: {doppelt}"


def test_verortungs_werkzeug_steht_in_beiden_infrage_kommenden_mustern():
    """A2: ``get_node_collections`` muss in M06 UND M08 stehen.

    Zwei Live-Läufe derselben Frage („In welchen Sammlungen ist der erste
    Treffer eingeordnet?") am 2026-08-10 landeten einmal in M08 und einmal in
    M06 — welches Muster greift, hängt am Muster des Vorzugs, nicht am Wortlaut.
    Nur eines von beiden zu bestücken hiesse deshalb, das Werkzeug in rund der
    Hälfte der Fälle fehlen zu lassen, und zwar STILL: ``_select_active_tools``
    schneidet die Liste wortlos auf die Namen des gewählten Musters zu.

    Gemessen, was dann passiert: ohne das Werkzeug rief das Modell viermal
    ``get_collection_contents`` auf, um die Sammlungen einzeln durchzusehen, und
    antwortete am Ende, es lasse sich nichts zuordnen. Mit ihm genügt ein Aufruf.
    """
    fm = _pattern_frontmatter()
    ohne = [pid for pid in ("M06", "M08")
            if "get_node_collections" not in (fm[pid].get("tools") or [])]
    assert not ohne, (
        f"get_node_collections fehlt in {ohne} — die Verortungsfrage landet "
        "mal in M06, mal in M08; fehlt es in einem, faellt es dort still aus."
    )


def test_m11_kennt_m17_als_moeglichen_vor_inhalt():
    # M11 (iterative Nachbearbeitung) arbeitet auf dem VORIGEN Bot-Inhalt aus
    # der Gesprächshistorie. Seit M17 kann dieser Vor-Inhalt auch ein geholtes
    # Material sein — steht M17 nicht in den Auswahlregeln, schickt der
    # Klassifikator ein „mach das kürzer" nach einem Volltext-Zug woandershin.
    fm = _pattern_frontmatter()["M11"]
    regeln = " ".join(str(x) for x in (fm.get("when_to_use") or []))
    assert "M17" in regeln


def test_m18_laesst_die_vorschau_zeigen_statt_nacherzaehlen():
    # S4 (2026-08-11): Den Vorschautext des Servers legt der Chat seit S2
    # SELBST vor — als gerahmten Kasten (``turn_persist`` → ``inline_documents``,
    # Art ``schreib_vorschau``), wörtlich und mit der Rückfrage im Fuß.
    # Stünde in der Kernregel weiter, das Modell solle die Vorschau
    # „VOLLSTÄNDIG und in seinen Worten" vorlegen, bekäme der Nutzer beides:
    # den Kasten UND eine Nacherzählung derselben Felder.
    # Kleingeschrieben verglichen: der Seed betont per Versalien (``ZWEISTUFIG``,
    # ``NÄCHSTEN``), und ob eine Regel dasteht, darf nicht daran hängen.
    kr = (_pattern_frontmatter()["M18"].get("core_rule") or "").lower()
    assert "in seinen worten" not in kr, (
        "Die Vorschau zeigt der Chat selbst — das Modell ordnet nur ein"
    )
    # Was das Modell nach einem Ja tun MUSS, und was seit dem Fingerabdruck-
    # Fund die tragende Zeile ist: ``domain/write_confirm.token_for`` gibt den
    # Schlüssel nur bei Feld-für-Feld gleichen Argumenten heraus. Weicht eines
    # ab, wird nicht bestätigt, sondern still neu vorgeschaut.
    assert "denselben argumenten" in kr, (
        "Ohne diese Regel scheitert die Bestätigung am Fingerabdruck"
    )


def test_m16_nennt_nur_das_tool_das_sein_resolver_wirklich_aufruft():
    # W5-1: der Themenseiten-Pfad ist ein EIN-Call-Pfad geworden —
    # ``get_topic_page_content`` löst die Seite selbst auf. Die vorgeschaltete
    # ``search_wlo_topic_pages``-Suche gibt es nicht mehr; sie im Pattern stehen
    # zu lassen, beschreibt dem Studio-Redakteur einen Weg, den der Code nicht
    # geht.
    assert _pattern_frontmatter()["M16"].get("tools") == ["get_topic_page_content"]


def test_config_seed_dir_zeigt_standardmaessig_auf_den_ausgelieferten_baum():
    # Ohne gesetzten Default müsste jede Installation die Umgebungsvariable
    # kennen — genau die Hürde, die W6 beseitigt.
    get_settings.cache_clear()
    assert get_settings().config_seed_dir == "seeds"


# ── C1-g1a: der ausgelieferte Seed traegt die englische Fassung ────────────
# Ohne Inhalt waeren die neuen `*_en`-Felder Maschinerie ohne Verbraucher —
# genau die Fehlerklasse, die dieses Projekt schon siebenmal protokolliert hat.

def test_seed_begruessung_ist_zweisprachig():
    cfg = yaml.safe_load(
        (_SEEDS / "01-base" / "welcome-config.yaml").read_text(encoding="utf-8")
    )["welcome"]
    assert cfg["greeting_en"].strip()
    assert len(cfg["quick_replies_en"]) == len(cfg["quick_replies"])
    # Der Tour-Chip wird per TEXT verglichen, nicht per Position — die
    # englische Fassung muss deshalb woertlich in der englischen Liste stehen.
    assert cfg["tour_reply_en"] in cfg["quick_replies_en"]
    assert cfg["tour_reply"] in cfg["quick_replies"]


def test_seed_kopfzeilen_knoepfe_sind_zweisprachig():
    buttons = yaml.safe_load(
        (_SEEDS / "01-base" / "header-nav.yaml").read_text(encoding="utf-8")
    )["header_nav"]["buttons"]
    assert buttons
    for b in buttons:
        assert b["label_en"].strip(), b["id"]


# ── C1-g2a: die Lotsen-Beschriftungen ──────────────────────────────────────

def test_seed_lotsen_regeln_sind_zweisprachig():
    rules = yaml.safe_load(
        (_SEEDS / "02-domain" / "guide-rules.yaml").read_text(encoding="utf-8")
    )["message_rules"]
    assert rules
    for r in rules:
        assert r.get("label_en", "").strip(), r["label"]


# ── C1-g2b: die Kontext-Aktionen ──────────────────────────────────────────

def test_seed_kontext_aktionen_sind_zweisprachig():
    cfg = yaml.safe_load(
        (_SEEDS / "01-base" / "context-actions.yaml").read_text(encoding="utf-8")
    )["context_actions"]
    for kind, text in cfg["greetings"].items():
        en = cfg["greetings_en"].get(kind, "")
        assert en.strip(), kind
        # `{title}` ist keine Zierde: der Knoten ersetzt ihn durch den
        # Seitentitel. Fällt er beim Übersetzen weg, grüßt der Bot ohne zu
        # sagen, WO der Nutzer gerade ist.
        assert ("{title}" in text) == ("{title}" in en), kind
    for kind, pills in cfg["pills"].items():
        for p in pills:
            assert p.get("label_en", "").strip(), f"{kind}: {p['label']}"


# ── K (2026-08-11): Intent ↔ Muster, die Verknüpfung selbst ──────────────
# Intents und Muster sind zwei getrennte Listen, die der Klassifikator-Prompt
# nebeneinander rendert. Verbunden werden sie an genau ZWEI Stellen: in den
# Few-Shot-Beispielen (dort stehen intent und pattern zusammen in einer Zeile)
# und in der ``when_to_use``-Prosa der Muster. Gemessen 2026-08-11: die drei
# neuen Intents I09/I10/I11 kamen an keiner der beiden vor — das Modell sah sie
# und die neuen Muster, aber nie ihre Zuordnung.


def _intents() -> list[dict[str, Any]]:
    roh = yaml.safe_load(
        (_SEEDS / "04-intents" / "intents.yaml").read_text(encoding="utf-8")
    )
    return roh.get("intents") or []


def _intent_ids() -> list[str]:
    return [i["id"] for i in _intents()]


def _few_shots() -> list[dict]:
    import yaml

    roh = yaml.safe_load(
        (_SEEDS / "01-base" / "classify-overrides.yaml").read_text(encoding="utf-8")
    )
    return roh.get("few_shot_examples") or []


def test_jeder_intent_hat_ein_beispiel_mit_seinem_muster():
    """Ohne ein Paar sieht der Klassifikator nie, welches Muster gemeint ist."""
    gepaart = {ex.get("intent") for ex in _few_shots() if ex.get("pattern")}
    ohne = sorted(set(_intent_ids()) - gepaart)
    assert ohne == [], (
        f"Diese Intents haben kein Few-Shot-Beispiel mit Muster: {ohne}. "
        "Sie und ihr Muster treffen sich im Prompt dann nirgends."
    )


def test_die_beispiele_nennen_nur_vorhandene_intents_und_muster():
    """Ein Beispiel auf ein gelöschtes Muster lehrt dem Modell einen Namen,
    den ``_select_active_tools`` nicht kennt."""
    muster = set(_pattern_frontmatter())
    intents = set(_intent_ids())
    kaputt = [
        (ex.get("input"), ex.get("intent"), ex.get("pattern"))
        for ex in _few_shots()
        if ex.get("intent") not in intents or ex.get("pattern") not in muster
    ]
    assert kaputt == [], f"Few-Shots mit unbekanntem Intent/Muster: {kaputt}"


def test_die_auftrags_muster_nennen_ihren_intent():
    """M18/M19/M20 sind die Muster der drei neuen Intents. Zehn Bestandsmuster
    nennen ihren Intent in ``when_to_use`` (M09: „Intent I04 … UND Topic"); die
    drei neuen taten es nicht. Der Klassifikator liest diese Zeilen — fehlt der
    Bezug, muss er die Zuordnung erraten."""
    fm = _pattern_frontmatter()
    for pid, iid in (("M18", "I09"), ("M19", "I10"), ("M20", "I11")):
        zeilen = " ".join(fm[pid].get("when_to_use") or [])
        assert iid in zeilen, f"{pid} nennt {iid} nicht in when_to_use"


# Bewusst geduldet: alle diese Überläufe gibt es im ALT-Baum genauso
# (`../badboerdi/backend/chatbots/wlo/v1/{03-patterns,04-intents}`, 2026-08-11
# nachgezählt — dieselben Feld-Paare, teils sogar länger: ALT I03.examples hat
# 13). Sie sind Verbatim-Port. Sie zu kürzen wäre eine stille Verhaltens-
# änderung am Bestand, ein anderer Vorgang als der Befund, den dieser Test
# pinnt: dass NEU-Einträge lautlos hinter den Deckel rutschten.
_ALT_UEBERLAEUFE = {
    ("M04", "trigger_phrases"),
    ("M09", "trigger_phrases"),
    ("M10", "when_not_to_use"),
    ("M10", "trigger_phrases"),
    ("M14", "trigger_phrases"),
    ("I01", "examples"),
    ("I02", "examples"),
    ("I03", "trigger_verbs"),
    ("I03", "examples"),
    ("I05", "examples"),
    ("I07", "examples"),
}

_MUSTER_LISTEN = (
    "when_to_use", "when_not_to_use", "trigger_phrases", "discriminators",
)
_INTENT_LISTEN = (
    "trigger_verbs", "negative_triggers", "discriminators", "examples",
)


def _sichtbarer_text(eintrag: Any) -> str:
    """Der Teil eines Listeneintrags, der im gerenderten Block landet.

    Prosa-Einträge stehen dort wörtlich; Diskriminatoren erscheinen über ihre
    ``rule``, Negativ-Trigger über ihre ``phrase``."""
    if isinstance(eintrag, dict):
        return str(eintrag.get("rule") or eintrag.get("phrase") or "")
    return str(eintrag or "")


def _abgeschnitten(
    defs: dict[str, dict[str, Any]],
    render,
    felder: tuple[str, ...],
    erlaubt: frozenset[tuple[str, str]] = frozenset(),
) -> list[tuple[str, str, str]]:
    """Welche Seed-Zeilen tauchen im gerenderten Block NICHT auf?"""
    fehlend: list[tuple[str, str, str]] = []
    for kennung, fm in defs.items():
        gerendert = render([fm])
        for feld in felder:
            if (kennung, feld) in erlaubt:
                continue
            for eintrag in fm.get(feld) or []:
                text = _sichtbarer_text(eintrag)
                if text and text not in gerendert:
                    fehlend.append((kennung, feld, text[:70]))
    return fehlend


def _alle_abgeschnittenen(
    erlaubt: frozenset[tuple[str, str]] = frozenset(),
) -> list[tuple[str, str, str]]:
    """Beide Blöcke — Muster und Intents — in einem Durchgang."""
    from boerdi.services.classify_prompt_blocks import (
        _render_intents_block,
        _render_patterns_hint_block,
    )

    return _abgeschnitten(
        _pattern_frontmatter(), _render_patterns_hint_block, _MUSTER_LISTEN, erlaubt,
    ) + _abgeschnitten(
        {str(i.get("id")): i for i in _intents()},
        _render_intents_block,
        _INTENT_LISTEN,
        erlaubt,
    )


def test_jede_gepflegte_zeile_erreicht_den_klassifikator():
    """Was der Prompt abschneidet, hat der Redakteur umsonst gepflegt.

    Beide Renderer kappen jede Liste — Muster bei fünf Einträgen, Intents bei
    20/8/8/6. Das ist ALT-verbatim (``llm_classify_prompt.py:596``), und ALT
    nennt den Vertrag im Kommentar daneben ausdrücklich: „when_to_use (positive
    Trigger, **3-5 Items**)". Eine Zeile dahinter ist deshalb nicht bloss
    ungelesen, sie täuscht: sie steht im Studio, wirkt gepflegt und erreicht das
    Modell nie. Gemessen 2026-08-11 traf das die Löschen-Trigger von I09 — die
    zerstörende Aktion war die einzige ohne Signal.

    Gemessen statt gezählt: der Test rendert die ECHTEN Blöcke und sucht jede
    Seed-Zeile darin. Damit hängt er an keiner Deckel-Zahl — verschiebt jemand
    einen Deckel, verschiebt sich der Test mit.
    """
    fehlend = _alle_abgeschnittenen(_ALT_UEBERLAEUFE)
    assert fehlend == [], (
        "Diese Seed-Zeilen werden abgeschnitten und erreichen den Klassifikator "
        "nie:\n  " + "\n  ".join(f"{k}.{f}: {t}" for k, f, t in fehlend)
    )


def test_die_erlaubnisliste_bleibt_ehrlich():
    """Kürzt jemand eine ALT-Liste, muss ihr Eintrag hier verschwinden.

    Sonst deckt die Ausnahme ab da einen NEUEN Überlauf im selben Feld mit ab —
    und der Wächter oben schweigt genau dort, wo er sprechen müsste."""
    laufen_ueber = {(k, f) for k, f, _ in _alle_abgeschnittenen()}
    verwaist = sorted(_ALT_UEBERLAEUFE - laufen_ueber)
    assert verwaist == [], (
        "Diese Ausnahmen werden nicht mehr gebraucht und gehören gelöscht: "
        f"{verwaist}"
    )


def test_safety_presets_sind_vollstaendig_modelliert() -> None:
    """Jeder Preset-Schlüssel im Seed muss im Modell stehen — sonst ist er im
    Studio-Formular unsichtbar und nur über „Rohtext" erreichbar.

    Befund 2026-08-13 (Nutzer, Bildschirmfoto): das Formular meldete vier
    Schlüssel als unbekannt — ``legal_trigger_override`` (strict, paranoid),
    ``threshold_multiplier`` und ``double_check`` (paranoid). Alle drei werden
    von ``services/safety/service.py`` ausgewertet; sie fehlten nur im Modell.
    """
    from boerdi.domain.config_models.base_governance import SafetyPreset

    seed = yaml.safe_load(
        (_SEEDS / "01-base" / "safety-config.yaml").read_text(encoding="utf-8"))
    bekannt = set(SafetyPreset.model_fields)
    fremd = {
        f"{stufe}.{schluessel}"
        for stufe, preset in (seed.get("presets") or {}).items()
        for schluessel in preset
        if schluessel not in bekannt
    }
    assert not fremd, (
        "Preset-Schlüssel ohne Modellfeld (im Studio nur im Rohtext-Reiter "
        f"editierbar): {sorted(fremd)}")
