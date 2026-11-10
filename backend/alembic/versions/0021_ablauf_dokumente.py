"""0021 — der Ablauf-Katalog wird ein Dokument je Ablauf (Paket AS-0, Plan 2026-11-09).

Bis AS-0 lagen alle Abläufe als Liste im Bereich ``06-ablaeufe/katalog``. Jetzt ist ``06-ablaeufe``
ein Ordner wie die Muster: je Ablauf ``06-ablaeufe/<id>``. Diese Migration teilt eine vorhandene
Katalog-Zeile auf, ohne etwas zu verlieren oder Angepasstes zu überschreiben:

- **unberührt** (Inhalt gleicht der gemerkten Werksfassung, ``werk_hash``): jeder Ablauf merkt sich
  seine eigene Prüfsumme als Basis — der Werksabgleich gleicht ihn danach wie gewohnt ab;
- **angepasst oder ohne Basis**: kein ``werk_hash`` — der Ablauf gilt als eigen (Status
  ``eigen-neues-werk`` oder ``werk``) und wird nie überschrieben;
- eine **stillgelegte eigene Fassung** wird je Kennung mit aufgeteilt (Kennungen, die es nur dort
  gab, fallen weg — sie stehen weiter in ``config_history`` des Katalogs);
- ein im Studio **gelöschter** Katalog (``config_werk_entfernt``) oder ein Katalog **ohne** den
  Werks-Ablauf ``sammlungsstruktur`` (die Redaktion hatte ihn entfernt): der Werks-Ablauf bekommt
  seinen eigenen Löschvermerk — sonst legte ihn der nächste Werksabgleich wieder an;
- **aus dem Werk importiert, ohne Basis** (Bestand vor Paket 12, ``updated_by`` ein Werksweg):
  die Abläufe behalten diesen ``updated_by`` — sie bleiben so „werk-veraltet“ und werden angehoben.

Es entstehen nur Dokumente mit gültiger Kennung (Form des Treibers, nicht ``katalog``), und nur,
wo es noch keines gibt. ``updated_by`` ist ``migration-0021`` (keine Kennung der Werkswege: ohne
Basis gilt ein Ablauf so als eigen). Der NOTIFY-Trigger aus 0003 meldet jede Änderung.

``downgrade`` setzt aus allen ``06-ablaeufe/<id>`` wieder einen Katalog zusammen (nach Kennung
sortiert, ohne Basis und ohne stillgelegte Fassungen — der Rückweg ist ein Notweg) und entfernt die
Einzeldokumente. Einen Löschvermerk des Katalogs setzt er nur, wenn es keinen Ablauf mehr gibt.

Offline (``alembic upgrade --sql``) schreibt die Migration nur einen Hinweis: die Prüfsummen lassen
sich nicht als festes SQL ausgeben, sie braucht die Daten.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-09
"""

import hashlib
import json
import re

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

_KATALOG = "06-ablaeufe/katalog"
_ORDNER = "06-ablaeufe/"
_ID = re.compile(r"[a-z][a-z0-9_]{0,39}")
_WERKS_ABLAEUFE = ("sammlungsstruktur",)
_VON = "migration-0021"
#: Wie ``services.werkfassung.AUS_DEM_WERK`` (abgeschrieben, s. ``_pruefsumme``).
_AUS_DEM_WERK = frozenset({"import", "seed-apply", "seed-apply-cli", "werksabgleich"})


def _pruefsumme(data: object) -> str:
    """Wie ``services.werkfassung.pruefsumme`` — hier abgeschrieben, damit die Migration nicht vom
    Anwendungscode abhängt, der sich später ändern kann."""
    kanonisch = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(kanonisch.encode("utf-8")).hexdigest()


def _ablaeufe(data: object) -> dict[str, dict]:
    """Die Einträge eines Katalogs mit gültiger Kennung, Kennung → Eintrag (der erste gewinnt)."""
    liste = data.get("ablaeufe") if isinstance(data, dict) else None
    ergebnis: dict[str, dict] = {}
    for eintrag in liste if isinstance(liste, list) else []:
        kennung = eintrag.get("id") if isinstance(eintrag, dict) else None
        if (isinstance(kennung, str) and _ID.fullmatch(kennung) and kennung != "katalog"
                and kennung not in ergebnis):
            ergebnis[kennung] = eintrag
    return ergebnis


def _offline() -> bool:
    if op.get_context().as_sql:
        op.execute("-- 0021: Daten-Migration (Ablauf-Katalog -> Dokumente) laeuft nur online")
        return True
    return False


def upgrade() -> None:
    if _offline():
        return
    conn = op.get_bind()
    zeile = conn.execute(sa.text(
        "SELECT data::text AS data, werk_hash, eigene_fassung::text AS eigene, updated_by "
        "FROM config_areas WHERE area = :a"), {"a": _KATALOG}).mappings().first()
    entfernt: set[str] = set()
    if zeile is not None:
        data = json.loads(zeile["data"])
        unberuehrt = zeile["werk_hash"] is not None and zeile["werk_hash"] == _pruefsumme(data)
        von = (zeile["updated_by"] if zeile["werk_hash"] is None
               and zeile["updated_by"] in _AUS_DEM_WERK else _VON)
        still = _ablaeufe(json.loads(zeile["eigene"])) if zeile["eigene"] else {}
        vorhanden = {r[0] for r in conn.execute(sa.text(
            "SELECT area FROM config_areas WHERE area LIKE '06-ablaeufe/%'"))}
        ablaeufe = _ablaeufe(data)
        if verworfen := sorted(set(still) - set(ablaeufe)):
            # Querschnitts-Review AS-0…AS-2: nicht still — der Betrieb holt sie bei Bedarf aus
            # ``config_history`` des Katalogs
            print(f"0021: nur in der stillgelegten eigenen Fassung, nicht übernommen "
                  f"(stehen in config_history von {_KATALOG}): {', '.join(verworfen)}")
        entfernt = {k for k in _WERKS_ABLAEUFE if k not in ablaeufe}
        for kennung, ablauf in ablaeufe.items():
            key = _ORDNER + kennung
            if key in vorhanden:
                continue
            eigene = still.get(kennung)
            conn.execute(sa.text(
                "INSERT INTO config_areas (area, data, version, updated_by, werk_hash, "
                "eigene_fassung) VALUES (:a, CAST(:d AS jsonb), 1, :von, :w, CAST(:e AS jsonb))"),
                {"a": key, "d": json.dumps(ablauf, ensure_ascii=False), "von": von,
                 "w": _pruefsumme(ablauf) if unberuehrt else None,
                 "e": json.dumps(eigene, ensure_ascii=False)
                 if eigene is not None and eigene != ablauf else None})
        conn.execute(sa.text("DELETE FROM config_areas WHERE area = :a"), {"a": _KATALOG})
    if conn.execute(sa.text("SELECT 1 FROM config_werk_entfernt WHERE area = :a"),
                    {"a": _KATALOG}).first():
        entfernt = set(_WERKS_ABLAEUFE)
        conn.execute(sa.text("DELETE FROM config_werk_entfernt WHERE area = :a"),
                     {"a": _KATALOG})
    for kennung in sorted(entfernt):
        conn.execute(sa.text(
            "INSERT INTO config_werk_entfernt (area) VALUES (:a) ON CONFLICT DO NOTHING"),
            {"a": _ORDNER + kennung})


def downgrade() -> None:
    if _offline():
        return
    conn = op.get_bind()
    zeilen = conn.execute(sa.text(
        "SELECT area, data::text AS data FROM config_areas "
        "WHERE area LIKE '06-ablaeufe/%' AND area <> :k ORDER BY area"), {"k": _KATALOG}).all()
    if zeilen:
        katalog = {"ablaeufe": [json.loads(z.data) for z in zeilen]}
        conn.execute(sa.text(
            "INSERT INTO config_areas (area, data, version, updated_by) "
            "VALUES (:a, CAST(:d AS jsonb), 1, :von) "
            "ON CONFLICT (area) DO UPDATE SET data = EXCLUDED.data, "
            "updated_by = EXCLUDED.updated_by"),
            {"a": _KATALOG, "d": json.dumps(katalog, ensure_ascii=False), "von": _VON + "-down"})
        conn.execute(sa.text(
            "DELETE FROM config_areas WHERE area LIKE '06-ablaeufe/%' AND area <> :k"),
            {"k": _KATALOG})
    vermerkt = conn.execute(sa.text(
        "DELETE FROM config_werk_entfernt WHERE area LIKE '06-ablaeufe/%' RETURNING area")).all()
    if vermerkt and not zeilen:
        conn.execute(sa.text(
            "INSERT INTO config_werk_entfernt (area) VALUES (:a) ON CONFLICT DO NOTHING"),
            {"a": _KATALOG})
