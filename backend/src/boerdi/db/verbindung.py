"""Die Verbindung eines Zugs vor LLM und MCP freigeben (Paket 19, Audit 2026-10-31, H-5).

Ein Zug teilt EINE ``AsyncSession``. Jede Abfrage öffnet darin eine Transaktion; die
Schreibwege schließen sie selbst (``update_session``, ``save_message`` … committen), die
Lesewege nicht. Bis hier stand die Verbindung deshalb nach dem Gedächtnis-Lesen in
``assess`` „idle in transaction“ — über Klassifikation, Werkzeuge und Antwort hinweg bis
``persist``. Mit Pool 5 + 10 wartete schon der 16. gleichzeitige Zug einer Kopie 30 s.

:func:`verbindung_freigeben` schließt eine offene Lese-Transaktion mit ``commit()``: die
Verbindung geht in den Pool zurück, und die gelesenen ORM-Objekte bleiben gültig
(``expire_on_commit=False``, ``db/session.make_session_factory``). ``rollback()`` wäre
falsch — er verwirft den Zustand aller geladenen Objekte, und das nächste Lesen eines
Attributs liefe im async-Betrieb in ``MissingGreenlet``.

Aufgerufen an den Nähten, an denen danach ein LLM- oder MCP-Abschnitt folgt: zwischen den
Knoten des Zug-Graphen (``graph/build``), nach dem Gedächtnis-Lesen in ``assess``, vor der
Zustimmungs-Prüfung in ``setup``, nach den RAG-Abfragen (``rag/retrieval``) und vor der
Einbettung beim Import (``rag/ingest``).
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def verbindung_freigeben(session: object) -> None:
    """Eine offene Transaktion von ``session`` abschließen; wirft nie.

    Nur für eine echte :class:`AsyncSession` — Attrappen der Knoten-Tests (``object()``,
    ``MagicMock``) bleiben unberührt. Scheitert der Abschluss (Verbindung weg), wird
    zurückgerollt: die Sitzung bleibt für die Schreibwege des Zugs nutzbar.
    """
    if not isinstance(session, AsyncSession):
        return
    offen = (len(session.new), len(session.dirty), len(session.deleted))
    if not session.in_transaction() and not any(offen):
        return
    if any(offen):
        # Review 19-4: hier sollen nur Lese-Transaktionen enden — die Schreibwege des Zugs
        # committen selbst. Ein künftiger Weg ohne eigenen Commit fiele sonst nicht auf.
        # Nur Zahlen, kein Inhalt.
        logger.warning("Verbindung des Zugs: %d neue, %d geänderte, %d gelöschte Objekte "
                       "ohne eigenen Commit — die Freigabe schreibt sie fest", *offen)
    try:
        await session.commit()
    except Exception:  # noqa: BLE001 — eine Freigabe darf den Zug nie beenden
        logger.debug("Verbindung des Zugs: Abschluss gescheitert, rolle zurück", exc_info=True)
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            logger.debug("Verbindung des Zugs: auch der Rollback scheiterte", exc_info=True)
