# Paket Q3: Vorgang — Befunde des Querschnitts-Reviews (2026-11-06)

Grundlage: [`../audits/2026-11-06-querschnitts-review.md`](../audits/2026-11-06-querschnitts-review.md),
Plan [`../plans/2026-11-06-querschnitts-befunde.md`](../plans/2026-11-06-querschnitts-befunde.md) (Q3).

## Was sich ändert

- **M6 — kein ewiger Vorgang.** Startet ein Ablauf auf einem Vorgang, dessen Lauf beendet ist (fertig,
  Fehler, abgebrochen) oder einem anderen Ablauf gehört, wird dieser Vorgang abgeschlossen (`fertig`; ein
  wartender Lauf → `abgebrochen`, sein offener Auftrag ebenso) und ein neuer angelegt — **bevor** die
  Antwort eines Moduls oder der Treiber etwas schreibt. Ein Vorgang ohne Lauf (freie Arbeit) wird
  übernommen. Ein Lauf, der endet, lässt seinen Vorgang offen: der eben gespeicherte Entwurf bleibt
  erreichbar. Abgeschlossene Vorgänge nehmen keine Teile mehr an.
- **Neues Vorhaben / Arbeitsstand löschen.** Zwei Direktaktionen hinter dem Sicherheitstor:
  `vorgang_neu` schließt den aktiven Vorgang, `vorgang_loeschen` fragt erst nach („Ja, löschen“) und
  löscht dann **alle** Vorgänge der Person samt Ablage und Aufträgen, auch abgeschlossene, dazu die
  anonymen Vorgänge dieser Sitzung und ihr hochgeladenes Dokument. Beide räumen den gemerkten Entwurf
  der Sitzung ab (erst nach Erfolg). Einen laufenden b-api-Auftrag bricht das Löschen nicht ab (keine
  Schnittstelle, K21); dessen Ergebnis liegt dort bis zu 30 Tage und wird nicht mehr abgeholt. Der
  Einstieg: Knöpfe unter jedem beendeten Ablauf (das Modell schreibt keine `__action__`-Knöpfe).
- **Verweis je Zug aus der Datenbank.** Der Preflight frischt den Verweis einmal je Zug auf (Frist, Teile,
  Lauf), **vor** den Ablauf-Prüfungen, die nur ihn lesen. Ein abgelaufener oder abgeschlossener Vorgang
  fällt weg; ein fremder Verweis (nach Ab- oder Ummelden) bleibt verborgen stehen und gilt nach dem
  Zurückmelden wieder — solange die neue Besitzerin nicht selbst einen Vorgang in die Sitzung geholt
  hat (eine Sitzung hält einen Verweis). Die Kennzeile liest danach nur noch die Sitzung.
- **Erfolg des Übernehmens zählt.** `uebernehmen` meldet, ob gespeichert wurde; `fortsetzen` und der
  Modul-Auslöser rechnen sonst nicht weiter (Hinweis „Konflikt“).
- **Datei und Abschluss einer Ablage** schreiben nur in den Vorgang ihres Stapels (`nur_dieser`) — nach
  „neues Vorhaben“ landet ein Dateistand nicht in einem fremden Vorgang. Ebenso speichern Modul-Auslöser
  und `fortsetzen` die Antwort nur in den Vorgang ihres Laufs; schließt eine zweite Sitzung ihn
  währenddessen, endet der Zug mit „Konflikt“.
- **Savepoints halten ihre Sperre.** `verbindung_freigeben` schreibt innerhalb eines Savepoints nicht
  mehr fest. Bisher tat es das über den Lader im Rückruf von `teile_speichern`: Sperre weg, danach
  `InvalidRequestError` — jeder Dateistand und jeder Abschluss einer Ablage ging verloren (seit Q1).
- **Auftrag abschließen** ist ein bedingtes Update: ist der Auftrag inzwischen gelöscht (zweiter Tab),
  gibt es keinen `StaleDataError` (500) mehr.
- **Datensparsamkeit:** Werte über `$teil` an ein Werkzeug höchstens 64 KB (auch für WLO-Werkzeug-Schritte
  eines Ablaufs; der Fehlertext nennt „zu groß“); frühere Fassungen nur für `draft`; der Teil `document`
  geht mit dem Dokument — beim Löschen, beim Ersetzen durch ein neues und beim 24-h-Verfall; der
  Aufbewahrungslauf räumt Teile ab, deren Dokument auf anderem Weg ging. Das Entfernen sperrt die Zeile
  des Vorgangs (`FOR UPDATE`).
- **Migration 0020:** Index auf `vorgaenge.session_id` (das `SET NULL` beim Löschen von Sitzungen),
  Muster-Index `aufrufer text_pattern_ops` (Präfixsuche nach anonymen Vorgängen; trägt auch die
  Gleichheit, der alte `ix_vorgaenge_aufrufer` fällt weg), Indexname `ix_vorgang_auftraege_vorgang_id`
  wie im Modell.

## Beim Deploy

- **Migration 0020** einspielen (`alembic upgrade head`). Sie legt zwei Indizes an und löscht einen; bei
  der heutigen Größe der Tabelle ohne spürbare Sperre.
- Bestehende Vorgänge mit fertigem Lauf bleiben `aktiv`, bis die Person einen Ablauf startet oder
  „Neues Vorhaben“ wählt — es gibt im Betrieb noch keine (Abläufe sind nicht live).

## Bewusst anders als geplant

- Scheitert der Treiber nach dem Schließen des alten Vorgangs, bleibt nur ein leerer neuer; der alte
  ist dann schon abgeschlossen (sein Entwurf nicht mehr erreichbar). Der leere wird beim nächsten
  Start übernommen.

- Plan Q3/1 sah vor, dass ein Lauf, der `fertig` endet, seinen Vorgang selbst schließt. Das Review fand
  drei Folgen (der Entwurf wäre sofort unerreichbar, eine Modul-Antwort landete im alten und der Lauf im
  neuen Vorgang, freie Arbeit würde geschlossen) — umgestellt auf „der nächste Start schließt“.
- Ein Einstieg zu „Arbeitsstand löschen“ außerhalb eines Ablaufs (Menü im Widget) fehlt noch — offene
  Entscheidung.
- Für die Historie von `draft` gibt es noch keinen Leser (geplant: zurück zur vorigen Gliederung); sie
  bleibt, weil sie klein ist und mit dem Vorgang geht.

## Review-Runden

1. **Erstes Review** (4 MAJOR): der Plan „ein fertiger Lauf schließt seinen Vorgang“ verlor den Entwurf,
   trennte Antwort und Lauf, schloss freie Arbeit, und die Aktionen hatten keinen Einstieg → Umbau wie
   oben, dazu Löschen aller Vorgänge mit Rückfrage, `FOR UPDATE`, ersetztes Dokument, `nur_dieser`,
   Auffrischen im Preflight, verborgener fremder Verweis, Index.
2. **Nachprüfung** (1 MAJOR, 6 MINOR, 4 NIT): Savepoint-Freigabe (MAJOR, auf Postgres nachgestellt),
   Gegenprobe im `nur_dieser`-Test, Ziel fest vor dem Speichern, Prüfung des `document`-Verweises unter
   der Sperre, bedingtes Abschließen von Aufträgen, fehlende Tests (Preflight-Reihenfolge,
   „inzwischen abgeschlossen“, `alle_loeschen` je Besitzerin, großes verwaistes Dokument, Konflikt bei
   „neues Vorhaben“), Docstrings, Knöpfe auch nach Fehler/Abbruch, Umfang des Löschens.
   Offen (älter, nicht aus Q3): `ui_auftrag._wartender_auftrag` liest den Verweis ohne Auffrischen;
   theoretische Verklemmung Verdrängen in `anlegen` gegen die sortierte Sperre; der Debug-Block der
   Nachrichten trägt den Verweis (nur intern sichtbar).

## Tests

- `tests/test_querschnitt_vorgang.py` (neu, 15): Lebenslauf des Vorgangs (offen nach dem Lauf, nächster
  Start schließt, fremder wartender Lauf, freie Arbeit, Modul-Auslöser auf beendetem Vorgang, gescheitertes
  Übernehmen), `nur_dieser`, Auffrischen im Preflight, Knöpfe, „neues Vorhaben“, Rückfrage und
  bestätigtes Löschen.
- `tests/test_dokument_ablage.py` (+3, Postgres): ersetztes Dokument nimmt seinen Teil mit, verwaiste
  Teile im Aufbewahrungslauf (auch groß in der Ablage), ein inzwischen neues Dokument bleibt.
- `tests/test_vorgang_pg_q3.py` (neu, Postgres): Neuberechnung über den Lader speichert, `nur_dieser`,
  `alle_loeschen` je Besitzerin. `tests/test_auftraege_ablage.py` (+1): Abschluss eines gelöschten
  Auftrags.
- `tests/test_migration_vorgang_indizes.py`, `tests/test_vorgaenge.py`, `tests/test_teil_verweise.py`,
  `tests/test_preflight_node.py` (Aktionen durch das Tor).
- Bewusst geänderte Erwartungen: unter einem fertigen Ablauf stehen jetzt die beiden Vorgangs-Knöpfe
  (`test_ablauf_auftrag`, `test_querschnitt_ablaeufe`); ein fremder Verweis bleibt stehen statt zu
  verschwinden (`test_arbeitsstand`).
- Reihenfolge: Die Tests der Überarbeitung liefen vor dem Code rot (fehlende Funktionen, „Vorgang
  `fertig` statt `aktiv`“, Dokument-Teil blieb); für die Migration wurde der Test nach der Änderung
  angepasst.
