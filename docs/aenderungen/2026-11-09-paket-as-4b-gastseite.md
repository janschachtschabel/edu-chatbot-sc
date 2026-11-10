# Paket AS-4b: Ablauf von der Gastseite starten (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), E2 A und §5f.
Baut auf AS-4a auf (Startschema, Auslöser „Gastseite“).

## Was sich ändert

- **JS-API:** `chat.startAblauf(id, daten?)` am Element `<boerdi-chat>`.
  - Der Zug geht als Direktaktion `ablauf_starten` mit `{ablauf, start}` hinaus.
  - Im Verlauf steht er als Blase des Gastgebers: „Ablauf „…“ von der Seite gestartet“.
  - Die Methode öffnet den Chat. Sie wartet auf die Shell und auf einen laufenden Zug, wie
    `startTask`.
- **Attribute:**
  - `ablauf-start="<id>"` und `ablauf-start-daten='{"…": …}'` starten den Ablauf beim ersten
    Öffnen. Sie öffnen nicht von selbst.
  - Kaputtes JSON startet nichts; die Warnung in der Konsole nennt keine Werte.
  - Die Attribute heißen `ablauf-start…` und nicht `start-ablauf`, sonst stieße das Input mit der
    Methode `startAblauf` zusammen.
- **Im Widget geprüft wird nur:** eine Kennung in der Form einer Ablauf-ID und ein reines Objekt,
  als JSON kopiert (ohne Funktionen und Prototypen). Alles andere prüft das Backend gegen das
  Startschema (AS-4a).
- **Warteschlange:** Aufträge und Abläufe des Gastgebers teilen eine Warteschlange (`starte`
  statt eines Texts) und gehen in ihrer Reihenfolge ab.
- **Doku:**
  - `docs/browser-plugin-einbindung.md`: §5 „Einen Ablauf mit Startdaten starten“, die
    Attribut-Tabelle, die JS-API und die Wegtabelle;
  - die Architektur-Referenz im Studio (`HOST_ATTRIBUTES`, DE und EN).

## Wo

- `frontend/projects/ui/src/shell/chat-shell.component.ts`: `startAblauf`, `_alsGastgeber`,
  Warteschlange.
- `frontend/projects/ui/src/i18n/de.ts`, `en.ts`: `chat.hostAblauf`.
- `frontend/projects/widget/src/element-api.ts`: `FORWARDED_METHODS`.
- `frontend/projects/widget/src/app/widget/widget.component.ts`: `startAblauf`, die Inputs
  `ablaufStart`/`ablaufStartDaten`, `_ablaufAusAttributen`, Nachziehen im Effect.
- Studio: `views/widget-contract-data.ts`, `i18n/catalogue/reference-widget.ts`.

## Tests

- `ui/src/shell/chat-shell-ablauf-start.spec.ts` (neu, 6):
  - Aktion und Parameter, die Blase des Gastgebers;
  - ohne Daten;
  - ungültige Kennung oder Daten;
  - reines JSON;
  - Warten auf einen laufenden Zug;
  - die Markierung gilt nur für einen Zug.
- `widget.component.spec.ts`: Start vor dem Mount; die Attribute starten erst beim Öffnen;
  kaputtes JSON. Der Vertrag umfasst jetzt 35 Attribute.
- `element-api.spec.ts`: die Methode wird durchgereicht.
- Ergebnis: ui 99 Dateien / 1222 Tests, Widget 4 / 80, Studio 171 / 2113 — alle grün; eslint
  sauber.

## Betrieb

Keine Migration, keine neue Variable. Das Image neu bauen (Widget, Studio). Danach im Browser
einmal hart neu laden.

## Review (Befundhebung)

Unabhängiges Review (Diff gegen den Klon `edu-chatbot-sc`). Ergebnis: 0 kritisch, 2 schwer,
8 kleiner, 3 Kleinigkeiten.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Das Attribut startet bei jedem Seitenaufruf neu (die Sitzung bleibt) — ein laufender Lauf ginge auf Schritt 0 zurück, ein wartender Auftrag würde abgebrochen. | schwer | Bremse im Backend: Mit `quelle: "gastseite"` startet ein Lauf desselben Ablaufs mit denselben Startdaten nicht neu („läuft hier schon“, `action.ablauf.laeuftSchon`). Andere Daten starten neu. `quelle` ist kein Recht, nur die Bremse. Tests im Backend. |
| 2 | Doku und Studio-Referenz sagten, ohne Auslöser „Gastseite“ starte nichts — ohne Daten startet `startAblauf` jeden Knopf-Ablauf. | schwer | Richtiggestellt (Doku §5, Attribut-Tabelle, Studio-Referenz DE/EN, Demo). |
| 3 | Mit gemounteter Shell öffnete `startAblauf` (und `startTask`) ein wieder geschlossenes Panel nicht. | kleiner | `setExpanded(true)` vor dem Senden, in beiden. |
| 4 | Bei einer fortgesetzten Sitzung geht ein Auftrag der Gastseite vor dem Verlauf ab (der alte Verlauf steht dahinter). | kleiner | Behoben in Paket RB-3 (`…-paket-rb3-gastseite-verlauf.md`): ein eigenes Signal „Verlauf bereit“ statt `isLoading` (das zu halten brach 25 Specs). |
| 5 | Nach dem Neuladen ist die Blase eine gewöhnliche Nutzerblase (kein Merker gespeichert). | kleiner | Behoben in Paket RB-3: `ChatRequest.from_host` → `ui.from_host` im Verlauf. |
| 6 | Vor dem Mount gab es nur einen Platz je Art; Reihenfolge fest statt wie gekommen. | kleiner | Eine geordnete Liste `_wartendeZuege` für Aufträge und Abläufe. |
| 7 | Ungültige Kennung oder Daten endeten still, das Panel öffnete trotzdem. | kleiner | `ablaufStartPruefen` (exportiert) vorab im Widget; Warnung ohne Werte in Widget und Shell. |
| 8 | Testlücken (gemischte Warteschlange, POST-Rückfall, Wiederöffnen, geschlossenes Panel, `{}`). | kleiner | Ergänzt. |
| 9 | `{}` als Daten ließ das Backend einen Knopf-Ablauf abweisen. | kleiner | Leere Daten zählen als keine. |
| 10 | Doku-Lücken (Kurzanleitung, edu-sharing-Einbindung, Demo, Plan, Docstring). | kleiner | Nachgezogen; Demo-Abschnitt „3a“ mit Knopf. |
| 11 | „Beide werden …“ nach „Drei Ausnahmen“. | Kleinigkeit | „Alle drei“. |
| 12 | Blase doppelt („Auftrag der Seite“ + „von der Seite gestartet“). | Kleinigkeit | „Ablauf „…“ gestartet“. |
| 13 | Keine frühe Grenze für die Daten. | Kleinigkeit | Höchstens 20 Schlüssel und 16 000 Zeichen JSON, sonst eine Warnung. |

Nach den Behebungen: ui 99 / 1226, Widget 4 / 84, Studio 171 / 2113 grün; eslint sauber;
Backend Startdaten-, Zug- und i18n-Tests grün.
