# Themenbaum zeigt nicht lesbare Zweige (2026-11-14)

Plan [`2026-11-14-mcp-stand-8cbc051.md`](../plans/2026-11-14-mcp-stand-8cbc051.md), Paket N5.

Der MCP meldet je Knoten, wenn er die Unterthemen gerade nicht lesen konnte (`childrenUnread`, ein
Ausfall, seit dem 13.11.) oder das Repository sie nicht herausgibt (`childrenRefused`, ab dem
Stand vom 14.11.). Das Modul übernahm beides nicht. Ein solcher Zweig sah aus wie ein Thema ohne
Unterthemen.

## Was sich ändert

- **Daten:** Ein Knoten trägt `nicht_lesbar` mit `ausfall` oder `gesperrt`
  (`ui_module/themenbaum.py`, Manifest des Moduls). Trägt er beide Kennzeichen, gilt `gesperrt`.
- **Anzeige am Eintrag** (`frontend/projects/ui-module/src/ui-themenbaum`):
  - Ausfall: „Unterthemen gerade nicht lesbar – Aufklappen lädt neu“. Der Eintrag ist
    aufklappbar; das Aufklappen lädt neu, auch auf der ersten Ebene. Scheitert es wieder, steht
    „nicht geladen“ mit „Erneut laden“ da wie bisher.
  - Abgelehnt: „Unterthemen nicht zugänglich“. Kein Auf/Zu, kein Abruf. Der Stand bleibt, bis ein
    neuer Baum kommt, auch nach einem Wechsel der Anmeldung.
  - Der Hinweis ist Text, gehört zur Beschreibung des Eintrags für Vorleser und steht in Deutsch
    und Englisch. Auf der tiefsten Ebene (8) steht keiner: Dort zeigt der Baum keine Unterthemen.
- **Aufklappen meldet die Ablehnung:** Gibt das Repository einen Zweig erst beim Aufklappen nicht
  heraus, kommt statt „nicht geladen“ mit „Erneut laden“ der Hinweis „nicht zugänglich“
  (`POST /api/ui/themenbaum/zweig` antwortet 200 mit leerer Liste und `nicht_lesbar`).
- **Die KI erfährt es:** Die Quittung nennt, bei wie vielen Themen die Unterthemen nicht lesbar
  waren, getrennt nach Grund und ohne Namen. Ist die Sammlung selbst abgelehnt, bekommt die KI
  „nicht zugänglich (nicht freigegeben oder nicht vorhanden)“ statt „prüfe das Argument“, und es
  gibt keinen zweiten Versuch.
- **Direktaktionen:** „Unterthemen“ und „Als Entwurf bearbeiten“ antworten für eine abgelehnte
  Sammlung mit einem eigenen Satz, ohne den Knopf „Erneut versuchen“.
- **Textfassung** (für Widgets ohne das Modul): der Hinweis steht in Klammern am Thema.

## Entscheide

- **„Nicht zugänglich“ statt „mit dieser Anmeldung nicht lesbar“.** Die meisten Personen sind
  nicht angemeldet, und derselbe Fall tritt ein, wenn eine Sammlung gelöscht wurde.
- **Ein unbekanntes Fach ist keine Ablehnung.** Der MCP meldet zu `subject` denselben Code
  (`not_found`) für „kein Fachportal mit diesem Namen“. Als Ablehnung zählt `not_found` deshalb
  nur zu einer Kennung; zum Fach bleibt der Hinweis „prüfe das Argument“.
- Der Ausfall-Hinweis trägt die Fehlerfarbe, der Hinweis „nicht zugänglich“ bleibt neutral: Das
  zweite ist kein Fehler der Anwendung.
- Die Kennzeichen zum Inhaltsabruf (`contentsUnread`, `contentsRefused`) entstehen nur mit
  Inhaltszahlen; der Baum fordert keine an.

## Review

Ein unabhängiges Review fand 1 schweren Befund (das unbekannte Fach, siehe oben), 7 kleinere und
6 Randnotizen. Behoben sind der schwere, alle kleineren und drei Randnotizen (Reihenfolge der
Prüfung im Widget, Hinweis auf Ebene 8, Vertragstexte).

Bewusst gelassen:
- Die Textfassung trägt den Klammerzusatz nur deutsch; sie ist insgesamt nicht übersetzt.
- Wird ein gekürzter Zweig beim Aufklappen abgelehnt, stehen bekannte Kinder, „weitere“ und der
  Hinweis zugleich da. Selten, und nichts davon ist falsch.
- Ein altes Widget-Bundle mit neuem Backend liest die Ablehnung als „keine Unterthemen“. Das gilt
  bis zum Neuladen der Seite.

## Geprüft

- Backend: volle Suite 10 327 Tests grün (5 übersprungen); neu `tests/test_ui_themenbaum_nicht_lesbar.py`, ergänzt
  `test_ui_themenbaum_aktion.py` und `test_ui_strukturentwurf_aktion.py`.
- Widget: 377 Modul-Tests grün; ein eigener Block in `ui-themenbaum.component.spec.ts` (9 Fälle)
  und ein Beispiel im Manifest.
- Browser (Playwright gegen das gebaute Bundle): 12 Tests zum Themenbaum grün, darunter:
  Hinweise sichtbar und in der Beschreibung, Aufklappen per Tastatur lädt nach einem Ausfall neu,
  320 px ohne waagerechtes Scrollen, Kontrast in Hell und Dunkel.
- Bundle: 662,9 kB roh, 193,0 kB gzip (vorher 661,0 und 192,4); Grenzen 700 und 210 eingehalten.

Nicht geprüft: gegen einen echten Ausfall oder eine echte Ablehnung am Repository. Beides lässt
sich dort nicht gezielt herstellen; die Formen stammen aus dem Quelltext des Servers.

## Deploy

- Keine Migration, keine neue Variable. Image neu bauen (Backend und Widget).
- Der Teil für Ausfälle wirkt sofort, der Teil für „nicht zugänglich“ nach dem Deploy des MCP.
