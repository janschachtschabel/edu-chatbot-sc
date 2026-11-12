# Fix: Eingabezeile fehlt auf dem Handy (2026-11-12)

## Befund

Gemeldet vom Nutzer auf Android mit Chrome, eingebettet in wp-test.wirlernenonline.de. Im
Vollbild-Panel fehlte die Eingabezeile. Unter den Nachrichten stand leere Fläche.

## Ursache

Unter 480 px Breite wird das schwebende Panel zum Vollbild (`widget.component.scss`, Regel
`@media (max-width: 480px)`): `position: fixed`, `height: 100vh`.

In Chrome auf Android ist `100vh` die Höhe bei **eingeklappter** Adressleiste. Ist sie sichtbar,
ragt das Panel um ihre Höhe (gut 100 px) unter den Bildrand. Dort sitzt die Eingabezeile.

## Behebung

- **Vollbild-Regel:** `height` und `max-height` mit `100dvh`, der Höhe des sichtbaren Bereichs.
  Davor bleibt `100vh` als Rückfall für Browser ohne `dvh`.
- **Schwebendes Panel und große Stufe** (`_widget-panel.scss`): `calc(100dvh - 40px)` mit
  demselben Rückfall.
- Der rahmenlose Einbau ist nicht betroffen, er nimmt die Höhe seines Containers.

## Prüfung

- Das Bündel enthält `100dvh` und den Rückfall.
- Budget eingehalten (gzip 192,4 von 210 kB). Widget-Unit-Tests 98 grün.
- `e2e/frameless.spec.ts` prüft jetzt auch, dass die Eingabezeile und das Panel im sichtbaren
  Bereich liegen.
- **Grenze:** Die Adressleiste von Android kann Playwright nicht nachbilden, dort gilt vh = dvh.
  Die eigentliche Probe ist ein Test auf dem Handy nach dem Deploy.

## Deploy

Image neu bauen, auf dem Handy die Seite neu laden. Keine Migration.
