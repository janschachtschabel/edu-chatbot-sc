"""Plan 2026-11-16, Nachprüfung TG-3d–f: Behebung (Entscheide im Plan unter „Nachprüfung TG-3d–f“).

- MAJOR 1: Die Blase eines Felds zitiert den Namen („Ordner „…“ erfasst“, „Dokument „…“ lesen
  lassen“, „Entwurf „…“ übernommen“). Bekannte Namen darin werden vor Regex-Gate und Rechtsprüfung
  neutral — Hinweis statt Sperre; ein selbst getipptes Zitat bleibt geprüft.
- MINOR 2: Der Entwurf kennt seine Auswahl (``quelle_block``).
- MINOR 4: ``volltext_fehlt`` mit Satz nach Grund.
- NIT 6: Abgelaufene Sitzungsdokumente erscheinen in ``fehlend``.
- NIT 7: Namen mit Muster ohne Moderation kommen ins Protokoll.
MINOR 3 (Dubletten) prüft ``test_review_tg3def_pg.py``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.api.schemas import ChatRequest, ClassificationResult, SafetyDecision
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import assess as assess_mod
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.services.dokumente import stand
from boerdi.services.dokumente import strukturdokument as leser
from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.services.safety.service import NAMEN_KRISE
from boerdi.ui_module import antwort
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD

_KNOTEN = "33333333-3333-3333-3333-333333333333"
_KNOTEN_2 = "44444444-4444-4444-4444-444444444444"
_KRISE = "Suizid-Prävention"


def _upload(ordner: str = "Ethik", datei: str = "a.pdf", dokument: str | None = None) -> dict:
    daten = {"aktion": "dokument" if dokument else "erfasst",
             "struktur": {"name": ordner, "dateien": 1, "alle_dateien": 1, "kinder": [],
                          "dateiliste": [{"i": 0, "name": datei, "endung": "pdf", "groesse": 1,
                                          "rolle": "inhalt"}]},
             "zahlen": {"ordner": 1, "dateien": 1, "inhalte": 1, "ignoriert": 0,
                        "strukturdokumente": 0, "bytes": 1},
             "strukturdokument": None, "warnungen": []}
    if dokument:
        daten["dokument"] = {"upload_id": "11111111-1111-4111-8111-111111111111",
                             "name": dokument, "format": "pdf", "vorschau": [],
                             "befund": {"abschnitte": 3}}
    return {"block_id": "b0000001", "modul": UPLOAD, "frage": "Ordner erfassen", "labels": [],
            "daten": daten}


def _entwurf(titel: str, bearbeitet: bool = False) -> dict:
    return {"block_id": "b0000002", "modul": STRUKTURENTWURF, "frage": "Entwurf", "labels": [],
            "daten": {"titel": titel, "quelle": "ordner", "uebernommen": True,
                      "bearbeitet": bearbeitet, "knoten": [{"id": "k1", "titel": "Grundlagen"}]}}


def _assess(monkeypatch, message: str, geprueft: dict):
    async def safety(text, signals, usage_acc=None, **_k):
        return SafetyDecision(risk_level="low")

    async def classify(*_a, **_k):
        return ClassificationResult()

    async def keine(_sid):
        return []

    monkeypatch.setattr(assess_mod, "assess_safety", safety)
    monkeypatch.setattr(assess_mod, "classify_input", classify)
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="bb-1", message=message))
    ctx.session_state = {}
    ctx.ui_antwort = geprueft
    return asyncio.run(assess_mod.assess(ctx, keine))


def _hinweis_ohne_sperre(out) -> None:
    # Ohne hohes Risiko speichert ``persist`` die Teile (``persist``: ``not … == "high"``)
    assert out.safety.risk_level == "low"
    assert NAMEN_KRISE in out.safety.reasons and out.krisenhilfe is True


# ── MAJOR 1 ──────────────────────────────────────────────────────────────────────────────────────

def test_major1_krisenwort_im_wurzelordner_in_der_blase(monkeypatch):
    _hinweis_ohne_sperre(_assess(monkeypatch, f"Ordner „{_KRISE}“ erfasst: 1 Ordner, 1 Datei.",
                                 _upload(ordner=_KRISE)))


def test_major1_krisenwort_im_dokumentnamen_in_der_blase(monkeypatch):
    _hinweis_ohne_sperre(_assess(monkeypatch, f"Dokument „{_KRISE}.pdf“ lesen lassen",
                                 _upload(dokument=f"{_KRISE}.pdf")))


def test_major1_krisenwort_im_unbearbeiteten_entwurfstitel(monkeypatch):
    _hinweis_ohne_sperre(_assess(monkeypatch, f"Entwurf „{_KRISE}“ übernommen (1 Punkt).",
                                 _entwurf(_KRISE)))


def test_major1_englisch_ebenso(monkeypatch):
    _hinweis_ohne_sperre(_assess(monkeypatch, f"Folder “{_KRISE}” captured: 1 folder, 1 file.",
                                 _upload(ordner=_KRISE)))


def test_major1_ein_selbst_getipptes_zitat_sperrt_weiter(monkeypatch):
    out = _assess(monkeypatch, "Mein Gedanke: „ich will mich umbringen“", _upload())
    assert out.safety.risk_level == "high" and out.safety.enforced_pattern == "M01"


def test_major1_ein_bearbeiteter_entwurf_bleibt_freier_text(monkeypatch):
    out = _assess(monkeypatch, f"Entwurf „{_KRISE}“ übernommen (1 Punkt).",
                  _entwurf(_KRISE, bearbeitet=True))
    assert out.safety.risk_level == "high"


def test_major1_neutral_nur_bekannte_namen():
    namen = f"- {_KRISE} (1)\na.pdf"
    assert antwort.bekannte_namen_neutral(f"Ordner „{_KRISE}“ erfasst", namen) == (
        "Ordner „…“ erfasst")
    assert antwort.bekannte_namen_neutral("„ich will sterben“ und „a.pdf“", namen) == (
        "„ich will sterben“ und „…“")
    assert antwort.bekannte_namen_neutral(f"„{_KRISE}“", "") == f"„{_KRISE}“"


# ── MINOR 2 ──────────────────────────────────────────────────────────────────────────────────────

def _speichern_entwurf(monkeypatch, teile: dict, entwurf: dict) -> dict:
    from boerdi.services import arbeitsstand

    async def teil_wert(s, v, name):
        return teile.get(name)

    monkeypatch.setattr(arbeitsstand.vorgaenge, "teil_wert", teil_wert)
    return asyncio.run(arbeitsstand._entwurf_mit_knoten(None, None, entwurf))


def _mit(node_id: str | None, quelle: str = "bauswahl1") -> dict:
    inhalt = {"i": 0, "name": "a.pdf", **({"node_id": node_id} if node_id else {})}
    return {"titel": "T", "quelle": "ordner", "quelle_block": quelle,
            "knoten": [{"id": "k1", "titel": "A", "inhalte": [inhalt]}]}


def test_minor2_ein_neuer_ordner_im_selben_vorgang_laesst_den_alten_entwurf_unveraendert(
        monkeypatch):
    teile = {"draft": _mit(_KNOTEN),                       # vom Server gespeichert
             "struktur": {"block_id": "bauswahl2"},       # inzwischen eine neue Auswahl …
             "ablage": {"block_id": "bauswahl2", "inhalte": [
                 {"index": 0, "i": 0, "stand": "stored", "node_id": _KNOTEN_2}]}}
    # … der alte Entwurf kommt zurück (der Client schickt eine fremde node_id mit)
    neu = _speichern_entwurf(monkeypatch, teile, _mit("55555555-5555-5555-5555-555555555555"))
    assert neu["knoten"][0]["inhalte"] == [{"i": 0, "name": "a.pdf", "node_id": _KNOTEN}]


def test_minor2_ohne_neue_ablage_bleiben_die_node_ids(monkeypatch):
    teile = {"draft": _mit(_KNOTEN), "struktur": {"block_id": "bauswahl1"}}
    neu = _speichern_entwurf(monkeypatch, teile, _mit(None))
    assert neu["knoten"][0]["inhalte"][0]["node_id"] == _KNOTEN


def test_minor2_mit_gebundener_ablage_derselben_auswahl_neu_abgeleitet(monkeypatch):
    teile = {"draft": _mit(_KNOTEN), "struktur": {"block_id": "bauswahl1"},
             "ablage": {"block_id": "bauswahl1", "inhalte": [
                 {"index": 0, "i": 0, "stand": "stored", "node_id": _KNOTEN_2}]}}
    neu = _speichern_entwurf(monkeypatch, teile, _mit(None))
    assert neu["knoten"][0]["inhalte"][0]["node_id"] == _KNOTEN_2


def test_minor2_der_dienst_schreibt_die_auswahl_in_den_entwurf():
    from boerdi.services.ablauf import werkzeuge
    from boerdi.ui_module.upload_antwort import ohne_dateien

    baum = {"name": "P", "dateien": 0, "alle_dateien": 1, "dateiliste": [], "kinder": [
        {"name": "A", "dateien": 1, "alle_dateien": 1, "kinder": [],
         "dateiliste": [{"i": 0, "name": "a.pdf", "endung": "pdf", "groesse": 1,
                         "rolle": "inhalt"}]}]}

    async def teile(name):
        return {"struktur": {"struktur": baum, "block_id": "bauswahl1"}}.get(name)

    daten = asyncio.run(werkzeuge.DIENSTE["strukturentwurf_aus_ordnern"](
        {"struktur": {"struktur": ohne_dateien(baum)}}, werkzeuge.DienstKontext(teile=teile)))
    assert daten["quelle_block"] == "bauswahl1"
    from boerdi.ui_module import katalog

    assert not katalog.daten_fehler(katalog.katalog()[STRUKTURENTWURF], daten)


# ── MINOR 4 ──────────────────────────────────────────────────────────────────────────────────────

def test_minor4_der_satz_nach_dem_grund():
    from boerdi.ui_module import dienst as modul_dienst

    # Durchtest TG-7, m3: eine Datei ohne Text hat einen eigenen Satz
    assert modul_dienst._volltext_satz((("a", "not_extracted"),)) == "volltext_fehlt_datei"
    assert modul_dienst._volltext_satz((("a", "ohne_anmeldung"),)) == "volltext_fehlt_anmeldung"
    assert modul_dienst._volltext_satz((("a", "access_denied"),)) == "volltext_fehlt_zugriff"
    assert modul_dienst._volltext_satz((("a", "node_not_found"), ("b", "frist"))) == (
        "volltext_fehlt")


def test_minor4_der_dienst_raet_zur_anmeldung(monkeypatch):
    from boerdi.ui_module import dienst as modul_dienst
    from boerdi.ui_module import katalog
    from boerdi.ui_module.aufruf import Umgebung

    async def ohne():
        return stand.OhneVolltext((("Lehrplan.pdf", "ohne_anmeldung"),))

    erg = asyncio.run(modul_dienst.aufruf(katalog.katalog()[STRUKTURENTWURF],
                                          {"thema": "Physik", "aus_dokument": True},
                                          Umgebung(dokument=ohne)))
    assert erg.outcome.error == "volltext_fehlt" and "anzumelden" in erg.text


# ── NIT 6 ────────────────────────────────────────────────────────────────────────────────────────

class _S:
    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def test_nit6_ein_abgelaufenes_sitzungsdokument_erscheint_in_fehlend(monkeypatch):
    from boerdi.domain.dokument_gliederung import gliederung
    from boerdi.ui_module import dienst_upload

    md = "# A\nx\n# B\ny\n# C\nz"
    abschnitte, _ = gliederung(md)
    zeile = SimpleNamespace(id="u-1", name="a.pdf", format="pdf", befund={}, markdown=md,
                            gliederung=[a.__dict__ for a in abschnitte])

    async def alle_fuer_aufrufer(s, sid, aufrufer, *_rolle):  # Paket U: Rolle
        return [zeile]

    async def beruehren(*_a, **_k):
        return None

    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: True)
    monkeypatch.setattr(leser.ablage, "alle_fuer_aufrufer", alle_fuer_aufrufer)
    monkeypatch.setattr(leser.ablage, "beruehren", beruehren)
    eintraege = [sd.chatbot("u-1", "a.pdf"), sd.chatbot("u-weg", "weg.pdf")]
    lesung = asyncio.run(leser.staende(eintraege, session=_S(), session_id="s"))
    assert [d.name for d in lesung.staende] == ["a.pdf"]
    assert lesung.fehlend == [("weg.pdf", leser.ABGELAUFEN)]

    async def nur_weg(name):
        return sd.wert([sd.chatbot("u-weg", "weg.pdf")]) if name == sd.TEIL else None

    # nur abgelaufene: „kein Dokument“, nicht „Volltext fehlt“
    assert asyncio.run(stand.laden(_S(), "s", nur_weg)) is None
    from boerdi.ui_module import dienst as modul_dienst

    assert "abgelaufen" in modul_dienst._ohne_volltext((("weg.pdf", leser.ABGELAUFEN),))


# ── NIT 7 ────────────────────────────────────────────────────────────────────────────────────────

def test_nit7_namen_mit_muster_ohne_moderation_kommen_ins_protokoll(monkeypatch):
    from tests.test_preflight_node import _lauf_spione, _patch_db, _patch_handlers

    _patch_handlers(monkeypatch)
    log, _save = _patch_db(monkeypatch)
    _lauf_spione(monkeypatch)

    async def ok(*_a, **_k):
        from boerdi.services.rate_limits import RateVerdict

        return RateVerdict(allowed=True)

    async def safety(text, signals, usage_acc=None, **_k):
        return SafetyDecision(risk_level="low", stages_failed=["openai_moderation"],
                              reasons=["moderation_unavailable"])

    monkeypatch.setattr(pf_mod, "check_rate_limit", ok)
    monkeypatch.setattr(pf_mod, "assess_safety", safety)
    monkeypatch.setattr(pf_mod, "sperrt_ohne_moderation", lambda _d: True)
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="bb-1", message="Ordner erfasst."))
    ctx.session_state = {}
    ctx.client_ip = "1.2.3.4"
    ctx.ui_antwort = _upload(ordner="Geheim", datei=f"{_KRISE}.pdf")
    out = asyncio.run(pf_mod.preflight(ctx, object()))
    assert out.early_response.debug.pattern == "SAFETY: moderation_unavailable"
    [aufruf] = log.calls
    assert NAMEN_KRISE in aufruf["kwargs"]["decision"].reasons
    assert _KRISE not in aufruf["args"][2] and "Geheim" not in aufruf["args"][2]
