"""Was das MODELL von einem Werkzeug-Ergebnis sieht — ``tool_result_redaction``.

Aus ``test_inline_grouping`` mitgezogen, als die Redaktion 2026-08-16 ihr eigenes
Modul bekam (dort blieb, was der NUTZER sieht). Alle Helfer sind rein — kein
LLM/MCP/RAG/Config, also laufen sie echt, ohne Mocks.
"""
from __future__ import annotations

import json

from boerdi.domain.tool_result_redaction import _redact_search_content_for_llm

# ════════════════════════════════════════════════════════════════════════
# _redact_search_content_for_llm — characterization (ALT: nur Integration)
# ════════════════════════════════════════════════════════════════════════

def test_redact_not_inline_mode_returns_truncated_raw():
    raw = "X" * 5000
    out = _redact_search_content_for_llm(
        "search_wlo_content", raw, [{"node_type": "content"}], False)
    assert out == raw[:4000]
    assert len(out) == 4000


def test_redact_inline_but_no_cards_returns_truncated_raw():
    raw = "Roh-Treffer-Text"
    assert _redact_search_content_for_llm("search_wlo_content", raw, [], True) == raw[:4000]


def test_redact_non_leak_tool_not_redacted():
    # search_wlo_collections steht NICHT auf der Leak-Liste → User sieht die Treffer.
    raw = "Sammlungs-Treffer"
    cards = [{"node_type": "content"}]
    assert _redact_search_content_for_llm("search_wlo_collections", raw, cards, True) == raw[:4000]


def test_redact_leak_tool_but_only_collections_not_redacted():
    # Leak-Tool, aber konkret nur Sammlungen zurück → keine Einzelinhalte → keine Redaction.
    raw = "Meta-Sammlung"
    cards = [{"node_type": "collection"}]
    assert _redact_search_content_for_llm("get_collection_contents", raw, cards, True) == raw[:4000]


def test_redact_einzelinhalte_replaced_with_summary_and_type_breakdown():
    raw = "Bruchrechnen-Video, Arbeitsblatt Brüche, ..."
    cards = [
        {"node_type": "content", "learning_resource_type": "Video"},
        {"node_type": "content", "learning_resource_type": "Video"},
        {"node_type": "content", "lrt_label": "Arbeitsblatt"},
    ]
    out = _redact_search_content_for_llm("search_wlo_content", raw, cards, True)
    assert out.startswith(
        "OK - search_wlo_content lieferte 3 Einzelinhalte (2x Video, 1x Arbeitsblatt)."
    )
    assert "Bruchrechnen" not in out          # Roh-Titel für die LLM redacted
    assert "NICHT im Antwort-Text" in out


# ════════════════════════════════════════════════════════════════════════
# search_wlo_all — Befund 2026-08-16 (Nutzer: „er findet die Optik-Sammlung
# weiterhin nicht")
#
# Das Kombi-Werkzeug antwortet in DREI Toepfen, und der unsichtbare
# (``content``) steht vorn. Gemessen an der echten Antwort zu „Optik": 86.933
# Zeichen, ``collections`` ab Zeichen 12.023, ``topicPages`` ab 17.410 — der
# Deckel ``raw_text[:4000]`` liess dem Modell 4 von 41 Node-IDs, allesamt
# Einzelinhalte. Es konnte „Optik" nicht in ``select_top_cards`` nennen, weil
# es die ID nie sah. #193 (Auswahl-Budget) und #196 (beide Kaesten) sitzen
# beide HINTER der Auswahl und konnten das nicht heilen.
# ════════════════════════════════════════════════════════════════════════

#: Die echte Node-ID der Sammlung „Optik" — sie ist der Anlass.
_OPTIK = "9e7ae956-e9df-430f-bace-f3db4b910013"

#: Nachbau der gemessenen Antwortform. Die Groessenverhaeltnisse sind Teil des
#: Befunds und gehoeren deshalb in die Vorlage: der ``content``-Topf steht vorn
#: und ist gross genug, dass die beiden sichtbaren Toepfe hinter dem
#: 4000-Zeichen-Deckel liegen — ohne das bestuenden die Tests zufaellig.
_FUELLTEXT = "Beschreibung des Einzelinhalts. " * 70   # ~2,2 KB je Treffer
_KOMBI = json.dumps({
    "query": "Optik",
    "content": {"total": 1170, "count": 2, "results": [
        {"nodeId": "c1", "title": "Optik — Grundwissen Physik",
         "nodeType": "content", "learningResourceTypes": ["Arbeitsblatt"],
         "description": _FUELLTEXT},
        {"nodeId": "c2", "title": "Unterrichtsreihe zum Licht",
         "nodeType": "content", "description": _FUELLTEXT},
    ]},
    "collections": {"total": 2, "count": 2, "results": [
        {"nodeId": "s1", "title": "Geometrische Optik", "nodeType": "collection",
         "description": "Strahlenoptik fuer die Sek I.",
         "keywords": ["Licht", "Schatten"], "disciplines": ["Physik"],
         "educationalContexts": ["Sekundarstufe I"],
         "previewUrl": "https://repo/preview?nodeId=s1",
         "mimeType": "application/x-directory", "fileSize": 0},
        {"nodeId": "s2", "title": "Elektromagnetische Wellen", "nodeType": "collection"},
    ]},
    "topicPages": {"total": 2, "count": 2, "results": [
        {"nodeId": _OPTIK, "title": "Optik", "nodeType": "collection",
         "description": "Die Lehre vom Licht.",
         "keywords": ["Linse", "Auge"], "disciplines": ["Physik"],
         "educationalContexts": ["Sekundarstufe I"],
         "topicPageUrl": f"https://repo/topic-pages?collectionId={_OPTIK}",
         "compendiumText": "# Optik\n" + "Kompendialer Text. " * 1000},
        {"nodeId": "tp2", "title": "Wellenoptik", "nodeType": "collection"},
    ]},
})

#: Was ``collect_cards`` aus ``_KOMBI`` macht (Reihenfolge: content, collections,
#: topicPages) — ``node_type`` ist dort noch das rohe Server-Feld.
_KOMBI_KARTEN = [
    {"node_type": "content"}, {"node_type": "content"},
    {"node_type": "collection"}, {"node_type": "collection"},
    {"node_type": "collection", "topic_page_url": "https://repo/tp/1"},
    {"node_type": "collection", "topic_page_url": "https://repo/tp/2"},
]


def _kombi_json(out: str) -> dict:
    """Der JSON-Kopf des redigierten Texts — der Einzelinhalt-Satz haengt hinten."""
    return json.loads(out.split("\n\nOK -")[0])


def test_die_vorlage_bildet_den_befund_ab():
    # Vorbedingung der Tests darunter: ohne sie liefe der Deckel ins Leere und
    # sie bestuenden aus dem falschen Grund.
    assert _OPTIK not in _KOMBI[:4000]


def test_kombi_suche_zeigt_jede_sammlung_und_jede_themenseite():
    # Der Kern: KEINE Node-ID der sichtbaren Toepfe darf verloren gehen, sonst
    # kann das Modell sie nicht waehlen.
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, True)
    for node_id in ("s1", "s2", _OPTIK, "tp2"):
        assert node_id in out


def test_kombi_suche_laesst_das_kompendium_weg():
    # Es macht die Antwort erst gross (68 der 87 KB im gemessenen Zug) und wird
    # bei Bedarf einzeln nachgeladen.
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, True)
    assert "Kompendialer Text" not in out
    assert len(out) < 4000


def test_kombi_suche_behaelt_genau_die_sechs_felder():
    # Titel, Beschreibung, Keywords, Fach, Bildungsstufe — und die ID, ohne die
    # der Rest nutzlos waere. Alles andere (Vorschaubild, MIME, Groesse) traegt
    # zur Auswahl nichts bei und kostet nur Kontext.
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, True)
    assert _kombi_json(out)["collections"]["results"][0] == {
        "nodeId": "s1",
        "title": "Geometrische Optik",
        "description": "Strahlenoptik fuer die Sek I.",
        "keywords": ["Licht", "Schatten"],
        "disciplines": ["Physik"],
        "educationalContexts": ["Sekundarstufe I"],
    }


def test_kombi_suche_deckelt_die_beschreibung():
    # Review-Befund 2026-08-16: der alte Pfad hatte mit ``raw_text[:4000]`` eine
    # harte Obergrenze, der neue gar keine — und ``maxCollections`` ist dem
    # Modell als freier Integer angeboten (Server-Maximum 20, also bis zu 40
    # Eintraege). Gemessen liefen Beschreibungen bis 1802 Zeichen. Die ID darf
    # NIE wegfallen, die Beschreibung darf gekuerzt werden.
    lang = json.dumps({
        "query": "x",
        "collections": {"total": 1, "count": 1, "results": [
            {"nodeId": "s1", "title": "Lang", "description": "A" * 5000},
        ]},
    })
    out = _redact_search_content_for_llm("search_wlo_all", lang, _KOMBI_KARTEN, True)
    beschreibung = _kombi_json(out)["collections"]["results"][0]["description"]
    assert len(beschreibung) <= 601          # Deckel + Auslassungszeichen
    assert beschreibung.endswith("…")        # das Kuerzen ist sichtbar
    assert "s1" in out


def test_kombi_suche_laesst_kurze_beschreibungen_ganz():
    # Gegenprobe: die gemessenen Sammlungs-Beschreibungen (441/422 Zeichen)
    # muessen vollstaendig durchgehen, sonst kuerzt der Deckel den Normalfall.
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, True)
    assert (_kombi_json(out)["collections"]["results"][0]["description"]
            == "Strahlenoptik fuer die Sek I.")


def test_kombi_suche_ohne_query_nennt_kein_leeres_feld():
    ohne = json.dumps({"collections": {"total": 0, "count": 0, "results": []}})
    out = _redact_search_content_for_llm("search_wlo_all", ohne, _KOMBI_KARTEN, True)
    assert "query" not in _kombi_json(out)


def test_kombi_suche_behaelt_die_trefferzahlen():
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, True)
    gezeigt = _kombi_json(out)
    assert gezeigt["collections"]["total"] == 2
    assert gezeigt["topicPages"]["total"] == 2
    assert gezeigt["query"] == "Optik"


def test_kombi_suche_haelt_die_einzelinhalte_zurueck():
    # Der Kasten-Modus zeigt sie nicht — also darf das Modell sie auch nicht
    # nennen. Genau dieser Leak lief hier bisher offen: der 4000-Zeichen-Deckel
    # liess NUR den content-Topf durch.
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, True)
    assert "Grundwissen Physik" not in out
    assert "Unterrichtsreihe" not in out
    assert "2 Einzelinhalte" in out
    assert "NICHT im Antwort-Text" in out


def test_kombi_suche_ueberlebt_den_angehaengten_prosablock():
    # Der MCP haengt seit dem Skill-Umbau die Freigabeliste als ZWEITEN
    # content-Block an; unser Client fuegt beide zu einem Text zusammen. Ein
    # blankes ``json.loads`` scheitert daran — und damit an genau den
    # Antworten, um die es hier geht (Sammlungstreffer).
    roh = _KOMBI + "\n\n[SKILL-REGISTRY — mitgeliefert von diesem Werkzeug]\nSkill-Registry: …"
    out = _redact_search_content_for_llm("search_wlo_all", roh, _KOMBI_KARTEN, True)
    assert _OPTIK in out


def test_kombi_suche_ohne_lesbares_envelope_faellt_auf_den_schnitt_zurueck():
    # Fehlertext statt Nutzlast: lieber der alte Deckel als gar nichts.
    roh = "Fehler: " + "X" * 5000
    out = _redact_search_content_for_llm("search_wlo_all", roh, _KOMBI_KARTEN, True)
    assert out == roh[:4000]


def test_kombi_suche_greift_auch_ohne_geparste_karten():
    # Der Kartenwaechter steht seit 2026-08-16 HINTER der Kombi-Verzweigung.
    # Das ist kein Randfall: die Prefetch-Einspeisung reichte bis zum selben Tag
    # eine leere Liste herein (siehe test_tool_loop). Vorher lief dann der
    # blinde Deckel — und ``test_die_vorlage_bildet_den_befund_ab`` belegt, dass
    # die Optik-ID darin nicht vorkommt. Ohne Einzelinhalte kein Ansage-Satz.
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, [], True)
    assert _OPTIK in out
    assert "Einzelinhalte" not in out


def test_kombi_suche_markiert_wo_ein_kompendium_liegt():
    # Der Kompendiumstext selbst bleibt draussen, aber das Modell muss WISSEN,
    # dass es zu dieser Sammlung einen gibt — sonst hat ``get_compendium_text``
    # keinen Ausloeser mehr (vorher war der gekuerzte Auszug im Ergebnis der
    # Anlass, den gibt es jetzt nicht mehr).
    ergebnisse = _kombi_json(
        _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, True)
    )["topicPages"]["results"]
    mit, ohne = ergebnisse[0], ergebnisse[1]
    assert mit["nodeId"] == _OPTIK
    assert mit["hasCompendium"] is True
    assert "hasCompendium" not in ohne     # kein Merker, wo nichts liegt


# ── Flachkarten-Modus: dieselbe Redaktion, aber ohne Zurueckhalten ────────
# Dort SIEHT der Nutzer die Einzelinhalte — was im Kasten-Modus richtig ist
# (den content-Topf ersetzen), waere hier eine Luege. Der 4000-Zeichen-Deckel
# war aber in BEIDEN Modi blind: gemessen 4 von 41 Node-IDs.

def test_flachmodus_zeigt_alle_drei_toepfe():
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, False)
    gezeigt = _kombi_json(out)
    assert [r["nodeId"] for r in gezeigt["content"]["results"]] == ["c1", "c2"]
    assert _OPTIK in out
    assert "s1" in out


def test_flachmodus_haelt_nichts_zurueck():
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, False)
    assert "NICHT im Antwort-Text" not in out
    assert "Grundwissen Physik" in out     # der Titel ist sichtbar, also nennbar


def test_flachmodus_nennt_den_materialtyp():
    # Im Flachmodus waehlt das Modell auch Einzelinhalte aus; ohne den Typ
    # koennte es „hast du Videos?" nicht bedienen.
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, False)
    erster = _kombi_json(out)["content"]["results"][0]
    assert erster["learningResourceTypes"] == ["Arbeitsblatt"]


def test_flachmodus_kuerzt_genauso():
    # Kein Kompendium, gedeckelte Beschreibung — der Umfang darf nicht davon
    # abhaengen, welcher Modus laeuft.
    out = _redact_search_content_for_llm("search_wlo_all", _KOMBI, _KOMBI_KARTEN, False)
    assert "Kompendialer Text" not in out
    assert len(_kombi_json(out)["content"]["results"][0]["description"]) <= 601


# ════════════════════════════════════════════════════════════════════════
# Der Skill-Katalog wird strukturell gekürzt, nicht abgeschnitten (2026-08-16)
#
# WURZEL des gemeldeten Fehlers, gemessen am echten Server: die Antwort von
# ``get_skill_registry`` ist 32 855 Zeichen lang, ``_ROH_DECKEL`` schneidet bei
# 4 000 ab — das Modell sieht 12 %. Der gesuchte Eintrag „Stunde planen" steht
# an Zeichen 13 091, seine nodeId ebenso. Beides ist unerreichbar.
#
# Daher die Live-Beobachtung, die wie Modell-Laune aussah: get_skill wurde mit
# erfundenen IDs gerufen (``e6bcb2e0…``, ``7f2c8b94…``, sogar ``'???'``) und
# lieferte je 67–100 Zeichen Fehlertext. Das Modell hat nicht geschludert; es
# hatte keine einzige gültige ID vor sich.
#
# Der Deckel-Kommentar sagt selbst, was hier fehlte: „Wo die Antwortform
# bekannt ist, wird sie strukturell gekürzt statt abgeschnitten." Für diese
# Antwortform war sie bekannt und wurde trotzdem abgeschnitten.
# ════════════════════════════════════════════════════════════════════════

def _registry_antwort(n: int = 28) -> str:
    """Die echte Form (gemessen 2026-08-16): ein langes ``markdown``-Feld VOR
    den ``entries`` — deshalb fällt beim blinden Abschneiden zuerst die
    maschinenlesbare Liste weg, also genau das, was gebraucht wird."""
    eintraege = [
        {"nodeId": f"{i:08x}-0000-4000-8000-000000000000",
         "title": f"Anleitung Nummer {i}",
         "description": "Beschreibung " * 12,
         "keywords": ["stichwort"] * 8}
        for i in range(n - 1)
    ]
    eintraege.append({
        "nodeId": "5b29f470-4417-49bb-a9f4-70441739bb3a",
        "title": "Stunde planen",
        "description": "Plant eine konkrete Einzel- oder Doppelstunde.",
        "keywords": ["stunde-planen", "Stundenentwurf für die 8b"],
    })
    return json.dumps({"registry": {
        "collectionId": "9e7ae956-e9df-430f-bace-f3db4b910013",
        "registryNodeId": "d84d54c4-f473-4e4b-8d54-c4f4738e4b87",
        "registryTitle": "Skillkatalog Physik Optik",
        "markdown": "# Skillkatalog\n\n" + ("Fließtext " * 1800),
        "entries": eintraege,
    }})


def test_der_letzte_katalog_eintrag_ueberlebt_die_kuerzung():
    """Der Kern: der gesuchte Eintrag steht hinten, und hinten wurde gekappt."""
    roh = _registry_antwort()
    sichtbar = _redact_search_content_for_llm("get_skill_registry", roh, [], False)

    assert "Stunde planen" in sichtbar, (
        "Der letzte Eintrag fehlt — genau der Fall aus dem Befund: das Modell "
        "kann ihn nicht waehlen, weil er nicht ankommt.")
    assert "5b29f470-4417-49bb-a9f4-70441739bb3a" in sichtbar, (
        "Seine nodeId fehlt — ohne sie kann get_skill nicht gerufen werden, und "
        "das Modell erfindet eine.")


def test_alle_node_ids_kommen_an():
    """Nicht nur der letzte: die Auswahl trifft das Modell, also braucht es
    jede ID. Eine Teilliste hiesse, ihm die Wahl vorwegzunehmen."""
    roh = _registry_antwort()
    sichtbar = _redact_search_content_for_llm("get_skill_registry", roh, [], False)
    fehlend = [f"{i:08x}-0000-4000-8000-000000000000" for i in range(27)
               if f"{i:08x}-0000-4000-8000-000000000000" not in sichtbar]
    assert not fehlend, f"{len(fehlend)} von 28 nodeIds fehlen, z.B. {fehlend[:2]}"


def test_der_katalog_wird_dabei_deutlich_kleiner():
    """Die Kürzung ersetzt den Deckel, sie hebt ihn nicht auf. Das doppelte
    ``markdown``-Feld traegt dieselben 28 Skills ein zweites Mal als Fliesstext
    — es faellt weg, die Liste bleibt."""
    roh = _registry_antwort()
    sichtbar = _redact_search_content_for_llm("get_skill_registry", roh, [], False)
    assert len(sichtbar) < len(roh) / 2, (
        f"{len(sichtbar)} von {len(roh)} Zeichen — die Kuerzung greift nicht.")


def test_auch_die_markdown_form_wird_gelesen():
    """Der Live-Pfad. Die Schema-Vorgabe des Werkzeugs ist ``markdown`` und das
    ist eine Entscheidung (``SkillRegistryArgs``: der Agent-Vorabruf legt den
    Registry-Text mit den Verwendungshinweisen dem Modell vor) — das Modell ruft
    also OHNE ``outputFormat`` und bekommt Markdown.

    Dieser Test kam nach der Messung, nicht davor: die JSON-Tests oben waren
    gruen, waehrend am echten Server nichts ankam. Erst der Abgleich mit dem
    Server zeigte, dass die gemessene Antwortform eine andere war.

    Gekoppelt an die Feldmarken ``### `` und ``nodeId:``, nicht an deutschen
    Fliesstext — ohne sie faellt der Aufrufer auf den blinden Deckel zurueck.
    """
    md = (
        "# Skillkatalog Physik Optik\n"
        "Registry-Dokument: d84d54c4 — Sammlung: 9e7ae956\n\n"
        "## Freigegebene Skills (2)\n\n"
        "### Dokumentieren\n"
        "nodeId: d2dbdbf9-99b8-4d01-9bdb-f999b85d011a\n"
        "Haelt schulische Vorgaenge fest.\n"
        "Keywords: dokumentieren, Aktenvermerk\n\n"
        "### Stunde planen\n"
        "nodeId: 5b29f470-4417-49bb-a9f4-70441739bb3a\n"
        "Plant eine konkrete Einzel- oder Doppelstunde.\n"
        "Keywords: stunde-planen, Stundenentwurf fuer die 8b\n"
    )
    sichtbar = _redact_search_content_for_llm("get_skill_registry", md, [], False)
    assert "5b29f470-4417-49bb-a9f4-70441739bb3a" in sichtbar
    assert "Stunde planen" in sichtbar
    assert "d2dbdbf9-99b8-4d01-9bdb-f999b85d011a" in sichtbar
    # Keywords gehoeren nicht in die Auswahlliste: sie machen sie lang, ohne die
    # Wahl zu verbessern — der Titel plus der Zweck reichen dafuer.
    assert "Keywords:" not in sichtbar


def test_ohne_erkennbare_feldmarken_bleibt_der_blinde_deckel():
    """Ein Fremdformat darf nicht als leerer Katalog durchgehen — dann stuende
    dort ``Freigegebene Anleitungen: 0`` und das Modell hielte die Sammlung fuer
    leer. Lieber der alte Deckel."""
    fremd = "Serverfehler: registry temporarily unavailable. " * 200
    sichtbar = _redact_search_content_for_llm("get_skill_registry", fremd, [], False)
    assert sichtbar == fremd[:4000]
