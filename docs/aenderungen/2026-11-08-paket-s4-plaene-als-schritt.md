# Paket S4 — Pläne als Freigabe-Schritt (2026-11-08)

Folgt auf [Paket S](2026-11-08-paket-s-schreibende-schritte.md). Auftrag des Nutzers: „weiter mit der Umsetzung,
bei den offenen Fragen nach eigenem Ermessen“. Pläne als Ablaufschritt waren dort offen.

## Was sich ändert

Ein Freigabe-Schritt darf jetzt auch einen **Plan** rufen. Ein Plan ist eine Änderung vieler Datensätze unter
**einer** Bestätigung. Damit kann ein Ablauf zum Beispiel die Volltexte eines Kestra-Flows an viele Datensätze
hängen.

| Werkzeug | Was |
|---|---|
| `wlo_attach_fulltexts` (W2) | viele Volltexte |
| `wlo_update_contents` (W3) | Metadaten vieler Datensätze |
| `wlo_create_collection_tree` | ein Sammlungsbaum |
| `wlo_add_to_collections` | viele Aufnahmen in Sammlungen |

- Vorlegen, Freigabe und Einlösen laufen wie bei jedem Freigabe-Schritt.
- Der Server arbeitet den Plan in Abschnitten ab:
  - **Fertig im ersten Abschnitt:** Der Lauf geht gleich weiter.
  - **Noch offen:** Der offene Plan trägt die Marke des Laufs. Der Lauf wartet; unter den Antworten steht
    „Plan fortsetzen“. Jeder Abschnitt geht ohne neue Bestätigung weiter (Paket M5), und die Marke reist mit.
  - **Fertig nach „Plan fortsetzen“:** Der Lauf geht weiter. Der strukturierte Teil der letzten Antwort
    (`complete`, `progress`, Einträge) wird Teil `schreibt`, ohne Schlüsselfelder.
  - **Abgelaufen oder nicht mehr gültig** (`plan_expired`, Frist): Der Lauf wartet mit „Vorschau erneut
    zeigen“. Die neue Vorschau zeigt, was schon da ist.
- **„Ablauf abbrechen“** verwirft auch den offenen Plan. Was er schon erledigt hat, bleibt in WLO, und der Satz
  sagt das.
- **Löschen** bleibt aus einem Ablauf ausgeschlossen (eigener Entscheid, siehe Paket S).

## Geändert

- `services/ablauf/werkzeuge.py`: `freigebbar` erlaubt Pläne.
- `services/plan_fortsetzen.py`: `_merke` behält die Marke des gleichen Plans; `weiter` legt bei Fertigstellung
  das Ergebnis für den Nachlauf ab (`FERTIG`, ein Zug lang).
- `services/ablauf/freigabe_zug.py`: offener Plan nach dem Einlösen, `nach_plan`, Knopf, Abbruch.
- `graph/nodes/preflight_ablauf.py`: Nachlauf nach „Plan fortsetzen“.
- `services/ablauf/pruefung_texte.py` (Befund `schreibend` ohne „Plan“), `i18n/bot_text.py`
  (`freigabeAbgebrochenPlan`).

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 1 hoch, 7 klein, 2 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| „Vorschau erneut zeigen“ (ein älterer Knopf im Widget) legte auch bei laufendem Plan neu vor. Ein zweites Ja ließ den Plan von vorn laufen; der alte blieb auf dem Server liegen. | Solange der Plan des Laufs offen ist, gibt es keine neue Vorschau: „Führe ihn zuerst mit ‚Plan fortsetzen‘ zu Ende“, mit Knopf. |
| Nach einer Ablehnung mitten im Plan oder einem verborgenen Werkzeug wartete der Lauf, statt zu `bei_fehler` zu gehen. | `plan_fortsetzen` meldet den Ausgang (`plan_aus: fehler/neu`); eine Ablehnung führt zu `bei_fehler`, nur „abgelaufen/ungültig“ zu einer neuen Vorschau. |
| „Ablauf abbrechen“ sagte „nichts geändert“, wenn der angelaufene Plan schon weg war. | Der Lauf merkt `plan_angelaufen`; der Satz sagt dann, dass Erledigtes bleibt. |
| Lief der Plan zu Zugbeginn ab, stand „kein offener Plan“ ohne Knopf da. | Der Knopf des wartenden Laufs steht darunter. |
| Bei `plan_offen` und `too_many_plans` ging „Plan fortsetzen“ verloren. | Die Knöpfe des Einlösens bleiben vorn. |
| `_plan_offen` prüfte weder Aufrufer noch Frist noch Kennung. Ein fremder Plan mit demselben Werkzeug ließ den Lauf hängen. | Es gelten Aufrufer, Frist und Kennung; ob ein Plan offen blieb, sagt die Einlösung selbst (`plan_offen`). |
| `complete` heißt „nichts mehr offen“, nicht „geklappt“. | **Eigener Entscheid:** Sind alle Einträge `failed`, geht der Lauf zu `bei_fehler`; teilweise Fehler stehen im Teil. |
| Zu große Angaben scheiterten still. | Mit Grund („in kleineren Teilen“). |
| `FERTIG` auch ohne ausdrückliches `complete`. | Nur bei `complete: true`. |
| Testlücken | 7 Tests: keine neue Vorschau, Abbruch nach Ablauf, Ablehnung mitten im Plan, ausgelastet/keine Antwort beim Fortsetzen, alle gescheitert, Ablauf zu Zugbeginn, fremder Plan. |

Offen: `MAX_REMEMBERED_ARGS_BYTES` zählt Zeichen, nicht Bytes (nur der Name).

## Tests

- neu `backend/tests/test_paket_s4_plan.py`: zu Ende über „Plan fortsetzen“, die Marke über Abschnitte, ein
  abgelaufener Plan, Abbruch, fertig im ersten Abschnitt, Chat-Plan ohne Lauf unverändert.
- angepasst `test_paket_s.py`: Pläne sind erlaubt, Löschen nicht.
- Volle Backend-Suite nach Gesamt-Review S, S4 und Review S4: 9052 grün, 5 übersprungen, 0 rot; ruff sauber.

## Betrieb

Keine Migration, kein Seed geändert. Backend neu bauen.
