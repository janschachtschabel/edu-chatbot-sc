"""Das Reranker-Modell selbst beziehen (Nutzer-Entscheid 2026-10-15).

Das Modell liegt weder im Repository noch im Image. Ist ``RAG_RERANKER_ENABLED`` an und fehlt es,
lädt das Backend es beim Start im Hintergrund — ohne Handgriff:

- **Quelle fest gepinnt:** die offizielle int8-ONNX-Datei des Herausgebers
  (``cross-encoder/mmarco-mMiniLMv2-L12-H384-v1``, Apache-2.0) auf Hugging Face, an einem festen
  Commit; Größe und SHA-256 je Datei stehen hier. Eine geänderte Datei auf der Gegenseite wird
  abgewiesen, nicht geladen.
- **Atomar:** geladen wird in ein verstecktes Zwischenverzeichnis, erst nach bestandener Prüfung
  umbenannt. Ein abgebrochener Lauf hinterlässt kein halbes Modell.
- **Eine Kopie lädt:** mehrere Backend-Kopien teilen sich das Volume; eine Sperrdatei hält die
  anderen zurück, sie warten auf das Ergebnis.
- **Bis dahin rechnet nichts damit:** ``rerank._get_reranker`` liefert ``None`` (Suche nach
  Einbettung, Karten ohne Gate). Danach wird sein Cache geleert — das Modell greift ohne Neustart.

Gescheitert (Netz, Prüfwert, Platte) meldet ``/api/health`` ``download-failed``; der nächste Start
versucht es erneut. Server ohne Internet setzen ``RERANK_AUTO_DOWNLOAD=false`` und legen das Modell
von Hand ab (``INSTALL.md``).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import socket
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from boerdi.services.rag import rerank
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

REVISION = "1427fd652930e4ba29e8149678df786c240d8825"
QUELLE = ("https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/resolve/"
          + REVISION)
SLUG = rerank.HF_SLUG


@dataclass(frozen=True)
class Datei:
    pfad: str  # unter QUELLE
    name: str  # im Modellverzeichnis
    groesse: int
    sha256: str


#: Geprüft am 2026-10-15 gegen die Hugging-Face-API (LFS-Prüfwerte) und nach dem Laden.
DATEIEN: tuple[Datei, ...] = (
    Datei("onnx/model_quint8_avx2.onnx", "model_quint8_avx2.onnx", 118_620_016,
          "6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b"),
    Datei("tokenizer.json", "tokenizer.json", 17_082_660,
          "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626"),
)

SPERRE = ".reranker-download.lock"
#: Ohne Lebenszeichen gilt eine Sperre so lange als „jemand lädt gerade“. Ein laufender Download
#: erneuert sie alle :data:`LEBENSZEICHEN_S` — deshalb darf die Frist kurz sein: ein abgebrochener
#: Lauf (Container neu erstellt, OOM) hält den nächsten Start nur Minuten auf.
SPERRE_GILT_S = 300
LEBENSZEICHEN_S = 30.0
#: Längste Ladezeit je Datei. Die Lese-Frist von httpx gilt je Stück — ein tröpfelnder Strom
#: unterliefe sie und hielte die Sperre ewig.
FRIST_JE_DATEI_S = 900.0
#: Wie oft eine wartende Kopie nachsieht, ob das Modell da ist.
WARTE_TAKT_S = 10.0

_client_fabrik = httpx.Client
#: ``""`` · ``"downloading"`` · ``"download-failed"`` — für ``rerank.reranker_status``.
_zustand = ""


def zustand() -> str:
    return _zustand


def _inhalt(pfad: Path) -> str | None:
    try:
        return pfad.read_text()
    except OSError:
        return None


def _alter(pfad: Path) -> float | None:
    try:
        return time.time() - pfad.stat().st_mtime
    except OSError:
        return None


def _vollstaendig(ziel: Path) -> bool:
    return ziel.is_dir() and any(ziel.glob("*.onnx"))


def _sperr_kennung() -> str:
    """Eindeutig je Versuch. Die Prozessnummer allein taugt nicht: im Container ist sie in
    jeder Kopie dieselbe (uvicorn läuft als PID 1)."""
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex}"


def _sperre_nehmen(basis: Path, kennung: str) -> bool:
    pfad = basis / SPERRE
    for _ in range(2):
        try:
            fd = os.open(pfad, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            alter = _alter(pfad)
            if alter is not None and alter < SPERRE_GILT_S:
                return False
            pfad.unlink(missing_ok=True)  # verwaist (kein Lebenszeichen) oder gerade weg
            continue
        os.write(fd, kennung.encode())
        os.close(fd)
        return True
    return False


def _lebenszeichen(pfad: Path, kennung: str) -> None:
    """Die eigene Sperre auffrischen — nie eine fremde."""
    if _inhalt(pfad) == kennung:
        os.utime(pfad)


def _laden(client: httpx.Client, datei: Datei, ziel: Path, puls: Callable[[], None]) -> None:
    pruef = hashlib.sha256()
    gelesen = 0
    frist = time.monotonic() + FRIST_JE_DATEI_S
    with client.stream("GET", f"{QUELLE}/{datei.pfad}") as antwort:
        antwort.raise_for_status()
        with ziel.open("wb") as aus:
            for stueck in antwort.iter_bytes(1 << 20):
                if time.monotonic() >= frist:
                    raise TimeoutError(f"{datei.pfad}: Gesamtfrist überschritten")
                gelesen += len(stueck)
                if gelesen > datei.groesse:
                    raise ValueError(f"{datei.pfad}: größer als erwartet")
                pruef.update(stueck)
                aus.write(stueck)
                puls()
    if gelesen != datei.groesse or pruef.hexdigest() != datei.sha256:
        raise ValueError(f"{datei.pfad}: Größe oder Prüfwert stimmt nicht")


def beziehen(basis: Path, *, client_fabrik=None) -> bool:
    """Das Modell nach ``basis/SLUG`` laden. ``True``, wenn es danach da ist.

    ``False`` heißt: gescheitert (auch ein nicht beschreibbares Verzeichnis) oder eine andere
    Kopie lädt gerade (Sperre).
    """
    ziel = basis / SLUG
    if _vollstaendig(ziel):
        return True
    kennung = _sperr_kennung()
    sperre = basis / SPERRE
    zwischen: Path | None = None
    letzter_puls = [0.0]

    def puls() -> None:
        jetzt = time.monotonic()
        if jetzt - letzter_puls[0] >= LEBENSZEICHEN_S:
            letzter_puls[0] = jetzt
            _lebenszeichen(sperre, kennung)

    try:
        basis.mkdir(parents=True, exist_ok=True)
        if not _sperre_nehmen(basis, kennung):
            logger.info("Reranker-Modell: eine andere Kopie lädt gerade (%s)", SPERRE)
            return False
        # Eigenes Zwischenverzeichnis je Versuch — zwei Kopien schreiben nie in dasselbe.
        zwischen = Path(tempfile.mkdtemp(prefix=f".{SLUG}.tmp-", dir=basis))
        fabrik = client_fabrik or _client_fabrik
        with fabrik(timeout=httpx.Timeout(60.0, connect=15.0), follow_redirects=True) as client:
            for datei in DATEIEN:
                _laden(client, datei, zwischen / datei.name, puls)
        if not _vollstaendig(ziel):
            # Ein unvollständiger Rest (etwa eine halbe Handkopie) stünde dem Umbenennen im Weg.
            shutil.rmtree(ziel, ignore_errors=True)
            os.replace(zwischen, ziel)
        logger.info("Reranker-Modell bezogen: %s (Revision %s)", ziel, REVISION[:7])
        return True
    except Exception as fehler:  # noqa: BLE001 — Bezug ist optional, Status meldet es
        logger.warning("Reranker-Modell nicht bezogen (%s) — Suche ohne Reranker", fehler)
        return False
    finally:
        if zwischen is not None:
            shutil.rmtree(zwischen, ignore_errors=True)
        if _inhalt(sperre) == kennung:
            sperre.unlink(missing_ok=True)


async def _warten_auf_andere(ziel: Path, basis: Path) -> bool:
    """Eine andere Kopie lädt: warten, bis das Modell da ist.

    Lebt sie, frischt sie ihre Sperre auf. Bleibt das Lebenszeichen länger als
    :data:`SPERRE_GILT_S` aus (Absturz) oder verschwindet die Sperre ohne Modell, lädt diese
    Kopie selbst — ``beziehen`` übernimmt eine verwaiste Sperre.
    """
    sperre = basis / SPERRE
    while True:
        if _vollstaendig(ziel):
            return True
        alter = _alter(sperre)
        if alter is None or alter >= SPERRE_GILT_S:
            if await asyncio.to_thread(beziehen, basis):
                return True
            if _alter(sperre) is None:
                return False  # selbst gescheitert, und niemand lädt
        await asyncio.sleep(WARTE_TAKT_S)


async def bereitstellen() -> None:
    """Beim Start: eingeschaltet, Selbstbezug erlaubt und Modell fehlt → beziehen, freischalten.

    Jeder Fehler endet in ``download-failed`` — nie in einem ``downloading``, das stehen bleibt.
    """
    global _zustand
    if (not rerank._reranker_enabled_via_env() or not get_settings().rerank_auto_download
            or rerank._reranker_model_dir()):
        return
    basis = rerank.modell_basis()
    ziel = basis / SLUG
    _zustand = "downloading"
    logger.info("Reranker eingeschaltet, Modell fehlt — beziehe es von Hugging Face")
    try:
        ok = await asyncio.to_thread(beziehen, basis)
        if not ok:
            # Eine andere Kopie kann zwischen ihrer Sperre und dieser Zeile fertig geworden sein.
            ok = _vollstaendig(ziel) or (
                _alter(basis / SPERRE) is not None and await _warten_auf_andere(ziel, basis))
    except Exception:  # noqa: BLE001 — der Status muss es sagen, nicht ein toter Task
        logger.warning("Reranker-Modell: Bezug abgebrochen", exc_info=True)
        ok = False
    if not ok:
        _zustand = "download-failed"
        return
    _zustand = ""
    rerank._get_reranker.cache_clear()
    try:
        await rerank.run_in_rerank_pool(rerank.warm_reranker)
    except Exception:  # noqa: BLE001 — das Modell liegt da; der erste Zug lädt es ohnehin
        logger.warning("Reranker-Modell bezogen, Vorwärmen gescheitert", exc_info=True)
