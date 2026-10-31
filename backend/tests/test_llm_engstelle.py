"""Paket 18F, Aufgaben 3.1 und 3.2: die LLM-Engstelle ``services/llm_parallel.platz``.

3.1 — Weist der Anbieter den Schlüssel ab (401), sagt das eine Logzeile mit Anbieter, Route und
Quelle des Schlüssels (nie der Schlüssel, nie der Text des Anbieters), gedrosselt je Minute, und
ein Zähler steigt. Erkannt auch, wenn instructor (Klassifikator) die 401 verpackt.

3.2 — Wartet ein Chat-Aufruf länger als ``LLM_SLOT_WAIT_S`` auf einen Platz, gilt der Zug als
ausgelastet: dieser Aufruf scheitert, jeder weitere desselben Zugs sofort. Andere Züge warten
normal; Hintergrund und Import haben keine Frist.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging

import litellm
import pytest
from instructor.core.exceptions import FailedAttempt, InstructorRetryException

from boerdi.obs import drossel, metrics
from boerdi.services import llm, llm_auth, llm_parallel
from boerdi.settings import get_settings

GEHEIM = "sk-GEHEIM-0123456789"


@pytest.fixture(autouse=True)
def _frisch(monkeypatch):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    llm_parallel.reset()
    llm_auth.setze_llm_schluessel(None)
    yield
    llm_parallel.reset()
    llm_auth.setze_llm_schluessel(None)
    get_settings.cache_clear()


def _abgelehnt() -> litellm.AuthenticationError:
    return litellm.AuthenticationError(
        message=f"OpenAIException - Incorrect API key provided: {GEHEIM}",
        llm_provider="openai", model="gpt-x")


def _zaehler(anbieter: str, quelle: str) -> float:
    return metrics.LLM_SCHLUESSEL_ABGELEHNT.labels(anbieter, quelle)._value.get()


async def _im_platz(fehler: BaseException, kanal: str = "live") -> None:
    with pytest.raises(type(fehler)):
        async with llm_parallel.platz(kanal):
            raise fehler


def _zeilen(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "llm_schluessel_abgelehnt" in r.getMessage()]


# ── 3.1 abgelehnter Schlüssel ──────────────────────────────────────────────────

def test_401_meldet_anbieter_route_und_quelle_ohne_schluessel(caplog):
    vorher = _zaehler("openai", "openai_api_key")
    with caplog.at_level(logging.WARNING):
        asyncio.run(_im_platz(_abgelehnt()))

    zeilen = _zeilen(caplog)
    assert len(zeilen) == 1
    assert zeilen[0].levelno == logging.ERROR  # der eigene Schlüssel: Betrieb muss handeln
    text = zeilen[0].getMessage()
    assert "anbieter=openai" in text and "quelle=openai_api_key" in text and "route=" in text
    assert GEHEIM not in caplog.text and "Incorrect API key" not in caplog.text
    assert _zaehler("openai", "openai_api_key") == vorher + 1


def test_weitergereichter_schluessel_ist_eine_warnung(monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    llm_auth.setze_llm_schluessel("Bearer abcdefgh-1234-weitergereicht")

    with caplog.at_level(logging.WARNING):
        asyncio.run(_im_platz(_abgelehnt()))

    zeilen = _zeilen(caplog)
    assert len(zeilen) == 1 and zeilen[0].levelno == logging.WARNING
    assert "quelle=weitergereicht" in zeilen[0].getMessage()
    assert "abcdefgh" not in caplog.text


def test_b_api_ohne_weitergereichten_schluessel(monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()

    with caplog.at_level(logging.WARNING):
        asyncio.run(_im_platz(_abgelehnt()))

    zeilen = _zeilen(caplog)
    assert len(zeilen) == 1 and zeilen[0].levelno == logging.ERROR
    assert "anbieter=b-api-openai" in zeilen[0].getMessage()
    assert "quelle=b_api_key" in zeilen[0].getMessage()


def test_gedrosselt_je_minute_mit_zahl_der_ausgelassenen(monkeypatch, caplog):
    jetzt = [1000.0]
    monkeypatch.setattr(drossel, "_uhr", lambda: jetzt[0])
    vorher = _zaehler("openai", "openai_api_key")

    with caplog.at_level(logging.WARNING):
        asyncio.run(_im_platz(_abgelehnt()))
        asyncio.run(_im_platz(_abgelehnt()))
        jetzt[0] += 61
        asyncio.run(_im_platz(_abgelehnt()))

    zeilen = [z.getMessage() for z in _zeilen(caplog)]
    assert len(zeilen) == 2
    assert "1 gleiche Meldungen ausgelassen" in zeilen[1]
    assert _zaehler("openai", "openai_api_key") == vorher + 3  # der Zähler zählt jede


def test_von_instructor_verpackte_401_wird_erkannt(caplog):
    verpackt = InstructorRetryException(
        "Max retries exceeded", n_attempts=1, total_usage=0,
        failed_attempts=[FailedAttempt(attempt_number=1, exception=_abgelehnt())])

    with caplog.at_level(logging.WARNING):
        asyncio.run(_im_platz(verpackt))

    assert len(_zeilen(caplog)) == 1


def test_verkettete_401_wird_erkannt(caplog):
    try:
        raise _abgelehnt()
    except litellm.AuthenticationError as ursache:
        fehler = RuntimeError("Aufruf gescheitert")
        fehler.__cause__ = ursache

    with caplog.at_level(logging.WARNING):
        asyncio.run(_im_platz(fehler))

    assert len(_zeilen(caplog)) == 1


def test_andere_fehler_melden_keinen_schluessel(caplog):
    fehler = litellm.BadRequestError(message="Invalid value", llm_provider="openai", model="x")
    with caplog.at_level(logging.WARNING):
        asyncio.run(_im_platz(fehler))
    assert _zeilen(caplog) == []


def test_klassifikator_und_strom_gehen_ueber_dieselbe_engstelle(caplog):
    """``llm.semaphore()`` (Klassifikator, Strom) ist jetzt ``platz("live")``."""
    async def lauf() -> None:
        with pytest.raises(litellm.AuthenticationError):
            async with llm.semaphore():
                raise _abgelehnt()

    with caplog.at_level(logging.WARNING):
        asyncio.run(lauf())
    assert len(_zeilen(caplog)) == 1


# ── 3.2 Frist beim Platz, Zug-Merker ──────────────────────────────────────────

async def _belegt(n: int = 2) -> asyncio.Semaphore:
    sem = llm_parallel._semaphore("live")
    for _ in range(n):
        await sem.acquire()
    return sem


def test_frist_laeuft_ab_dann_wartet_der_zug_nicht_mehr(monkeypatch, caplog):
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "0.1")
    get_settings.cache_clear()
    vorher = metrics.LLM_PLATZ_FRIST._value.get()

    async def lauf() -> tuple[float, float]:
        await _belegt()
        llm_parallel.binde_zug()
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        with pytest.raises(llm_parallel.LlmAusgelastet):
            async with llm_parallel.platz("live"):
                pass
        erste = loop.time() - t0
        assert llm_parallel.ausgelastet()
        t1 = loop.time()                  # weiter kein Platz frei: sofort, ohne zweite Frist
        with pytest.raises(llm_parallel.LlmAusgelastet):
            async with llm_parallel.platz("live"):
                pass
        return erste, loop.time() - t1

    with caplog.at_level(logging.WARNING):
        erste, zweite = asyncio.run(lauf())

    # asyncio darf einen Timer um die Taktauflösung früher auslösen (Windows: 15,6 ms).
    assert 0.07 <= erste < 1.0
    assert zweite < 0.05
    assert metrics.LLM_PLATZ_FRIST._value.get() == vorher + 1
    assert any("llm_platz_frist" in r.getMessage() for r in caplog.records)


def test_ein_anderer_zug_wartet_normal(monkeypatch):
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "0.1")
    get_settings.cache_clear()

    async def lauf() -> bool:
        sem = await _belegt()
        llm_parallel.binde_zug()
        with pytest.raises(llm_parallel.LlmAusgelastet):
            async with llm_parallel.platz("live"):
                pass

        async def anderer_zug() -> bool:
            llm_parallel.binde_zug()
            async with llm_parallel.platz("live"):
                return llm_parallel.ausgelastet()

        sem.release()
        return await asyncio.create_task(anderer_zug(), context=contextvars.Context())

    assert asyncio.run(lauf()) is False


def test_frist_null_heisst_ohne_grenze(monkeypatch):
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "0")
    get_settings.cache_clear()

    async def lauf() -> None:
        await _belegt()
        llm_parallel.binde_zug()

        async def nehmen() -> None:
            async with llm_parallel.platz("live"):
                pass

        with pytest.raises(TimeoutError):  # wartet weiter — kein LlmAusgelastet
            await asyncio.wait_for(nehmen(), 0.3)

    asyncio.run(lauf())


@pytest.mark.parametrize("kanal", ["bg", "ingest"])
def test_hintergrund_und_import_ohne_frist(monkeypatch, kanal):
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "0.05")
    get_settings.cache_clear()

    async def lauf() -> None:
        await _belegt()

        async def nehmen() -> None:
            async with llm_parallel.platz(kanal):
                pass

        with pytest.raises(TimeoutError):
            await asyncio.wait_for(nehmen(), 0.3)

    asyncio.run(lauf())


def test_vorgabe_dreissig_sekunden():
    assert get_settings().llm_slot_wait_s == 30.0


def test_ohne_gebundenen_zug_scheitert_nur_der_eine_aufruf(monkeypatch):
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "0.05")
    get_settings.cache_clear()

    async def lauf() -> bool:
        await _belegt()
        with pytest.raises(llm_parallel.LlmAusgelastet):
            async with llm_parallel.platz("live"):
                pass
        return llm_parallel.ausgelastet()

    assert asyncio.run(lauf()) is False


def test_platz_wird_nach_dem_aufruf_freigegeben():
    async def lauf() -> int:
        async with llm_parallel.platz("live"):
            pass
        with pytest.raises(RuntimeError):
            async with llm_parallel.platz("live"):
                raise RuntimeError("kaputt")
        return llm_parallel._semaphore("live")._value

    assert asyncio.run(lauf()) == 2


def test_ein_ausgelasteter_zug_nimmt_einen_freien_platz(monkeypatch):
    """Review 2026-10-30: verboten ist nur das Warten. Scheiterte erst ein Nebenaufruf an der
    Frist, bräche sonst die Werkzeugschleife in Runde 2 ab, obwohl ein Platz frei ist."""
    monkeypatch.setenv("LLM_SLOT_WAIT_S", "0.1")
    get_settings.cache_clear()

    async def lauf() -> tuple[bool, int]:
        sem = await _belegt()
        llm_parallel.binde_zug()
        with pytest.raises(llm_parallel.LlmAusgelastet):
            async with llm_parallel.platz("live"):
                pass
        sem.release()                     # ein Platz wird frei
        async with llm_parallel.platz("live"):
            belegt_drinnen = sem.locked()
        assert llm_parallel.ausgelastet()  # der Merker bleibt — er sagt, was geschah
        return belegt_drinnen, sem._value

    belegt_drinnen, frei_danach = asyncio.run(lauf())
    assert belegt_drinnen is True        # der Platz war genommen …
    assert frei_danach == 1              # … und ist wieder frei


def test_die_labelreihen_des_schluesselzaehlers_stehen_von_anfang_an():
    """Review 2026-10-30: ``increase()`` sieht den ersten 401 nur auf einer bestehenden Reihe."""
    from boerdi.services import llm_ereignisse  # noqa: F401 — belegt die Reihen beim Import

    reihen = {tuple(s.labels.values()) for m in metrics.LLM_SCHLUESSEL_ABGELEHNT.collect()
              for s in m.samples if s.name.endswith("_total")}
    assert {("openai", "openai_api_key"), ("b-api-openai", "b_api_key"),
            ("b-api-openai", "weitergereicht"), ("b-api-academiccloud", "b_api_key"),
            ("b-api-academiccloud", "weitergereicht")} <= reihen



def test_der_rag_vorabruf_meldet_last_ohne_warnung(monkeypatch, caplog):
    """Review 2026-10-30: je ausgelastetem Zug stand dort eine WARNING."""
    from boerdi.services.rag import vorab

    async def kein_platz(*_a, **_k):
        raise llm_parallel.LlmAusgelastet("kein LLM-Platz binnen 30 s")

    monkeypatch.setattr(vorab, "embed_backend", lambda: "remote")
    monkeypatch.setattr(vorab, "load_rag_config", lambda: {"a": {"mode": "always"}})
    monkeypatch.setattr(vorab, "embed_text", kein_platz)
    with caplog.at_level(logging.INFO):
        assert asyncio.run(vorab.rag_einbettung_vorab("Optik")) is None
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# ── Paket 19 (N-16, Review): was als vorübergehender Anbieterfehler gilt ─────


def _von_litellm_abgebildet(original: BaseException) -> BaseException:
    """Wie im Betrieb: LiteLLM bildet jede Ausnahme ohne HTTP-Status auf
    ``APIConnectionError`` ab, das Original steht nur in ``__context__``."""
    from litellm.litellm_core_utils.exception_mapping_utils import exception_type

    try:
        try:
            raise original
        except Exception as o:  # noqa: BLE001 — die Abbildung nimmt jede Ausnahme
            exception_type(model="gpt-4o", original_exception=o, custom_llm_provider="openai")
    except Exception as e:  # noqa: BLE001
        return e
    raise AssertionError("exception_type warf nicht")


def test_ein_programmfehler_hinter_litellm_ist_nicht_voruebergehend():
    from boerdi.services.llm_ereignisse import ist_voruebergehend

    fehler = _von_litellm_abgebildet(TypeError("'NoneType' object is not subscriptable"))
    assert isinstance(fehler, litellm.APIConnectionError)
    assert not ist_voruebergehend(fehler)


def test_ein_netzfehler_hinter_litellm_ist_voruebergehend():
    import httpx

    from boerdi.services.llm_ereignisse import ist_voruebergehend

    assert ist_voruebergehend(_von_litellm_abgebildet(httpx.ConnectError("refused")))
    assert ist_voruebergehend(_von_litellm_abgebildet(ConnectionResetError("reset")))


def test_frist_und_ratenlimit_sind_voruebergehend():
    from boerdi.services.llm_ereignisse import LlmFristAbgelaufen, ist_voruebergehend

    assert ist_voruebergehend(litellm.Timeout(message="t", model="m", llm_provider="openai"))
    assert ist_voruebergehend(litellm.RateLimitError(message="429", model="m",
                                                     llm_provider="openai"))
    assert ist_voruebergehend(LlmFristAbgelaufen("keine Antwort binnen 8 s"))


def test_ein_fremder_timeouterror_ist_nicht_voruebergehend():
    """Etwa asyncpg ``command_timeout`` aus der RAG-Abfrage — kein Anbieterfehler."""
    from boerdi.services.llm_ereignisse import ist_voruebergehend

    assert not ist_voruebergehend(TimeoutError())
