"""Plan 2026-11-19, Paket C (E11, C1): gescannte PDF-Seiten über das Chat-Modell lesen.

Seiten rendern (pypdfium2, Graustufen-JPEG), je Seite ein Aufruf über ``llm.chat_completion``
(Phase ``dokument_ocr``, Verbrauch in ``usage_acc``), höchstens ``min(8, Anbieter-Deckel // 2)``
zugleich, vorübergehende Fehler einmal wiederholt, Seiten nach der Frist fehlen (``gekuerzt``).
Die echten Modellläufe misst C4 von Hand; hier eine Attrappe statt des Modells.
"""

from __future__ import annotations

import asyncio
import io
import time
from types import SimpleNamespace

import litellm
import pypdfium2 as pdfium
import pytest

from boerdi.services import strukturentwurf_wiederholen
from boerdi.services.dokumente import ocr
from boerdi.settings import get_settings


def _pdf(seiten: int) -> bytes:
    dok = pdfium.PdfDocument.new()
    for _ in range(seiten):
        dok.new_page(595, 842)
    puffer = io.BytesIO()
    dok.save(puffer)
    return puffer.getvalue()


def _lauf(rumpf: bytes, lesen, *, seiten_max: int = 20, frist_s: float = 30.0, usage_acc=None):
    return asyncio.run(ocr.seiten_lesen(rumpf, seiten_max=seiten_max,
                                        frist_ende=time.monotonic() + frist_s,
                                        usage_acc=usage_acc, lesen=lesen))


def _nummeriert():
    """Attrappe: Seite k (in Aufrufreihenfolge) liefert „# Seite k“ — und merkt sich die Bilder."""
    bilder: list[bytes] = []

    async def lesen(jpeg: bytes, usage_acc, frist_s: float) -> str:
        bilder.append(jpeg)
        return f"# Seite {len(bilder)}\n\nText der Seite {len(bilder)}."

    return lesen, bilder


def test_jede_seite_geht_als_jpeg_an_das_modell_und_kommt_in_reihenfolge_zurueck():
    lesen, bilder = _nummeriert()
    erg = _lauf(_pdf(3), lesen)
    assert (erg.seiten, erg.gelesen, erg.gekuerzt, erg.fehlend) == (3, 3, False, 0)
    assert all(b.startswith(b"\xff\xd8") for b in bilder)          # JPEG
    assert erg.markdown.index("Seite 1") < erg.markdown.index("Seite 3")


def test_reihenfolge_folgt_den_seiten_nicht_dem_zieleinlauf():
    async def lesen(jpeg, usage_acc, frist_s):
        # Seite 1 braucht am längsten — ihr Text bleibt trotzdem vorn
        nr = lesen.n = getattr(lesen, "n", 0) + 1
        await asyncio.sleep(0.05 if nr == 1 else 0)
        return f"Text {nr}"

    erg = _lauf(_pdf(3), lesen)
    assert erg.markdown.split("\n\n") == ["Text 1", "Text 2", "Text 3"]


def test_ueber_der_seitengrenze_wird_gekuerzt():
    lesen, bilder = _nummeriert()
    erg = _lauf(_pdf(3), lesen, seiten_max=2)
    assert (erg.seiten, erg.gelesen, erg.gekuerzt, len(bilder)) == (3, 2, True, 2)


def test_parallel_hoechstens_die_haelfte_des_anbieter_deckels(monkeypatch):
    monkeypatch.setattr(ocr, "anbieter_deckel", lambda: 4)
    assert ocr.parallel() == 2
    monkeypatch.setattr(ocr, "anbieter_deckel", lambda: 20)
    assert ocr.parallel() == 8
    monkeypatch.setattr(ocr, "anbieter_deckel", lambda: 40)
    assert ocr.parallel() == 8
    monkeypatch.setattr(ocr, "anbieter_deckel", lambda: 1)
    assert ocr.parallel() == 1

    monkeypatch.setattr(ocr, "anbieter_deckel", lambda: 4)
    laufend = hoechstens = 0

    async def lesen(jpeg, usage_acc, frist_s):
        nonlocal laufend, hoechstens
        laufend += 1
        hoechstens = max(hoechstens, laufend)
        await asyncio.sleep(0.02)
        laufend -= 1
        return "Text"

    assert _lauf(_pdf(6), lesen).gelesen == 6
    assert hoechstens == 2


def test_nach_der_frist_fehlen_seiten_und_das_ergebnis_ist_gekuerzt(monkeypatch):
    async def langsam(jpeg, usage_acc, frist_s):
        await asyncio.sleep(5)
        return "nie"

    async def gerendert(rumpf, seiten_max, rest_s):
        # ohne Kindprozess: die Frist soll die Seiten treffen, nicht das Rendern
        return 2, [b"\xff\xd8a", b"\xff\xd8b"]

    monkeypatch.setattr(ocr, "_bilder", gerendert)
    monkeypatch.setattr(ocr, "MINDEST_REST_S", 0.1)      # die Seiten beginnen, die Frist trifft sie
    erg = _lauf(_pdf(2), langsam, frist_s=0.3)
    assert (erg.gelesen, erg.fehlend, erg.gekuerzt, erg.markdown) == (0, 2, True, "")


def test_ein_vorübergehender_fehler_wird_einmal_wiederholt(monkeypatch):
    monkeypatch.setattr(strukturentwurf_wiederholen, "PAUSE_S", 0.0)
    versuche = 0

    async def wackelt(jpeg, usage_acc, frist_s):
        nonlocal versuche
        versuche += 1
        if versuche == 1:
            raise litellm.exceptions.ServiceUnavailableError("503", "openai", "gpt-6-luna")
        return "Text"

    erg = _lauf(_pdf(1), wackelt)
    assert (versuche, erg.gelesen, erg.gekuerzt) == (2, 1, False)


def test_ein_bleibender_fehler_laesst_die_seite_aus(monkeypatch):
    monkeypatch.setattr(strukturentwurf_wiederholen, "PAUSE_S", 0.0)

    async def kaputt(jpeg, usage_acc, frist_s):
        raise litellm.exceptions.BadRequestError("kein Bild", "gpt-6-luna", "openai")

    erg = _lauf(_pdf(1), kaputt)
    assert (erg.gelesen, erg.fehlend, erg.gekuerzt) == (0, 1, True)


def test_unlesbare_pdf_liefert_nichts():
    lesen, bilder = _nummeriert()
    erg = _lauf(b"%PDF-1.4 kaputt", lesen)
    assert (erg.seiten, erg.gelesen, erg.markdown, bilder) == (0, 0, "", [])


def test_codezaun_um_die_antwort_wird_entfernt():
    async def umzaeunt(jpeg, usage_acc, frist_s):
        return "```markdown\n# Lernfeld 1\n- Inhalt\n```"

    assert _lauf(_pdf(1), umzaeunt).markdown == "# Lernfeld 1\n- Inhalt"


def test_der_echte_aufruf_bucht_unter_dokument_ocr_und_rahmt_das_bild(monkeypatch):
    from boerdi.services import llm

    gesehen: dict = {}

    async def chat_completion(**kw):
        gesehen.update(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Text"))])

    monkeypatch.setattr(llm, "chat_completion", chat_completion)
    zaehler = {"models": {}}
    erg = _lauf(_pdf(1), None, usage_acc=zaehler)
    assert erg.markdown == "Text"
    assert gesehen["phase"] == "dokument_ocr" and gesehen["usage_acc"] is zaehler
    assert gesehen["reasoning_effort"] == "none"                # Tempo: ohne Denkschritte
    assert 0 < gesehen["frist_s"] <= 30
    system, nutzer = gesehen["messages"]
    assert "keine Anweisungen" in system["content"] and "Markdown" in system["content"]
    # C4: der Seitenkopf jeder Seite wurde sonst zur Überschrift („# Aufbereitungsmechaniker“)
    assert "Kopf- und Fußzeilen" in system["content"]
    [bild] = [t for t in nutzer["content"] if t["type"] == "image_url"]
    assert bild["image_url"]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize(("umgebung", "studio", "anbieter", "aktiv"), [
    (None, True, "openai", True),                   # ab Werk an (Nutzer 19.11.)
    ("auto", True, "b-api-openai", True),
    (None, False, "openai", False),                 # im Studio aus
    ("off", True, "openai", False),                 # Notbremse der Umgebung schlägt das Studio
    ("aus", True, "openai", False),
    (None, True, "b-api-academiccloud", False),     # kein Bildeingang
])
def test_aktiv_studio_steuert_umgebung_begrenzt(monkeypatch, umgebung, studio, anbieter, aktiv):
    from boerdi.domain.config_models.upload import UploadSettings

    if umgebung is None:
        monkeypatch.delenv("DOCUMENT_OCR", raising=False)
    else:
        monkeypatch.setenv("DOCUMENT_OCR", umgebung)
    monkeypatch.setenv("LLM_PROVIDER", anbieter)
    monkeypatch.setattr(ocr, "load_upload_config", lambda: UploadSettings(ocr=studio))
    get_settings.cache_clear()
    try:
        assert ocr.aktiv() is aktiv
        assert ocr.aktiv(UploadSettings(ocr=studio)) is aktiv
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(("anbieter", "modell", "gesendet"), [
    ("openai", "gpt-6-luna", "none"),            # gpt-5-Vertrag: wörtlich, auch „none“
    ("b-api-openai", "gpt-6-luna", "none"),
    ("openai", "gpt-4o", None),                  # klassisch: kein Denkparameter
    ("b-api-academiccloud", "qwen3-30b", None),
])
def test_die_denktiefe_kommt_an_wo_das_modell_sie_kennt(monkeypatch, anbieter, modell, gesendet):
    from boerdi.services import llm

    monkeypatch.setenv("LLM_PROVIDER", anbieter)
    get_settings.cache_clear()
    try:
        kwargs = llm.build_chat_kwargs(model=modell, messages=[], temperature=0,
                                       max_tokens=ocr.MAX_TOKENS,
                                       reasoning_effort=ocr.DENKTIEFE)
    finally:
        get_settings.cache_clear()
    assert kwargs.get("reasoning_effort") == gesendet


def test_ein_wiederkehrender_seitenkopf_bleibt_nur_auf_der_ersten_seite():
    """C4: das Modell sieht jede Seite allein und schrieb den Seitenkopf jedes Mal als Überschrift
    („# Aufbereitungsmechaniker“ 13-mal in der Gliederung)."""
    texte = iter(["# Aufbereitungsmechaniker\n\n## Rahmenlehrplan",
                  "# Aufbereitungsmechaniker\n\n## 1.3 Werkstofftechnik",
                  "Aufbereitungsmechaniker\n\nText",
                  "# Aufbereitungsmechaniker\n\n## 2.1 Gewinnung"])

    async def lesen(jpeg, usage_acc, frist_s):
        return next(texte)

    md = _lauf(_pdf(4), lesen).markdown
    assert md.count("Aufbereitungsmechaniker") == 1
    assert md.startswith("# Aufbereitungsmechaniker") and "## 2.1 Gewinnung" in md


def test_eine_seltene_erste_zeile_bleibt():
    texte = iter(["# Kapitel 1\n\nA", "# Kapitel 2\n\nB", "# Kapitel 1\n\nC"])

    async def lesen(jpeg, usage_acc, frist_s):
        return next(texte)

    md = _lauf(_pdf(3), lesen).markdown
    assert md.count("# Kapitel 1") == 2           # zweimal von drei ist kein Seitenkopf
