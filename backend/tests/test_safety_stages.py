"""Safety-Layer — die beiden LLM-Stufenmodule direkt (moderation + legal).

Neu in 3-4: der Transport wandert von ALT ``llm_provider`` auf die NEU-Fassaden
(``litellm.amoderation`` / ``services.llm.chat_completion``). Diese Datei pinnt
(a) die 3-Zweig-Credential-Auflösung ``moderation._moderation_target`` (Port von
ALT ``get_moderation_client``), (b) das Parsing der Moderation-Antwort und
(c) die Fail-Open-Garantie beider Stufen ({} statt Ausnahme → Regex bleibt Floor).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from boerdi.obs.usage import new_accumulator
from boerdi.services.safety import legal as legal_mod
from boerdi.services.safety import moderation as mod


def _settings(*, openai="", b_api="", openai_base="", b_base="https://b-api.example"):
    return SimpleNamespace(
        openai_api_key=SecretStr(openai),
        openai_base_url=openai_base,
        b_api_key=SecretStr(b_api),
        b_api_base_url=b_base,
    )


# ── _moderation_target: 3-Zweig-Routing (Port von get_moderation_client) ──

def test_target_openai_with_key(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "openai")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings(openai="sk-abc"))
    base, key, headers = mod._moderation_target()
    assert base == "https://api.openai.com/v1"  # openai_base_url leer → Default
    assert key == "sk-abc"
    assert headers is None


def test_target_openai_without_key_is_none(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "openai")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings(openai=""))
    assert mod._moderation_target() is None


def test_target_b_api_openai_passthrough_uses_b_key(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-openai")
    monkeypatch.setattr(mod, "get_settings",
                        lambda: _settings(b_api="b-key", b_base="https://b-api.example/"))
    base, key, headers = mod._moderation_target()
    assert base == "https://b-api.example/openai"  # trailing slash gestript + /openai
    assert key == "b-key"
    assert headers == {"X-API-KEY": "b-key"}


def test_target_b_api_openai_falls_back_to_native_openai(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-openai")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings(b_api="", openai="sk-native"))
    base, key, headers = mod._moderation_target()
    assert base == "https://api.openai.com/v1"
    assert key == "sk-native"
    assert headers is None


def test_target_b_api_openai_no_keys_is_none(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-openai")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings())
    assert mod._moderation_target() is None


def test_target_academiccloud_ist_aus_auch_mit_openai_schluessel(monkeypatch):
    # Paket 7 (L5, Nutzer 2026-10-09): Die AcademicCloud hat keine Moderation
    # (B-API ``/academiccloud/moderations`` → 404, gemessen 2026-10-09). Bis dahin
    # gingen die Nachrichten dann an OpenAI — wer AcademicCloud wählt, will das
    # nicht. Es bleibt der Regex-Boden.
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-academiccloud")
    monkeypatch.setattr(mod, "get_settings",
                        lambda: _settings(openai="sk-x", openai_base="https://proxy/v1/"))
    assert mod._moderation_target() is None


def _ok_moderation(**_kwargs):
    return _fake_moderation_response(flagged=False, categories={"hate": False},
                                     scores={"hate": 0.01})


def test_die_moderation_wartet_nicht_hinter_antwort_stroemen(monkeypatch):
    """Review Paket 7 (MAJOR 8): die Moderation wartete innerhalb ihrer Frist auf einen
    Platz am Anbieter-Deckel. Ein Antwort-Strom hält seinen Platz bis zum Ende — bei
    20 gleichzeitigen Antworten lief die Frist ab, und jede Nachricht ging ungeprüft
    durch. Sie hat jetzt eigene Plätze."""
    from boerdi.services import llm, llm_parallel

    monkeypatch.setattr(llm_parallel, "_anbieter_deckel", lambda: 1)
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))
    monkeypatch.setattr(mod, "_MOD_TIMEOUT_SECONDS", 0.2)

    async def _fake(**kwargs):
        return _ok_moderation(**kwargs)

    monkeypatch.setattr(mod, "_amoderation", _fake)

    async def _lauf():
        llm_parallel.reset()
        async with llm.semaphore():               # der eine Platz: ein laufender Strom
            return await mod.moderate("Hallo")

    assert asyncio.run(_lauf())["scores"] == {"hate": 0.01}


def test_die_moderation_hat_eine_eigene_grenze(monkeypatch):
    from boerdi.services import llm_parallel

    monkeypatch.setattr(llm_parallel, "MODERATION_PARALLEL", 2)
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))
    gleichzeitig = [0, 0]

    async def _fake(**kwargs):
        gleichzeitig[0] += 1
        gleichzeitig[1] = max(gleichzeitig)
        await asyncio.sleep(0.02)
        gleichzeitig[0] -= 1
        return _ok_moderation(**kwargs)

    monkeypatch.setattr(mod, "_amoderation", _fake)

    async def _lauf():
        llm_parallel.reset()
        return await asyncio.gather(*(mod.moderate(f"n{i}") for i in range(6)))

    assert all(asyncio.run(_lauf()))
    assert gleichzeitig[1] == 2


def test_das_warten_auf_einen_platz_zaehlt_zur_frist(monkeypatch):
    """Review Paket 9 (MAJOR 4): die Frist galt nur dem Aufruf. Hing der Anbieter,
    warteten weitere Züge ohne Grenze auf einen der Plätze — samt Sitzungssperre."""
    from boerdi.services import llm_parallel

    monkeypatch.setattr(llm_parallel, "MODERATION_PARALLEL", 1)
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))
    monkeypatch.setattr(mod, "_MOD_TIMEOUT_SECONDS", 0.2)

    async def _fake(**kwargs):
        return _ok_moderation(**kwargs)

    monkeypatch.setattr(mod, "_amoderation", _fake)

    async def _lauf():
        llm_parallel.reset()
        async with llm_parallel.moderations_semaphore():   # der eine Platz ist belegt
            try:
                return await asyncio.wait_for(mod.moderate("x"), 2.0)
            except TimeoutError:
                return "wartet noch"

    assert asyncio.run(_lauf()) == {}


def test_ein_uebersprungener_lauf_nennt_den_grund(monkeypatch, caplog):
    """Im Log stand nur „moderation failed: “ — ``str(TimeoutError())`` ist leer."""
    monkeypatch.setattr(mod, "_moderation_target", lambda: ("https://b/openai", "k", None))
    monkeypatch.setattr(mod, "_MOD_TIMEOUT_SECONDS", 0.05)

    async def _schweigt(**kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(mod, "_amoderation", _schweigt)
    with caplog.at_level("WARNING", logger=mod.__name__):
        assert asyncio.run(mod.moderate("x")) == {}
    assert "moderation skipped" in caplog.text and "TimeoutError" in caplog.text


def test_target_academiccloud_without_openai_key_is_none(monkeypatch):
    monkeypatch.setattr(mod, "get_provider", lambda: "b-api-academiccloud")
    monkeypatch.setattr(mod, "get_settings", lambda: _settings())
    assert mod._moderation_target() is None


# ── moderate(): Parsing + Fail-Open ──────────────────────────────────────

class _Bag:
    """Objekt-Form mit ``model_dump()`` — die Form, die ALT vom nativen
    OpenAI-SDK bekam. Wird nur noch im Gegenprobe-Test benutzt, damit der
    tolerante Zweig in ``moderate()`` nicht ungeprüft bleibt."""

    def __init__(self, d):
        self._d = d

    def model_dump(self):
        return self._d


def _fake_moderation_response(*, flagged, categories, scores):
    """Gemessen am 2026-07-27 gegen omni-moderation-latest: ``results[0]`` ist
    ein **Objekt** (``OpenAIModerationResult``) — ``.flagged``/``.categories``/
    ``.category_scores`` tragen —, aber ``categories`` und ``category_scores``
    sind darin **plain dicts** ohne ``model_dump()``.

    Die frühere Attrappe legte hier ``_Bag`` hinein und war deshalb dauerhaft
    grün, während jeder echte Aufruf mit ``'dict' object has no attribute
    'model_dump'`` im Fail-Open landete: die Moderationsstufe war im Betrieb
    tot, ohne dass ein Test es merkte.
    """
    result = SimpleNamespace(
        flagged=flagged,
        categories=dict(categories),
        category_scores=dict(scores),
    )
    return SimpleNamespace(results=[result])


def test_moderate_also_parses_the_model_shape(monkeypatch):
    """Gegenprobe zur gemessenen dict-Form: liefert ein Anbieter Modelle mit
    ``model_dump()``, darf die Stufe nicht wieder still ausfallen. Ohne diesen
    Test wäre der tolerante Zweig ungeprüfter Vorratscode."""
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))

    async def _fake(**_kwargs):
        result = SimpleNamespace(
            flagged=True, categories=_Bag({"hate": True}), category_scores=_Bag({"hate": 0.9})
        )
        return SimpleNamespace(results=[result])

    monkeypatch.setattr(mod, "_amoderation", _fake)
    out = asyncio.run(mod.moderate("x"))
    assert out == {"flagged": True, "categories": {"hate": True}, "scores": {"hate": 0.9}}


def test_moderate_parses_flagged_categories_and_scores(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))

    async def _fake(**kwargs):
        assert kwargs["model"] == "omni-moderation-latest"
        return _fake_moderation_response(
            flagged=True,
            categories={"violence": True, "hate": False},
            scores={"violence": 0.9, "hate": 0.1},
        )

    monkeypatch.setattr(mod, "_amoderation", _fake)
    out = asyncio.run(mod.moderate("etwas gewalttätiges"))
    assert out["flagged"] is True
    assert out["categories"] == {"violence": True, "hate": False}
    assert out["scores"] == {"violence": 0.9, "hate": 0.1}


# ── Schreibweise der Kategorien (Befund 2026-09-27) ──────────────────────
# Die 13 Kategorien von omni-moderation-latest, wie die API sie nennt …
_API = {
    "harassment": 0.01, "harassment/threatening": 0.02, "hate": 0.03,
    "hate/threatening": 0.04, "illicit": 0.05, "illicit/violent": 0.06,
    "self-harm": 0.07, "self-harm/intent": 0.30, "self-harm/instructions": 0.09,
    "sexual": 0.10, "sexual/minors": 0.11, "violence": 0.12, "violence/graphic": 0.13,
}
# … wie das OpenAI-SDK sie als Feldnamen führt …
_SDK = {k.replace("-", "_").replace("/", "_"): v for k, v in _API.items()}
# … und was tatsächlich ankommt: BEIDES, 21 Schlüssel (golden-20260927-131857-
# e6b-an-3.json; das SDK legt die API-Namen neben den Feldnamen als Extras ab).
_GEMISCHT = {**_SDK, **_API}
# Die eine Schreibweise, die Seed und Code benutzen: API-Name, "_" statt "-".
_KANON = {k.replace("-", "_"): v for k, v in _API.items()}


@pytest.mark.parametrize("eingang", [_GEMISCHT, _API, _SDK],
                         ids=["gemischt-wie-gemessen", "api", "sdk"])
def test_moderate_fuehrt_jede_schreibweise_auf_die_des_seeds_zurueck(monkeypatch, eingang):
    """Der Seed prüft ``self_harm/intent`` (Schwelle 0,25, harte Kategorie). Die
    Moderation meldete ``self-harm/intent`` UND ``self_harm_intent`` — nie die
    Mischform. Also galt für Suizid-Absicht die Vorgabe 0,95, und die harte
    Kategorie griff nie. Gleich ist nicht genug: auch kein Duplikat darf
    bleiben, sonst zählt dieselbe Kategorie doppelt in Debug und Protokoll."""
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))

    async def _fake(**_kwargs):
        return _fake_moderation_response(
            flagged=True,
            categories={k: v >= 0.25 for k, v in eingang.items()},
            scores=eingang,
        )

    monkeypatch.setattr(mod, "_amoderation", _fake)
    out = asyncio.run(mod.moderate("x"))
    assert out["scores"] == _KANON
    assert out["categories"] == {k: v >= 0.25 for k, v in _KANON.items()}


def test_moderate_no_target_returns_empty(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target", lambda: None)
    assert asyncio.run(mod.moderate("x")) == {}


def test_moderate_error_returns_empty(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))

    async def _boom(**kwargs):
        raise RuntimeError("upstream 500")

    monkeypatch.setattr(mod, "_amoderation", _boom)
    assert asyncio.run(mod.moderate("x")) == {}


def test_moderate_haengt_nie_laenger_als_seine_frist(monkeypatch):
    # Audit 2026-09-29. ``litellm.amoderation`` baut seinen Client ohne
    # Zeitlimit (``httpx.Timeout(None)``). Ein Anbieter, der die Verbindung
    # annimmt und nie antwortet, hielt damit JEDEN Zug an — samt der
    # Sitzungssperre. Die Stufe ist fail-open: nach der Frist gilt ``{}``.
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))
    monkeypatch.setattr(mod, "_MOD_TIMEOUT_SECONDS", 0.05)

    async def _schweigt(**kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(mod, "_amoderation", _schweigt)

    async def _lauf():
        return await asyncio.wait_for(mod.moderate("x"), timeout=2.0)

    assert asyncio.run(_lauf()) == {}


def test_moderate_passes_b_api_headers(monkeypatch):
    monkeypatch.setattr(mod, "_moderation_target",
                        lambda: ("https://b-api.example/openai", "b-key", {"X-API-KEY": "b-key"}))
    seen = {}

    async def _fake(**kwargs):
        seen.update(kwargs)
        return _fake_moderation_response(flagged=False, categories={}, scores={})

    monkeypatch.setattr(mod, "_amoderation", _fake)
    asyncio.run(mod.moderate("x"))
    assert seen["api_base"] == "https://b-api.example/openai"
    assert seen["extra_headers"] == {"X-API-KEY": "b-key"}


# ── classify_legal(): Parsing + Fail-Open ────────────────────────────────

def test_classify_legal_parses_categories(monkeypatch):
    payload = ('{"strafrecht": {"risk": 0.8, "reason": "Bedrohung"},'
               ' "jugendschutz": {"risk": 0.0, "reason": ""},'
               ' "persoenlichkeitsrechte": {"risk": 0.1, "reason": ""},'
               ' "datenschutz": {"risk": 0.0, "reason": ""}}')

    async def _fake(**kwargs):
        msg = SimpleNamespace(content=payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    monkeypatch.setattr(legal_mod, "chat_completion", _fake)
    out = asyncio.run(legal_mod.classify_legal("ich bedrohe dich"))
    assert out["strafrecht"]["risk"] == 0.8
    assert out["strafrecht"]["reason"] == "Bedrohung"
    assert set(out) == {"strafrecht", "jugendschutz", "persoenlichkeitsrechte", "datenschutz"}


def test_classify_legal_error_returns_empty(monkeypatch):
    async def _boom(**kwargs):
        raise RuntimeError("no transport")

    monkeypatch.setattr(legal_mod, "chat_completion", _boom)
    assert asyncio.run(legal_mod.classify_legal("x")) == {}


# ── K1d: die Rechtsprüfung bucht ─────────────────────────────────────────

def test_classify_legal_reicht_den_merkposten_an_den_transport(monkeypatch):
    seen: dict = {}

    async def _fake(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    monkeypatch.setattr(legal_mod, "chat_completion", _fake)
    acc = new_accumulator()

    asyncio.run(legal_mod.classify_legal("x", usage_acc=acc))

    assert seen["usage_acc"] is acc
    assert seen["phase"] == "legal"


def test_zwei_gleichzeitige_rechtspruefungen_zaehlen_beide(monkeypatch):
    """Der Aufruf steckt in einem ``gather`` — mehrere Nebenläufige schreiben
    auf denselben Merkposten. ``add_usage`` ist eine reine Dict-Mutation ohne
    ``await``, unter asyncio also unteilbar. Der Test fährt es wirklich
    gleichzeitig, statt sich darauf zu verlassen."""
    async def _fake(**kwargs):
        await asyncio.sleep(0)          # erzwingt einen echten Aufgabenwechsel
        return SimpleNamespace(
            model="m",
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2,
                                  prompt_tokens_details=None,
                                  completion_tokens_details=None),
        )

    monkeypatch.setattr(legal_mod, "chat_completion", _real_transport_booking(_fake))
    acc = new_accumulator()

    async def _both():
        await asyncio.gather(
            legal_mod.classify_legal("a", usage_acc=acc),
            legal_mod.classify_legal("b", usage_acc=acc),
        )

    asyncio.run(_both())

    assert acc["calls"] == 2
    assert acc["per_phase"]["legal"]["prompt"] == 20


def _real_transport_booking(inner):
    """Attrappe MIT Buchung: bildet ab, was ``llm.chat_completion`` tut, statt
    die Buchung wegzumocken — sonst prüfte der Nebenläufigkeitstest nichts."""
    from boerdi.obs.usage import add_usage, extract_usage

    async def _wrapped(**kwargs):
        resp = await inner(**kwargs)
        add_usage(kwargs.get("usage_acc"), extract_usage(resp), kwargs.get("phase"))
        return resp

    return _wrapped
