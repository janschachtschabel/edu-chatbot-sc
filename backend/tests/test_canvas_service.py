"""Characterization net for ``services/canvas_service.py`` — the canvas_service
OWN surface only: the three pure quick-reply/category helpers, the
``__getattr__`` module shim, and the async ``generate_canvas_content`` core.

Port of ALT ``tests/test_canvas_service.py`` (1315-line module net) but ONLY the
canvas_service-own tests. ALT tested the re-exported symbols (``_strip_latex``,
``resolve_material_type``, the ``get_*`` YAML getters, …) through the
canvas_service facade; NEU canvas_service DROPS that facade (consumers import
from the canonical ``domain/canvas/*`` homes), so those behaviours are pinned at
their homes instead (``test_canvas_postprocess.py`` / ``test_canvas_intent.py`` /
``test_canvas_types.py``) — not duplicated here.

Transport-adaptation vs ALT: canvas_service now calls ``llm.chat_completion``
(routing/semaphore) instead of ALT's ``client.chat.completions.create``. The
test fakes ``llm.chat_completion`` — the NEU analog of ALT's ``build_chat_kwargs``
capture-passthrough: it pins the *pre-gating* call args (temperature/max_tokens/
messages) model-profile-independently. ``captured["cc"]`` holds those kwargs.
Precedent: test_llm_learning_path.py (which fakes the deeper ``_acompletion``;
here we need temperature/max_tokens, so we fake one layer up).

Boundaries (the only mocks):
- ``config_loader.load_canvas_*`` (YAML-I/O) — patched at ``types.config_loader``
  (the getters live in ``domain/canvas/types`` and call the loader as a module
  attribute).
- ``fetch_wikipedia_summary`` — bare-name import in canvas_service → patch at ``cs``.
- ``llm.chat_completion`` — the LLM transport seam.

``test_module_getattr_shim`` uses ``defaults_only`` (not unpatched as in ALT):
NEU's ``config_loader`` is Postgres-backed, so the shim test is pinned against
the deterministic ``_DEFAULT_*`` fallback rather than a live store.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.canvas import types as canvas_types
from boerdi.services import canvas_service as cs
from boerdi.services import llm


def _boom(*_a, **_k):
    raise RuntimeError("yaml kaputt (test)")


@pytest.fixture
def defaults_only(monkeypatch):
    """Alle Canvas-YAML-Loader schlagen fehl → deterministische ``_DEFAULT_*``.

    Patch-Ort: die config_loader-Fassade (``types.config_loader``), weil die
    Getter die Loader per Attribut-Lookup zur Laufzeit aufrufen.
    """
    for name in (
        "load_canvas_material_types",
        "load_canvas_type_aliases",
        "load_canvas_create_triggers",
        "load_canvas_edit_triggers",
        "load_canvas_persona_priorities",
    ):
        monkeypatch.setattr(canvas_types.config_loader, name, _boom)


# ═══════════════════════════════════════════════════════════════════════
# Quick-Replies & Kategorie  (Default-Registry: 18 Typen, 5 analytische)
# ═══════════════════════════════════════════════════════════════════════

_ANALYTICAL_LABELS = [
    "📊 Bericht", "📈 Factsheet", "🗂️ Projektsteckbrief",
    "📰 Pressemitteilung", "⚖️ Vergleichs-Analyse",
]


def test_material_type_quick_replies_format_and_order(defaults_only):
    qr = cs.material_type_quick_replies()
    assert len(qr) == 18
    assert qr[0] == "🤖 Automatisch"
    assert all(" " in chip for chip in qr)  # "<emoji> <label>"


def test_quick_replies_for_analytical_persona(defaults_only):
    qr = cs.material_type_quick_replies_for_persona("P-ENT")
    assert qr[:5] == _ANALYTICAL_LABELS
    assert qr[5] == "🤖 Automatisch"
    assert len(qr) == 18


def test_quick_replies_for_didactic_or_unknown_persona(defaults_only):
    for persona in ("P-LEH", None, "P-GIBTSNICHT"):
        qr = cs.material_type_quick_replies_for_persona(persona)
        assert qr[0] == "🤖 Automatisch"
        assert qr[-5:] == _ANALYTICAL_LABELS
        assert len(qr) == 18


def test_get_material_type_category(defaults_only):
    assert cs.get_material_type_category("bericht") == "analytisch"
    assert cs.get_material_type_category("arbeitsblatt") == "didaktisch"
    assert cs.get_material_type_category("gibtsnicht") == "didaktisch"
    assert cs.get_material_type_category(None) == "didaktisch"


def test_module_getattr_shim(defaults_only):
    assert isinstance(cs.MATERIAL_TYPES, dict) and cs.MATERIAL_TYPES
    assert isinstance(cs._CREATE_TRIGGERS, tuple)
    with pytest.raises(AttributeError):
        _ = cs.GIBTS_NICHT


# ═══════════════════════════════════════════════════════════════════════
# generate_canvas_content
# ═══════════════════════════════════════════════════════════════════════


class _FakeMsg:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMsg(content)


class _FakeResp:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def _run_gen(
    monkeypatch,
    *,
    content="# Arbeitsblatt: Brüche\n\nAufgabe 1",
    raise_llm=False,
    wiki=None,
    wiki_raise=False,
    topic="Brüche",
    mtype="arbeitsblatt",
    **kwargs,
):
    """Führt generate_canvas_content mit gemockten Boundaries aus.

    Returns (title, md, captured) — ``captured["cc"]`` sind die Aufruf-Parameter
    von ``llm.chat_completion`` (pinnt die canvas_service-Seite des LLM-Aufrufs,
    unabhängig vom Modell-Profil des echten Transports).
    """
    captured: dict = {}

    async def fake_wiki(_topic, timeout_s=6.0):
        captured["wiki_topic"] = _topic
        if wiki_raise:
            raise ValueError("wiki down (test)")
        return wiki

    async def fake_chat_completion(**kw):
        captured["cc"] = kw
        if raise_llm:
            raise RuntimeError("boom")
        return _FakeResp(content)

    # Deterministisches Default-Vokabular (YAML-I/O-Boundary).
    monkeypatch.setattr(canvas_types.config_loader, "load_canvas_material_types", _boom)
    # Wikipedia-Boundary: bare-name-Import → Patch am cs-Modul.
    monkeypatch.setattr(cs, "fetch_wikipedia_summary", fake_wiki)
    # LLM-Transport-Boundary (pre-gating seam).
    monkeypatch.setattr(llm, "chat_completion", fake_chat_completion)

    title, md = asyncio.run(cs.generate_canvas_content(topic, mtype, **kwargs))
    return title, md, captured


def test_gen_happy_path_didactic_structure(monkeypatch):
    title, md, cap = _run_gen(
        monkeypatch,
        session_state={"entities": {"fach": "Mathematik", "stufe": "Sek I"}},
    )
    assert title == "Arbeitsblatt: Brüche"  # aus der H1 der LLM-Antwort
    assert md.startswith("# Arbeitsblatt: Brüche")
    msgs = cap["cc"]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user"]
    sys_msg, user_msg = msgs[0]["content"], msgs[1]["content"]
    assert "pädagogischer Assistent" in sys_msg
    assert "Fach: Mathematik | Bildungsstufe: Sek I" in sys_msg
    assert "Typ: **📝 Arbeitsblatt**" in user_msg
    assert "**Brüche**" in user_msg
    assert "QUALITÄTS-GATES" in user_msg
    # LLM-Aufruf-Parameter (canvas_service-Seite):
    assert cap["cc"]["temperature"] == 0.5
    assert cap["cc"]["max_tokens"] == 2500
    # Transport-Adaption: canvas_service übergibt KEIN Modell — die Auflösung
    # (get_chat_model) ist Sache von llm.chat_completion.
    assert "model" not in cap["cc"]


def test_gen_without_entities_uses_generic_learner_ctx(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, session_state=None)
    sys_msg = cap["cc"]["messages"][0]["content"]
    assert "allgemeine Lernende" in sys_msg
    assert "ANREDE" not in sys_msg  # formality="" → keine Direktive


def test_gen_unknown_type_key_falls_back_to_auto(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, mtype="gibtsnicht")
    assert "Typ: **🤖 Automatisch**" in cap["cc"]["messages"][1]["content"]


def test_gen_analytical_type_uses_analytical_system_prompt(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, mtype="bericht")
    sys_msg = cap["cc"]["messages"][0]["content"]
    assert "analytischer Assistent" in sys_msg
    assert "FAKTENTREUE" in sys_msg
    assert "pädagogischer Assistent" not in sys_msg


def test_gen_formality_siezen_appends_hard_directive(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, formality="siezen")
    sys_msg = cap["cc"]["messages"][0]["content"]
    assert "ANREDE — KRITISCH" in sys_msg
    assert "musst du siezen" in sys_msg


def test_gen_formality_duzen_appends_du_directive(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, formality="duzen")
    assert "Du-Form verwenden" in cap["cc"]["messages"][0]["content"]


def test_gen_formality_neutral_variants_add_nothing(monkeypatch):
    for f in ("wie_user", "neutral"):
        _, _, cap = _run_gen(monkeypatch, formality=f)
        assert "ANREDE" not in cap["cc"]["messages"][0]["content"]


def test_gen_memory_context_block_trimmed(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, memory_context="  Nutzer mag Fußball  ")
    user_msg = cap["cc"]["messages"][1]["content"]
    assert "Bisher bekannter Kontext aus der Sitzung:\nNutzer mag Fußball" in user_msg


# ── T12: Sammlungs-Kontext (Kompendium) in „Erstelle Inhalt dazu" ──────────

def test_gen_injects_collection_context_from_page_metadata(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, session_state={"entities": {
        "_page_metadata": {"title": "Optik-Sammlung", "compendium_text": "Licht und Linsen."},
    }})
    user_msg = cap["cc"]["messages"][1]["content"]
    assert "Optik-Sammlung" in user_msg
    assert "Licht und Linsen." in user_msg
    assert "nur nutzen, wenn zum Thema passend" in user_msg


def test_gen_collection_compendium_trimmed_to_1500(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, session_state={"entities": {
        "_page_metadata": {"title": "T", "compendium_text": "K" * 3000},
    }})
    user_msg = cap["cc"]["messages"][1]["content"]
    assert "K" * 1501 not in user_msg  # Kompendium auf 1500 gekappt


def test_gen_without_page_metadata_has_no_collection_block(monkeypatch):
    _, _, cap = _run_gen(monkeypatch, session_state={"entities": {"fach": "Mathe"}})
    user_msg = cap["cc"]["messages"][1]["content"]
    assert "Kontext der aktuellen Seite" not in user_msg


def test_gen_llm_error_degrades_to_error_markdown(monkeypatch):
    title, md, _ = _run_gen(monkeypatch, raise_llm=True)
    assert md == "# Arbeitsblatt: Brüche\n\n*Fehler beim Erstellen: boom*"
    assert title == "Arbeitsblatt: Brüche"  # H1 des Fehler-Markdowns


def test_gen_wikipedia_block_and_citation_safety_net(monkeypatch):
    wiki = {
        "title": "Photosynthese",
        "url": "https://de.wikipedia.org/wiki/Photosynthese",
        "extract": "Pflanzen wandeln Licht um.",
    }
    title, md, cap = _run_gen(
        monkeypatch,
        content="# Infoblatt: Photosynthese\n\nText",
        topic="Photosynthese", mtype="infoblatt", wiki=wiki,
    )
    user_msg = cap["cc"]["messages"][1]["content"]
    assert "Mögliche Faktenbasis aus der deutschen Wikipedia" in user_msg
    assert "RELEVANZ-PRÜFUNG" in user_msg
    assert "Photosynthese" in user_msg
    # LLM hat die Quelle weggelassen → Safety-Net hängt GENAU EINE Zeile an.
    assert md.count("Quelle: Wikipedia-Artikel") == 1
    assert "CC BY-SA 4.0" in md


def test_gen_wikipedia_citation_not_duplicated(monkeypatch):
    wiki = {"title": "Photosynthese", "url": "u", "extract": "E."}
    _, md, _ = _run_gen(
        monkeypatch,
        content='# X\n\n*Quelle: Wikipedia-Artikel „Photosynthese" (u). '
                "Inhalte unter CC BY-SA 4.0 verarbeitet.*",
        topic="Photosynthese", mtype="infoblatt", wiki=wiki,
    )
    assert md.count("Quelle: Wikipedia-Artikel") == 1


def test_gen_wikipedia_failure_is_tolerated(monkeypatch):
    title, _, cap = _run_gen(monkeypatch, wiki_raise=True)
    assert "Faktenbasis" not in cap["cc"]["messages"][1]["content"]
    assert title == "Arbeitsblatt: Brüche"  # Generierung läuft normal weiter


def test_gen_requested_label_on_auto_type(monkeypatch):
    title, _, cap = _run_gen(
        monkeypatch,
        mtype="auto", requested_label="Lernplakat",
        content="Nur Text ohne Heading",
    )
    user_msg = cap["cc"]["messages"][1]["content"]
    assert "ausdrücklich um **Lernplakat**" in user_msg
    # Ohne H1 in der Antwort: Titel-Fallback nutzt das requested_label.
    assert title == "Lernplakat: Brüche"


def test_gen_postprocessing_strips_latex_and_empty_sections(monkeypatch):
    _, md, _ = _run_gen(
        monkeypatch,
        content="# Quiz: X\n\nBerechne $\\frac{1}{2}$ mal 4\n\n## Differenzierung:",
        mtype="quiz",
    )
    assert md == "# Quiz: X\n\nBerechne 1/2 mal 4\n"
