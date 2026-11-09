# Paket K2b — Auftrag abbrechen, Eingabe je Schritt sperren (2026-11-08)

Plan: [`plans/2026-11-08-kestra-ablaeufe-komfort.md`](../plans/2026-11-08-kestra-ablaeufe-komfort.md), Entscheid F1
(je Schritt wählbar, Vorgabe frei, Abbruch-Knopf immer).

## Was die Person sieht

- Unter „Der Auftrag läuft noch“ und unter jeder Antwort des Backends zum Auftrag stehen **„Stand prüfen“
  und „Auftrag abbrechen“**. Unter einer gewöhnlichen Modell-Antwort steht nur „Stand prüfen“ (sonst
  verdrängten zwei Knöpfe unter dem Deckel jeden Vorschlag).
- Auch das Fortschritt-Modul (`ui_fortschritt`) zeigt „Auftrag abbrechen“, solange der Auftrag läuft.
- **Abbrechen** fragt erst nach („Ja, abbrechen“ / „Stand prüfen“). Bestätigt endet der Lauf als
  `abgebrochen`, der Auftrag ebenso. Nach dem Festschreiben endet er auch bei der B-API (`DELETE`, nur mit dem
  Schlüssel der Person). Darunter stehen „Neues Vorhaben“ und „Arbeitsstand löschen“. Ist die Anmeldung
  abgelaufen, sagt die Antwort, dass der Auftrag bei der b-api bis zu seinem Ende weiterläuft.
- **„Neues Vorhaben“** fragt bei einem wartenden Auftrag ebenso erst nach („Ja, neu beginnen“); auch diese
  Bestätigung gilt nur für den Auftrag, für den sie gefragt wurde.
- **Gesperrter Schritt** (`warten: gesperrt`):
  - Solange der Auftrag läuft, zeigt das Eingabefeld den Platzhalter „Ein Auftrag läuft – weiter geht es mit
    den Knöpfen.“ Es bleibt bedienbar (**weiche Sperre**): eine Krisennachricht muss sich immer tippen lassen.
  - Getippte Nachrichten, Modul-Antworten und andere Knöpfe beantwortet das Backend nur mit einem Hinweis samt
    beiden Knöpfen. Dafür läuft die Sicherheitsprüfung (wie bei jeder Direktaktion), aber keine Modell-Antwort
    und kein Aufruf der b-api.
  - Durch bleiben „Stand prüfen“, „Auftrag abbrechen“, „Neues Vorhaben“ und „Arbeitsstand löschen“. Kein Deckel
    der Schnellantworten (`max_count`, Muster, Gastgeber) streicht im gesperrten Lauf die beiden Auftrags-Knöpfe.
  - Eine Nachricht mit hohem Risiko (Krise) oder ohne Moderation geht wie bei einer Wendung den gewöhnlichen Weg
    und bekommt ihre Krisenantwort. Nach einer Krise **ruht die Sperre**, solange dieses Warten dauert
    (`session_state["auftrag_sperre_ruht"]`) — die Person soll auf die Krisenantwort antworten können.
  - Die stummen Antworten von Kontext-Ping und Tour-Tick tragen die Marke, aber keine Knöpfe.

## Geändert

- **Backend**
  - `domain/config_models/ablauf.py`: Feld `Schritt.warten` (`frei` | `gesperrt`, Vorgabe leer = frei).
  - `services/ablauf/pruefung.py` (+ Texte): `warten` gilt nur an Schritten der Art `auftrag`.
  - `services/ablauf/auftrag_zug.py`:
    - `AKTION_ABBRECHEN` (`ablauf_auftrag_abbrechen`) und `abbrechen()` mit Rückfrage;
    - `knoepfe()` und `pruefen_knoepfe()` (bisher `pruefen_knopf`);
    - `gesperrt()` und `gesperrt_antwort()`.
  - `services/ablauf/zug_basis.py`: `abbrechen()` meldet, ob es geklappt hat (bei einem Konflikt `False`). Die
    Start-Antwort trägt beide Knöpfe.
  - `graph/nodes/preflight_ablauf.py`:
    - `Ausloeser.gesperrt`, nicht für Kontext-Ping und Tour-Tick;
    - `abgewiesen()` mit der Liste der erlaubten Aktionen;
    - der Hinweis kommt vor jeder anderen Aktion.
  - `graph/nodes/preflight.py`: Die neue Direktaktion durchläuft dieselbe Sicherheitsprüfung. Im gesperrten Lauf
    bekommt auch ein anderer Knopf nur den Hinweis.
  - `api/schemas.py` und `api/chat.py`: `ChatResponse.eingabe_gesperrt`, gesetzt in `_anmeldestand` aus dem
    Verweis nach dem Zug, für beide Wege (POST und Strom).
  - `services/turn_assembly.py`: Unter einer Modell-Antwort stehen beide Knöpfe.
  - `i18n/bot_text.py`: Texte für Abbruch und Sperre (de/en).
- **Widget**
  - `ui-module/_vertrag/modul-host.ts`: neuer `AuftragSchritt` `abbrechen`.
  - `ui-fortschritt` (Element, Ablauf, Texte, Stil): Knopf „Auftrag abbrechen“.
  - `ui/controllers/collection-actions.ts`: `auftragAbbrechen()`. Karten-Aktionen geben `eingabe_gesperrt`
    weiter (`setEingabeGesperrt`).
  - `ui/shell`:
    - Signal `eingabeGesperrt` setzt den Hinweis-Platzhalter (weiche Sperre: Feld und Senden bleiben bedienbar);
    - Neustart und `resetSession` geben die Eingabe frei.
- **Studio**: Feldtexte `feld.Schritt.warten.*` (de/en). Die Schema-Fixture ist neu erzeugt
  (`scripts/export_area_schemas.py`).

## Bewusst so

- **Nach dem Neuladen** zeigt das Eingabefeld zunächst keinen Hinweis; der Verlauf trägt die Sperre nicht.
  Tippt die Person, antwortet das Backend mit dem Hinweis, und diese Antwort setzt ihn wieder.
- **Die Tour** läuft vor dem Preflight: eine selbst gestartete Tour und getippte Tour-Antworten gehen auch im
  gesperrten Lauf durch. Sie berühren den Auftrag nicht.
- Ein **veralteter Verweis** kann einmal den Hinweis zeigen: Eine zweite Sitzung hat schon abgeholt. „Stand
  prüfen“ frischt ihn auf.
- Abbrechen folgt **nicht** `bei_fehler`: Ein Abbruch durch die Person ist kein Fehler des Flows. Der Lauf endet
  als `abgebrochen`.

## Review (2026-11-08)

Kein Befund kritisch; einer hoch, vier mittel. Alles ist behoben.

| Befund | Behebung |
|---|---|
| **Hoch:** Die Vorgabe `"frei"` änderte die Fassung (`treiber.fassung`, `exclude_none`) jedes Ablaufs. Nach dem Deploy wäre jeder wartende Lauf abgebrochen, samt DELETE bei der B-API. | Die Vorgabe ist `None`. Ein Test hält fest, dass die Fassung bestehender Abläufe gleich bleibt. |
| Ein altes „Ja, abbrechen“ im Verlauf beendete still einen späteren Lauf desselben Ablaufs. | Die Bestätigung trägt das Kürzel des Auftrags. Passt es nicht, fragt der Chatbot neu. |
| Gesperrte Antworten ohne Knöpfe (Konflikt, Drosselung, Sicherheits-Block) ließen die Person vor einem gesperrten Feld stehen. | `_eingabe_sperre` hängt dann „Stand prüfen“ und „Auftrag abbrechen“ an. |
| `_anmeldestand` konnte einen gespeicherten Zug brechen. | Die Sperre wirft nie (sie fällt auf frei zurück). |
| Tests fehlten. | Ergänzt: Hintergrund-Züge, zweites „Ja“, altes „Ja“, Antwort ohne Knöpfe, Sperre wirft nicht. |
| Kleinere Punkte | Ein zweites „Ja“ meldet „Dieser Auftrag läuft nicht mehr.“; Kommentar zur Sicherheitsprüfung der erlaubten Knöpfe. |

## Zweites Review (2026-11-08)

Ein frischer Reviewer ohne Vorwissen: 0 kritisch, 2 hoch, 6 mittel, 4 Kleinigkeiten. Alles ist behoben oder
dokumentiert.

| Befund | Behebung |
|---|---|
| **Hoch:** Kontext-Ping und Tour-Tick bekamen im gesperrten Lauf „Stand prüfen“/„Abbrechen“ an ihre stumme Antwort — das Widget zeigte bei jedem Öffnen eine leere Blase mit zwei Knöpfen. | `_eingabe_sperre` hängt an Hintergrund-Antworten keine Knöpfe. |
| **Hoch:** Das gesperrte Feld (`disabled`) ließ keine Krisennachricht zu, und die Krisenantwort sperrte selbst. | Weiche Sperre: das Feld bleibt bedienbar, nur der Platzhalter weist hin. Eine Krisenantwort sperrt nicht, und danach ruht die Sperre für dieses Warten. |
| Der Deckel der Schnellantworten lief nach der Sperre und konnte die Auftrags-Knöpfe streichen (`max_count: 0`). | Im gesperrten Lauf behält der Deckel sie (`widget_postprocess._auftrags_knoepfe_behalten`). |
| In der freien Spur verdrängten die beiden Knöpfe unter dem Deckel jeden Vorschlag; der Anmelde-Knopf schob „Abbrechen“ hinaus. | Unter Modell-Antworten nur „Stand prüfen“. |
| „Neues Vorhaben“ beendete einen laufenden Auftrag ohne Rückfrage — auch ein alter Knopf im Verlauf. | Rückfrage mit Kürzel, wie beim Abbrechen. |
| Das Studio speichert „— nicht gesetzt —“ als `""`; das Muster wies es mit 422 ab. | `""` gilt als leer (`BeforeValidator`); Schema unverändert. |
| Das Mikrofon blieb im gesperrten Feld bedienbar. | Erledigt durch die weiche Sperre (gewollt). |
| Ein bestätigter Abbruch ohne Schlüssel der Person meldete „abgebrochen“, obwohl der Auftrag bei der b-api weiterlief. | Eigene Antwort `auftragNurHierAbgebrochen`. |
| Kleinigkeiten | Abbruch-Knopf nach gelöschtem Arbeitsstand meldet „läuft nicht mehr“; Tour-Ausnahme und Sicherheitsprüfung im Hinweis dokumentiert; Fokus und Tab-Reihenfolge erledigt durch die weiche Sperre. |

Ein Test des ganzen `preflight()`-Knotens deckt jetzt die Krise im gesperrten Lauf ab.

## Tests

- Backend:
  - neu `tests/test_ablauf_auftrag_abbruch.py` (Rückfrage, Abbruch, Konflikt, Knöpfe, Prüfung, Sperre,
    Preflight-Hinweis, erlaubte Aktionen, `eingabe_gesperrt`);
  - `test_schemas.py`, `test_ablauf_auftrag.py` (`pruefen_knoepfe`, „Neues Vorhaben“ mit Rückfrage) angepasst;
  - zweites Review: Hintergrund-Antworten, Krise (Einheit und ganzer Preflight-Knoten), ruhende Sperre, Deckel,
    „Neues Vorhaben“, leeres `warten`, Abbruch ohne Schlüssel, gelöschter Arbeitsstand;
    `test_turn_assembly.py` (nur „Stand prüfen“ unter Modell-Antworten).
- Widget:
  - `ui-fortschritt.element.spec.ts` (Abbrechen, nicht im Verlauf, nicht während eines Zugs, nicht nach dem
    Ende);
  - `collection-actions.spec.ts` (`auftragAbbrechen`, Sperre weitergeben);
  - `chat-shell-turn.spec.ts` (Hinweis im bedienbaren Feld, Freigabe, Neustart).

## Betrieb

Keine Migration und keine neue Variable. Das Widget-Bündel muss neu gebaut werden (neues Element-Verhalten,
Shell).
