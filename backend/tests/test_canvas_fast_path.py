"""Characterization net for ``services/canvas_fast_path.py`` — the
Canvas-Create-Fast-Path (I05 → M10), sister of ``run_lp_fast_path``.

1:1 port of the ``test_canvas_fp_*`` block from ALT
``tests/test_chat_pipeline_phases.py``. The result is now a
``CanvasFastPathResult`` NamedTuple, but since it IS a tuple the ALT positional
assertions (``out == (False, None, [], …)`` and positional unpack) hold
unchanged. The function is keyword-only, so ``_run_canvas`` calls it with
keywords.

Patch-Orte: alle canvas-Namen (``extract_material_type_from_message``,
``resolve_material_type``, ``get_type_aliases``, ``get_material_types``,
``generate_canvas_content``, ``named_artifact_label``,
``material_type_quick_replies_for_persona``) sind bare-name-Top-Importe in
``canvas_fast_path`` → dort patchen. ``_canvas_completion_message`` (pur, aus
``domain/completion_messages``, bereits genetzt) läuft ECHT mit.

NICHT gepinnt (wie ALT): einzelne Garbage-Filter-Unterregeln (nur der
Meta-Wort-Start als Repräsentant), alternative Lösungen-Validator-Formate, die
lexikalischen Stripper-Varianten des messy Fallbacks.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.api.schemas import ChatRequest, ClassificationResult, Environment
from boerdi.domain.completion_messages import _canvas_completion_message
from boerdi.obs.usage import new_accumulator
from boerdi.services import canvas_fast_path as cfp
from boerdi.services.canvas_fast_path import run_canvas_create_fast_path


@pytest.fixture
def canvas_fp(monkeypatch):
    """Patcht alle canvas-Boundaries von ``run_canvas_create_fast_path`` (alles
    bare names in canvas_fast_path → Patch auf ``cfp``). ``rec`` steuert die
    Rückgaben und protokolliert die Aufrufe."""
    rec = {
        "extract": "",                # extract_material_type_from_message → Key
        "resolve": {},                # Mapping für resolve_material_type
        "named": "",                  # named_artifact_label
        "gen_result": ("Titel", "## Einstieg\n\nText"),
        "gen_raises": False,
        "gen_calls": [],
        "named_calls": [],
        "qr": ["Arbeitsblatt", "Quiz"],
        "qr_calls": [],
    }

    monkeypatch.setattr(cfp, "extract_material_type_from_message",
                        lambda msg: rec["extract"])
    monkeypatch.setattr(
        cfp, "resolve_material_type",
        lambda v: rec["resolve"].get((v or "").strip().lower(), ""),
    )
    monkeypatch.setattr(cfp, "get_type_aliases",
                        lambda: {"arbeitsblatt": "arbeitsblatt", "quiz": "quiz"})
    monkeypatch.setattr(cfp, "get_material_types", lambda: {
        "arbeitsblatt": {"label": "Arbeitsblatt", "emoji": "📝"},
        "quiz": {"label": "Quiz", "emoji": "❓"},
        # NOTE: pinnt IST-Verhalten — der Robust-Fallback greift auf
        # get_material_types()["auto"]["emoji"] zu; ohne "auto"-Key in der
        # Material-Typ-Config gäbe es einen KeyError.
        "auto": {"label": "Passendes Material", "emoji": "✨"},
    })

    async def _gen(**kw):
        rec["gen_calls"].append(kw)
        if rec["gen_raises"]:
            raise RuntimeError("gen boom")
        return rec["gen_result"]
    monkeypatch.setattr(cfp, "generate_canvas_content", _gen)

    def _named(msg, ent):
        rec["named_calls"].append((msg, ent))
        return rec["named"]
    monkeypatch.setattr(cfp, "named_artifact_label", _named)

    def _qr(persona, lang="de"):
        # C1-g2e: die Chip-Beschriftungen folgen der Sprache des Zuges — die
        # Attrappe haelt beides fest, sonst waere die Sprache unbelegt.
        rec["qr_calls"].append((persona, lang))
        return rec["qr"]
    monkeypatch.setattr(cfp, "material_type_quick_replies_for_persona", _qr)
    return rec


MD_WITH_LOES = "## Aufgaben\n\n1. Rechne 2+2.\n2. Rechne 3+3.\n\n## Lösungen\n\n1. 4\n2. 6"


def _run_canvas(message="Erstelle ein Arbeitsblatt", entities=None,
                session_state=None, pattern_output=None, lp_routed=False,
                intent="I05", tools_called=None, new_state="S1",
                locale="de-DE", frame_exhausted=False, usage_acc=None):
    classification = ClassificationResult(intent_id=intent,
                                          entities=entities or {})
    return asyncio.run(run_canvas_create_fast_path(
        req=ChatRequest(session_id="s", message=message,
                        environment=Environment(locale=locale)),
        classification=classification,
        session_state=session_state if session_state is not None else {"entities": {}},
        pattern_output=pattern_output or {},
        memory_context=None,                    # nur durchgereicht
        lp_routed=lp_routed,
        tools_called=tools_called if tools_called is not None else ["TC-SENTINEL"],
        new_state=new_state,
        frame_exhausted=frame_exhausted,
        usage_acc=usage_acc,
    ))


def test_canvas_fp_passthrough_when_not_i05(canvas_fp):
    tc = ["vorher"]
    out = _run_canvas(intent="I03", tools_called=tc, new_state="SX")
    assert out == (False, None, [], "", ["vorher"], [], "SX")
    assert out[4] is tc                      # tools_called identisch durchgereicht
    assert canvas_fp["gen_calls"] == []


def test_canvas_fp_tritt_bei_erschoepftem_frame_zurueck(canvas_fp):
    """B3: der Fast-Path ist der ZWEITE Erzeuger der Slot-Rückfrage.

    Sein Eintritt hängt allein an ``intent_id == 'I05'`` — die Musterwahl
    umgeht er absichtlich („even if the pattern engine eliminated M10"). Live
    gemessen 2026-08-10: die Umleitung des Klärers auf M15 blieb wirkungslos,
    weil der Fast-Path danach lief und die Frage erneut rendete
    (``effective_pattern override: engine=M15 → executed=M03,
    canvas_routed=True``). Ist der Vorgang erschöpft, muss er zurücktreten.
    """
    tc = ["vorher"]
    out = _run_canvas(message="egal", tools_called=tc, new_state="SX",
                      frame_exhausted=True)
    assert out == (False, None, [], "", ["vorher"], [], "SX")
    assert canvas_fp["gen_calls"] == []


def test_canvas_fp_passthrough_when_lp_routed(canvas_fp):
    # Selbst mit I05 + fertigen Slots: lp_routed=True gewinnt → kein Fast-Path.
    canvas_fp["resolve"] = {"arbeitsblatt": "arbeitsblatt"}
    out = _run_canvas(entities={"thema": "Photosynthese",
                                "material_typ": "Arbeitsblatt"},
                      lp_routed=True, new_state="SX")
    assert out[0] is False and out[6] == "SX"
    assert canvas_fp["gen_calls"] == []


def test_canvas_fp_success_generates_and_mutates_session(canvas_fp):
    canvas_fp["resolve"] = {"arbeitsblatt": "arbeitsblatt"}
    canvas_fp["gen_result"] = ("Titel", MD_WITH_LOES)
    ss = {"entities": {}}
    tc = ["TC-SENTINEL"]
    routed, payload, forced_qr, text, tools, cards, new_state = _run_canvas(
        entities={"thema": "Photosynthese", "material_typ": "Arbeitsblatt"},
        session_state=ss, tools_called=tc,
    )
    assert routed is True and payload is None and forced_qr == []
    assert tools == ["canvas_service.generate_canvas_content"]
    assert tools is not tc                   # neu gebunden, Sentinel unberührt
    assert cards == [] and new_state == "S3"
    # response_text = Completion-Bubble (echter Helfer) + Markdown konkateniert.
    expected = (
        _canvas_completion_message(
            "Arbeitsblatt", "Photosynthese", MD_WITH_LOES,
            canvas_enabled=False, formality="",
        ).rstrip() + "\n\n" + MD_WITH_LOES.lstrip()
    ).strip()
    assert text == expected
    assert text.startswith(
        "Ich habe dir ein **Arbeitsblatt** zum Thema *Photosynthese* erstellt."
    )
    # ## Lösungen vorhanden → KEIN Stub angehängt.
    assert "_Lösungen werden ergänzt" not in text
    # Session-Mutationen (sticky Canvas-Kontext für Folge-Turns):
    assert ss["entities"]["_canvas_material_type"] == "arbeitsblatt"
    assert ss["entities"]["_canvas_topic"] == "Photosynthese"
    assert ss["entities"]["_canvas_last_markdown"] == MD_WITH_LOES
    assert ss["entities"]["thema"] == "Photosynthese"
    # Boundary-Aufruf: kwargs inkl. formality-Default, leerem requested_label,
    # der Ausgabe-Sprache aus ``req.environment.locale`` (C1-f2a) und dem
    # Token-Merkposten (K1c; hier None, weil dieser Aufruf keinen mitgibt).
    (kw,) = canvas_fp["gen_calls"]
    assert kw == {"topic": "Photosynthese", "material_type_key": "arbeitsblatt",
                  "session_state": ss, "memory_context": None,
                  "formality": "", "requested_label": "", "lang": "de",
                  "usage_acc": None}
    assert canvas_fp["named_calls"] == []    # Robust-Fallback nicht befragt


def test_canvas_fp_loesungen_stub_and_siezen_formality(canvas_fp):
    # Quiz ohne Lösungen-Block → Stub wird angehängt; formality=siezen aus
    # pattern_output steuert die Bubble UND wird an den Generator gereicht.
    canvas_fp["resolve"] = {"quiz": "quiz"}
    canvas_fp["gen_result"] = ("T", "1. Frage A?\n2. Frage B?")
    ss = {"entities": {}}
    routed, _p, _q, text, tools, _c, new_state = _run_canvas(
        entities={"thema": "Bruchrechnung", "material_typ": "Quiz"},
        session_state=ss, pattern_output={"formality": "siezen"},
    )
    assert routed is True and new_state == "S3"
    assert tools == ["canvas_service.generate_canvas_content"]
    assert text.startswith(
        "Ich habe Ihnen ein **Quiz** zum Thema *Bruchrechnung* erstellt."
    )
    assert "## Lösungen" in text
    assert "_Lösungen werden ergänzt" in text
    # Der Stub steckt auch im persistierten Markdown (Folge-Edit-Basis).
    assert "_Lösungen werden ergänzt" in ss["entities"]["_canvas_last_markdown"]
    assert canvas_fp["gen_calls"][0]["formality"] == "siezen"


def test_canvas_fp_topic_from_marker_pattern_in_message(canvas_fp):
    # Kein thema/fach in Entities/Session → Topic aus "zum Thema X"-Marker.
    canvas_fp["extract"] = "arbeitsblatt"
    canvas_fp["gen_result"] = ("T", MD_WITH_LOES)
    ss = {"entities": {}}
    routed, *_rest = _run_canvas(
        message="Erstelle ein Arbeitsblatt zum Thema Photosynthese für Klasse 6",
        session_state=ss,
    )
    assert routed is True
    assert canvas_fp["gen_calls"][0]["topic"] == "Photosynthese"
    assert ss["entities"]["thema"] == "Photosynthese"


def test_canvas_fp_sticky_session_topic_and_type(canvas_fp):
    # Classifier still (keine Entities) → Topic UND Typ aus der Session.
    canvas_fp["resolve"] = {"quiz": "quiz"}
    canvas_fp["gen_result"] = ("T", MD_WITH_LOES)
    ss = {"entities": {"thema": "Brüche", "material_typ": "Quiz"}}
    routed, _p, _q, _t, tools, _c, new_state = _run_canvas(
        message="mach weiter", session_state=ss,
    )
    assert routed is True and new_state == "S3"
    kw = canvas_fp["gen_calls"][0]
    assert kw["topic"] == "Brüche" and kw["material_type_key"] == "quiz"


def test_canvas_fp_generation_error_degrades_gracefully(canvas_fp):
    canvas_fp["resolve"] = {"arbeitsblatt": "arbeitsblatt"}
    canvas_fp["gen_raises"] = True
    ss = {"entities": {}, "state_id": "S2"}
    routed, payload, forced_qr, text, tools, cards, new_state = _run_canvas(
        entities={"thema": "Photosynthese", "material_typ": "Arbeitsblatt"},
        session_state=ss,
    )
    assert routed is True and payload is None and forced_qr == []
    assert text == (
        "Ich konnte das **Arbeitsblatt** zum Thema *Photosynthese* gerade "
        "nicht erstellen (RuntimeError). Versuch es nochmal — "
        "meistens klappt es beim zweiten Anlauf."
    )
    assert tools == ["canvas_service.generate_canvas_content", "error"]
    assert cards == []
    assert new_state == "S2"                 # session state_id, nicht "S3"
    assert "_canvas_topic" not in ss["entities"]   # keine Session-Mutation

    # Ohne state_id in der Session fällt new_state auf "S3" zurück.
    out2 = _run_canvas(
        entities={"thema": "Photosynthese", "material_typ": "Arbeitsblatt"},
        session_state={"entities": {}},
    )
    assert out2[6] == "S3"


def test_canvas_fp_topic_without_type_asks_for_type_with_persona_qr(canvas_fp):
    # Fach-Fallback (kein thema, aber fach) + Typ-Degradation mit Persona-QRs.
    ss = {"entities": {}, "persona_id": "P-LEH"}
    routed, payload, forced_qr, text, tools, cards, new_state = _run_canvas(
        entities={"fach": "Mathe"}, session_state=ss, new_state="SX",
        tools_called=["TC-SENTINEL"],
    )
    assert routed is True and payload is None
    assert text.startswith(
        "Welches Material soll ich dir zum Thema **Mathe** erstellen?"
    )
    assert tools == []                       # neu gebunden (nicht der Sentinel)
    assert cards == []
    assert new_state == "SX"                 # unverändert durchgereicht
    assert forced_qr == ["Arbeitsblatt", "Quiz"]
    assert canvas_fp["qr_calls"] == [("P-LEH", "de")]
    assert canvas_fp["gen_calls"] == []


def test_canvas_fp_robust_fallback_named_artifact_uses_auto(canvas_fp):
    # Topic da, Typ unbekannt, aber klar benanntes Artefakt → mt_key="auto",
    # Label = der genannte Begriff, requested_label an den Generator gereicht.
    canvas_fp["named"] = "Argumentationshilfe"
    canvas_fp["gen_result"] = ("T", "## Einstieg\n\nText")
    routed, _p, _q, text, tools, _c, new_state = _run_canvas(
        message="Erstelle mir eine Argumentationshilfe",
        entities={"thema": "Klimawandel", "material_typ": "Superblatt"},
    )
    assert routed is True and new_state == "S3"
    assert tools == ["canvas_service.generate_canvas_content"]
    assert canvas_fp["named_calls"] == [
        ("Erstelle mir eine Argumentationshilfe", "Superblatt"),
    ]
    kw = canvas_fp["gen_calls"][0]
    assert kw["material_type_key"] == "auto"
    assert kw["requested_label"] == "Argumentationshilfe"
    assert text.startswith(
        "Ich habe dir ein **Argumentationshilfe** zum Thema *Klimawandel* erstellt."
    )


def test_canvas_fp_no_topic_asks_for_topic(canvas_fp):
    routed, payload, forced_qr, text, tools, cards, new_state = _run_canvas(
        message="Erstelle mir was", new_state="SX",
    )
    assert routed is True and payload is None
    assert text == (
        "Gerne erstelle ich dir ein Material. Zu welchem **Thema**? "
        "Beispiel: \"Erstelle ein Arbeitsblatt zur Photosynthese für Klasse 6\"."
    )
    assert tools == [] and cards == []
    assert forced_qr == []                   # KEINE Typ-Chips in diesem Zweig
    assert new_state == "SX"
    assert canvas_fp["gen_calls"] == []


def test_canvas_fp_garbage_fallback_topic_rejected(canvas_fp):
    # Messy-Fallback liefert "Ideen für ein neues" → Plausibilitätscheck
    # (Meta-Wort-Start "ideen") verwirft das Topic → generische Thema-Frage
    # statt Generierung, obwohl der Material-Typ erkannt wurde.
    canvas_fp["extract"] = "arbeitsblatt"
    routed, _p, _q, text, tools, _c, _ns = _run_canvas(
        message="Ich brauche Ideen für ein neues Arbeitsblatt",
    )
    assert routed is True
    assert text.startswith("Gerne erstelle ich dir ein Material.")
    assert tools == []
    assert canvas_fp["gen_calls"] == []


def test_canvas_fp_phantom_topic_forces_clarification(canvas_fp):
    # "einem Thema" ist ein Phantom-Topic → wie leer behandeln, keine Generierung.
    canvas_fp["resolve"] = {"quiz": "quiz"}
    routed, _p, _q, text, tools, _c, _ns = _run_canvas(
        message="Mach ein Quiz zu einem Thema",
        entities={"thema": "einem Thema", "material_typ": "Quiz"},
    )
    assert routed is True
    assert text.startswith("Gerne erstelle ich dir ein Material.")
    assert tools == []
    assert canvas_fp["gen_calls"] == []


# ── C1-f2b2: Sprache der Rückfragen, des Fehlers und des Lösungen-Wächters ──
MD_WITH_SOLUTIONS = ("## Tasks\n\n1. Add 2+2.\n2. Add 3+3.\n\n"
                     "## Solutions\n\n1. 4\n2. 6")


def test_canvas_fp_ask_type_english(canvas_fp):
    _routed, _p, _q, text, _t, _c, _ns = _run_canvas(
        entities={"thema": "Maths"}, locale="en-GB",
    )
    assert text.startswith("Which kind of material should I create on **Maths**?")
    # Das genannte Stichwort muss ein Alias sein. Seit C1-g2e kennt
    # ``type-aliases.yaml`` auch ``automatic`` — der englische Satz nennt
    # deshalb das englische Wort, nicht mehr das deutsche.
    assert '"Automatic"' in text
    assert "Automatisch" not in text


def test_canvas_fp_ask_topic_english(canvas_fp):
    _routed, _p, _q, text, _t, _c, _ns = _run_canvas(
        message="Create a worksheet", entities={}, locale="en-GB",
    )
    assert text.startswith("I will gladly create a material for you.")


def test_canvas_fp_generation_error_english(canvas_fp):
    canvas_fp["resolve"] = {"arbeitsblatt": "arbeitsblatt"}
    canvas_fp["gen_raises"] = True
    _routed, _p, _q, text, _t, _c, _ns = _run_canvas(
        entities={"thema": "Photosynthesis", "material_typ": "Arbeitsblatt"},
        locale="en-GB",
    )
    assert text == (
        "I could not create the **Arbeitsblatt** on *Photosynthesis* just now "
        "(RuntimeError). Please try again — it usually works on the second attempt."
    )


def test_canvas_fp_english_solutions_block_recognised(canvas_fp):
    """Der Wächter liest unser EIGENES Markdown. Seit C1-f2a ist das bei
    ``locale='en-*'`` englisch — mit dem deutschen ``## Lösungen``-Muster
    griff er NIE und hängte an jedes englische Arbeitsblatt einen deutschen
    Stub an."""
    canvas_fp["resolve"] = {"arbeitsblatt": "arbeitsblatt"}
    canvas_fp["gen_result"] = ("Title", MD_WITH_SOLUTIONS)
    ss = {"entities": {}}
    _routed, _p, _q, text, _t, _c, _ns = _run_canvas(
        entities={"thema": "Fractions", "material_typ": "Arbeitsblatt"},
        session_state=ss, locale="en-GB",
    )
    assert "Lösungen" not in text
    assert "Solutions will be added" not in text
    assert ss["entities"]["_canvas_last_markdown"] == MD_WITH_SOLUTIONS


def test_canvas_fp_english_solutions_stub_is_english(canvas_fp):
    canvas_fp["resolve"] = {"quiz": "quiz"}
    canvas_fp["gen_result"] = ("T", "1. Question A?\n2. Question B?")
    _routed, _p, _q, text, _t, _c, _ns = _run_canvas(
        entities={"thema": "Fractions", "material_typ": "Quiz"},
        locale="en-GB",
    )
    assert "## Solutions" in text
    assert "_Solutions will be added" in text
    assert "Lösungen" not in text


def test_merkposten_erreicht_den_material_generator(canvas_fp):
    """K1c-Naht: der Canvas-Fast-Path führte gar keinen Merkposten — anders
    als der LP-Fast-Path, der ihn schon als Parameter hatte (Z. 95)."""
    canvas_fp["resolve"] = {"arbeitsblatt": "arbeitsblatt"}
    canvas_fp["gen_result"] = ("Titel", MD_WITH_LOES)
    acc = new_accumulator()

    _run_canvas(entities={"thema": "Photosynthese", "material_typ": "Arbeitsblatt"},
                usage_acc=acc)

    assert canvas_fp["gen_calls"][0]["usage_acc"] is acc
