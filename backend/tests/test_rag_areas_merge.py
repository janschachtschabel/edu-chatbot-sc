"""Die zwei Bereichs-Listen zusammenfuehren (Paket R).

**Der Befund** (gemessen 2026-08-18): es gibt zwei Listen von Wissensbereichen,
und sie koennen still auseinanderlaufen.

* ``services/rag/admin.list_areas`` gruppiert ueber ``RagChunk.area`` — was in
  der **Datenbank** liegt. Daraus speist sich die Wissen-Seite im Studio.
* ``config_loader.load_rag_config`` behaelt nur Eintraege MIT ``mode`` — was in
  der **Konfiguration** steht. Daraus speist sich, was der Chatbot durchsucht.

Wer im Studio beim Einlesen einen neuen Bereichsnamen tippt, legt ihn nur in der
Datenbank an. Der Chatbot durchsucht ihn nie, und nichts sagt es — das ist die
teuerste Sorte Fehler, weil sie wie ein Bedienfehler aussieht.
Umgekehrt steht ein konfigurierter Bereich ohne Dokumente in der
Werkzeug-Beschreibung und ist bei jeder Suche leer.
"""

from boerdi.domain.rag_areas import zusammenfuehren

_DB = [
    {"area": "FAQ", "chunks": 12, "documents": 2},
    {"area": "Neu-Getippt", "chunks": 3, "documents": 1},
]
_CONFIG = {
    "FAQ": {"mode": "always"},
    "Nur-Konfiguriert": {"mode": "always"},
}


def test_beide_seiten_kommen_vor():
    namen = [z["area"] for z in zusammenfuehren(_DB, _CONFIG)]
    assert namen == ["FAQ", "Neu-Getippt", "Nur-Konfiguriert"]


def test_der_gepflegte_bereich_ist_beides():
    faq = zusammenfuehren(_DB, _CONFIG)[0]
    assert faq == {"area": "FAQ", "chunks": 12, "documents": 2, "configured": True}


def test_nur_eingelesen_heisst_der_chatbot_nutzt_ihn_nicht():
    neu = zusammenfuehren(_DB, _CONFIG)[1]
    assert neu["configured"] is False
    assert neu["chunks"] == 3


def test_nur_konfiguriert_heisst_leer_aber_angekuendigt():
    leer = zusammenfuehren(_DB, _CONFIG)[2]
    assert leer == {"area": "Nur-Konfiguriert", "chunks": 0,
                    "documents": 0, "configured": True}


def test_ohne_konfiguration_ist_nichts_gepflegt():
    assert [z["configured"] for z in zusammenfuehren(_DB, {})] == [False, False]


def test_ohne_dokumente_bleibt_die_konfiguration_sichtbar():
    assert zusammenfuehren([], _CONFIG) == [
        {"area": "FAQ", "chunks": 0, "documents": 0, "configured": True},
        {"area": "Nur-Konfiguriert", "chunks": 0, "documents": 0, "configured": True},
    ]


def test_leer_bleibt_leer():
    assert zusammenfuehren([], {}) == []
