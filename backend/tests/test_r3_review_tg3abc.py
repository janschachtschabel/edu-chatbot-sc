"""Plan 2026-11-16, Review TG-3a–c (Entscheide im Plan „Review TG-3a–c (16.11.)“).

- R3-1: Ordner- und Dateinamen gehen nur an die Moderation, nicht an die Krisen- und
  Drohungsmuster; keine Namen ins Sicherheitsprotokoll.
- R3-2: ``struktur`` trägt die ``block_id`` der Auswahl; ``struktur`` und ``ablage`` werden nur bei
  gleicher ``block_id`` verknüpft; ``grund`` prüft ``i < zahlen.dateien``.
- R3-3: ``struktur`` ist von der Pauschalfreigabe bestätigbarer Werkzeuge ausgenommen.
- R3-4: ausgeschlossene Dateien gehen ohne Namen mit.
- R3-5: ``verwirft`` koppelt Alias-Paare.
- Testlücken: großer Teil ``struktur`` (Ablage, ``BEREITSTELLUNG``, ``$teil`` über 64 KB), Name nur
  aus Leerzeichen.
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest, ClassificationResult, SafetyDecision
from boerdi.api.schemas_ui import UiAntwort, UiBlock
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import assess as assess_mod
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.services.safety import service as safety_service
from boerdi.ui_module import antwort
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD

_KRISE_DATEI = "Suizid-Prävention.pdf"


def _datei(i: int, name: str, rolle: str = "inhalt") -> dict:
    return {"i": i, "name": name, "endung": "pdf", "groesse": 10, "rolle": rolle}


def _upload_daten(ordner: str = "Ethik", datei: str = _KRISE_DATEI) -> dict:
    return {"aktion": "erfasst",
            "struktur": {"name": ordner, "dateien": 1, "alle_dateien": 1, "kinder": [],
                         "dateiliste": [_datei(0, datei)]},
            "zahlen": {"ordner": 1, "dateien": 1, "inhalte": 1, "ignoriert": 0,
                       "strukturdokumente": 0, "bytes": 10},
            "strukturdokument": None, "warnungen": []}


def _geprueft(daten: dict, modul: str = UPLOAD) -> dict:
    return {"block_id": "b0000001", "modul": modul, "frage": "Ordner erfassen", "labels": [],
            "daten": daten}


# ── R3-1 ─────────────────────────────────────────────────────────────────────────────────────────

def test_r31_namen_stehen_getrennt_vom_freien_text():
    teile = antwort.sicherheits_teile("Hier mein Ordner", _geprueft(_upload_daten()))
    assert teile.frei == "Hier mein Ordner"
    assert _KRISE_DATEI in teile.namen and "Ethik" in teile.namen
    assert teile.alles.endswith("Hier mein Ordner") and _KRISE_DATEI in teile.alles


def test_r31_ohne_auswahl_bleibt_alles_freier_text():
    teile = antwort.sicherheits_teile("Hallo", None)
    assert (teile.frei, teile.namen) == ("Hallo", "")


def test_r31_ein_bearbeiteter_entwurf_bleibt_freier_text_ein_unbearbeiteter_nicht():
    """Titel, die die Person bearbeitet hat, können ihr eigener Satz sein — dann alle Stufen; ein
    unbearbeiteter Entwurf trägt nur Titel aus Ordnern, WLO oder der KI."""
    entwurf = {"titel": "Ethik", "quelle": "ordner", "uebernommen": True,
               "knoten": [{"id": "k1", "titel": "Suizid-Prävention"}]}
    bearbeitet = antwort.sicherheits_teile("x", _geprueft({**entwurf, "bearbeitet": True},
                                                          STRUKTURENTWURF))
    assert bearbeitet.namen == "" and "Suizid-Prävention" in bearbeitet.frei
    roh = antwort.sicherheits_teile("x", _geprueft({**entwurf, "bearbeitet": False},
                                                   STRUKTURENTWURF))
    assert roh.frei == "x" and "Suizid-Prävention" in roh.namen


def _ctx(message: str, geprueft: dict | None) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="bb-1", message=message))
    ctx.session_state = {}
    ctx.client_ip = "1.2.3.4"
    ctx.ui_antwort = geprueft
    return ctx


async def _keine_erinnerung(_sid):
    return []


def _assess(monkeypatch, message: str, geprueft: dict | None):
    gerufen: list = []

    async def safety(text, signals, usage_acc=None, **k):
        gerufen.append((text, k))
        return SafetyDecision(risk_level="low")

    async def classify(*_a, **_k):
        return ClassificationResult()

    monkeypatch.setattr(assess_mod, "assess_safety", safety)
    monkeypatch.setattr(assess_mod, "classify_input", classify)
    return asyncio.run(assess_mod.assess(_ctx(message, geprueft), _keine_erinnerung)), gerufen


def test_r31_suizid_praevention_als_datei_loest_keine_krisenantwort_aus(monkeypatch):
    out, gerufen = _assess(monkeypatch, "Ordner „Ethik“ erfasst: 1 Datei.",
                           _geprueft(_upload_daten()))
    assert out.safety.risk_level == "low"
    [(text, k)] = gerufen
    assert _KRISE_DATEI not in text and _KRISE_DATEI in k["nur_moderation"]


def test_r31_suizid_praevention_als_ordner_loest_keine_krisenantwort_aus(monkeypatch):
    out, gerufen = _assess(monkeypatch, "Ordner erfasst.",
                           _geprueft(_upload_daten(ordner="Suizid-Prävention", datei="a.pdf")))
    assert out.safety.risk_level == "low"
    assert "Suizid-Prävention" in gerufen[0][1]["nur_moderation"]


def test_r31_ein_krisensatz_in_der_nachricht_loest_sie_weiter_aus(monkeypatch):
    out, gerufen = _assess(monkeypatch, "ich will mich umbringen", _geprueft(_upload_daten()))
    assert out.safety.risk_level == "high" and out.safety.enforced_pattern == "M01"
    assert gerufen == []                         # Kurzschluss vor den LLM-Stufen


def test_r31_assess_safety_gibt_die_namen_nur_an_die_moderation(monkeypatch):
    gesehen: list[str] = []

    async def moderate(text, **_k):
        gesehen.append(text)
        return {"flagged": False, "categories": {}, "category_scores": {}}

    monkeypatch.setattr(safety_service.moderation, "moderate", moderate)
    monkeypatch.setattr(safety_service, "load_safety_config",
                        lambda: {"security_level": "standard", "presets": {"standard": {
                            "moderation": "always", "legal_classifier": "never",
                            "prompt_injection": True}}})
    entscheid = asyncio.run(safety_service.assess_safety(
        "Hier mein Ordner", nur_moderation=f"Ethik\n{_KRISE_DATEI}"))
    assert entscheid.risk_level != "high" and entscheid.enforced_pattern != "M01"
    assert gesehen and gesehen[0].startswith("Ethik") and gesehen[0].endswith("Hier mein Ordner")


def test_r31_im_protokoll_stehen_keine_namen(monkeypatch):
    """Ein Krisensatz neben einer Auswahl: Abweisung und Protokoll — ohne Datei- und Ordnernamen,
    auch nicht aus der Blase."""
    from tests.test_preflight_node import _lauf_spione, _patch_db, _patch_handlers

    _patch_handlers(monkeypatch)
    log, _save = _patch_db(monkeypatch)
    _lauf_spione(monkeypatch)
    monkeypatch.setattr(pf_mod, "check_rate_limit", _ok_rate)
    ctx = _ctx("Ordner „Geheim-Ethik“ erfasst — ich will mich umbringen",
               _geprueft(_upload_daten(ordner="Geheim-Ethik")))
    asyncio.run(pf_mod.preflight(ctx, object()))
    [aufruf] = log.calls
    protokoll = aufruf["args"][2]
    assert "umbringen" in protokoll
    assert _KRISE_DATEI not in protokoll and "Geheim-Ethik" not in protokoll


async def _ok_rate(*_a, **_k):
    from boerdi.services.rate_limits import RateVerdict

    return RateVerdict(allowed=True)


def test_r31_protokoll_text_ohne_auswahl_unveraendert():
    assert antwort.protokoll_text(antwort.PruefText(frei="„Zitat“ bleibt")) == "„Zitat“ bleibt"
    assert antwort.protokoll_text(antwort.PruefText(frei="Dokument „Lehr.pdf“ lesen lassen",
                                                    namen="Lehr.pdf")) == (
        "Dokument „…“ lesen lassen")


def _ui_antwort_ok(daten: dict) -> dict | None:
    block = UiBlock(block_id="b0000001", modul=UPLOAD, version=1, art="abfragen",
                    daten={"zweck": "bereitstellen"}, text="t", status="offen")
    entities: dict = {}
    antwort.merke_frage(entities, block)
    return antwort.antwort_pruefen(entities[antwort.OFFENE_FRAGE],
                                   UiAntwort(block_id="b0000001", daten=daten))


# ── R3-4: ausgeschlossene Dateien ohne Namen ────────────────────────────────────────────────────

def _mit_ignorierter(name: bool) -> dict:
    daten = _upload_daten(datei="a.pdf")
    ignoriert = {"i": 1, "endung": "tmp", "groesse": 3, "rolle": "ignorieren"}
    if name:
        ignoriert["name"] = "Zeugnis_Müller.tmp"
    daten["struktur"]["dateiliste"].append(ignoriert)
    daten["zahlen"] = {**daten["zahlen"], "dateien": 2, "ignoriert": 1}
    return daten


def test_r34_eine_ignorierte_datei_geht_ohne_namen():
    geprueft = _ui_antwort_ok(_mit_ignorierter(name=False))
    assert geprueft is not None
    [_inhalt, ignoriert] = geprueft["daten"]["struktur"]["dateiliste"]
    assert "name" not in ignoriert


def test_r34_ein_altes_buendel_mit_namen_verliert_ihn_vor_der_pruefung():
    from boerdi.services import arbeitsstand_teile

    geprueft = _ui_antwort_ok(_mit_ignorierter(name=True))
    assert geprueft is not None
    assert "Zeugnis_Müller" not in str(geprueft)
    teile = arbeitsstand_teile.teile_aus_antwort(geprueft)
    assert "Zeugnis_Müller" not in str(teile)


def test_r34_ein_name_an_einer_ignorierten_datei_verwirft_das_schema():
    from boerdi.ui_module import katalog

    manifest = katalog.katalog()[UPLOAD]
    assert katalog.antwort_fehler(manifest, _mit_ignorierter(name=True))
    assert not katalog.antwort_fehler(manifest, _mit_ignorierter(name=False))
    # ohne Rolle „ignorieren“ bleibt der Name Pflicht
    ohne = _upload_daten(datei="a.pdf")
    del ohne["struktur"]["dateiliste"][0]["name"]
    assert katalog.antwort_fehler(manifest, ohne)


# ── R3-2: Bindung über block_id, ``i`` innerhalb der Erfassung ───────────────────────────────────

def test_r32_struktur_traegt_die_block_id_der_auswahl():
    from boerdi.services import arbeitsstand_teile

    geprueft = _ui_antwort_ok(_upload_daten(datei="a.pdf"))
    teile = {t[0]: t for t in arbeitsstand_teile.teile_aus_antwort(geprueft)}
    assert teile["struktur"][2]["block_id"] == "b0000001"
    assert "block_id" not in teile["structure"][2]


def test_r32_gebunden_nur_bei_gleicher_block_id():
    from boerdi.services.arbeitsstand_teile import gebunden

    assert gebunden({"block_id": "b1"}, {"block_id": "b1"})
    assert not gebunden({"block_id": "b1"}, {"block_id": "b2"})
    assert not gebunden({}, {"block_id": "b1"})          # Stand vor R3-2: nicht verknüpft
    assert not gebunden({"block_id": "b1"}, None)


def test_r32_eine_nummer_ausserhalb_der_erfassung_wird_abgewiesen():
    daten = _upload_daten(datei="a.pdf")
    daten["struktur"]["dateiliste"][0]["i"] = 1          # zahlen.dateien ist 1
    assert _ui_antwort_ok(daten) is None


def test_r32_metadaten_tragen_die_block_id_der_ablage():
    from boerdi.services.ablauf import metadaten

    teil = metadaten._teil([], [], "b0000001")
    assert teil["block_id"] == "b0000001"
    assert "block_id" not in metadaten._teil([], [])


# ── R3-3: ``struktur`` nicht pauschal an kuratierende Werkzeuge ─────────────────────────────────

def test_r33_struktur_nur_ueber_liest():
    from boerdi.domain.write_confirm import CURATION_TOOLS
    from boerdi.services import teil_verweise

    schreibend = sorted(CURATION_TOOLS)[0]
    assert not teil_verweise.darf(schreibend, "struktur")
    assert teil_verweise.darf(schreibend, "structure")
    assert teil_verweise.darf(schreibend, "document")
    assert teil_verweise.darf(schreibend, "strukturdokument")
    # ein Modul, das ``struktur`` liest, bekommt sie
    assert teil_verweise.darf("ui_strukturentwurf", "struktur")


# ── R3-5: Alias-Paare in ``verwirft`` ───────────────────────────────────────────────────────────

def test_r35_alias_paare():
    from boerdi.services.ablauf import typen

    assert typen.mit_aliassen(["structure"]) == ["structure", "struktur"]
    assert typen.mit_aliassen(["struktur"]) == ["struktur", "structure"]
    assert typen.mit_aliassen(["document"]) == ["document", "strukturdokument"]
    assert typen.mit_aliassen(["structure", "struktur"]) == ["structure", "struktur"]
    assert typen.mit_aliassen(["draft"]) == ["draft"]


# ── Testlücke: großer Teil ``struktur`` ──────────────────────────────────────────────────────────

def _grosse_struktur(n: int = 500) -> dict:
    return {"struktur": {"name": "P", "dateien": n, "alle_dateien": n, "kinder": [],
                         "dateiliste": [_datei(i, f"{i:04d}" + "n" * 100 + ".pdf")
                                        for i in range(n)]},
            "zahlen": {}, "warnungen": [], "block_id": "b0000001"}


def test_luecke_ein_teil_struktur_ueber_64_kb_geht_nicht_an_ein_werkzeug_der_ki():
    from boerdi.services import teil_verweise

    gross = _grosse_struktur()
    assert len(str(gross)) > teil_verweise.MAX_BYTES

    async def teile(name):
        return gross if name == "struktur" else None

    args, fehlt = asyncio.run(teil_verweise.einsetzen(
        {"entwurf": {"x": {"$teil": "struktur"}}}, teile, "ui_strukturentwurf"))
    assert fehlt == ["struktur"]
    # ein Dienst- oder Modul-Schritt eines Ablaufs (ohne Werkzeug) bekommt den ganzen Teil
    args, fehlt = asyncio.run(teil_verweise.einsetzen(
        {"entwurf": {"x": {"$teil": "struktur"}}}, teile))
    assert fehlt == [] and args["entwurf"]["x"] == gross
