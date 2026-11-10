# Paket AS-7b — Führungen im Widget und im Studio (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5m (F-2, F-4, F-7). Baut auf AS-7a auf
(`2026-11-10-paket-as-7a-fuehrungen-backend.md`).

## Widget

- **Chip** `__fuehrung__|Label|URL` (F-2): `chips/guide-qr.ts` kennt das Präfix neben `__guide__`.
  - Derselbe Knopf und dieselbe Übergabe der Sitzung wie bei der Tour.
  - Er hängt nicht am Lotsen-Modus, denn er ist ein Schritt des Ablaufs.
- **Navigation:** `session/link-handoff.resolveGuideNavUrl` erlaubt ein Ziel derselben Herkunft (etwa
  den Pfad `/mitmachen/`) auch ohne Eintrag in der Vertrauensliste. Übergabe-Parameter kommen dann
  keine dazu.
  - Entscheid: Ein Sprung auf derselben Seite ist kein offener Umweg. Bisher brauchte er einen
    vertrauten Host, auf Seiten außerhalb von WLO führte der Chip also ins Leere.
  - Fremde Hosts bleiben gesperrt, auch protokoll-relativ (`//host`).
- **Seiten-Ping** (F-4): `controllers/seiten-ping.ts`.
  - Nach dem Laden des Verlaufs fragt `ShellLifecycle._afterResume` zuerst, ob der zuletzt
    bekannte Stand `wartet_seite` ist. Dann geht ein unsichtbarer Zug `page_event: ablauf_seite`
    hinaus.
  - Kommt eine Antwort mit Inhalt (die Seite passt), erscheint sie und ist der Gruß dieser Seite;
    der Kontext-Gruß entfällt dann.
  - Höchstens einmal je Seitenaufruf, nicht während eines Zugs, Fehler bleiben still.
- **Status** `wartet_seite` in der Leiste („wartet auf den Seitenwechsel“) und in „Meine Vorgänge“,
  jeweils de/en.
- **Angebot unter der Begrüßung** (F-7):
  - Das Boot-Bündel `GET /api/config/guide-mode` trägt neu `ablauf_seiten`: aktive Abläufe mit
    Auslöser `seite`, je mit Kennung, Titel je Sprache und Mustern. Es ist ein neues Feld im
    offenen Objekt, der Vertrag ändert sich nicht.
  - Passt die Seite (`widget/seiten-muster.ts`, dieselbe lineare Regel wie im Backend, gespiegelte
    Testfälle), stellt die Hülle höchstens zwei Start-Chips vor die Start-Chips
    (`widget/fuehrung-angebote.ts`).
  - Ein gesetztes `start-replies` des Gastgebers gewinnt.
  - Gestartet wird per Knopf: `ausloeser.per_knopf` nimmt jetzt auch `seite` an.

## Studio

- **Regel-Editor:** neue Bedingung „Seite passt“ (`wenn_seite`). Die Muster stehen in einer Zeile,
  mit Komma getrennt; jedes muss mit `/` beginnen, sonst sperrt der Editor.
- **Ablaufbild und Schrittfolge** beschriften Seitenregeln („Seite passt zu …“).

## Tests

- **Widget:**
  - `guide-qr.spec` (Führungs-Chip);
  - `link-handoff.spec` (dieselbe Herkunft, fremder `//host`);
  - `seiten-ping.spec` (4);
  - `lifecycle.spec` (Ping vor dem Kontext-Gruß);
  - `seiten-muster.spec` (17, spiegelt die Backend-Fälle, linear);
  - `fuehrung-angebote.spec`, `guide-mode-config.spec`;
  - Leiste und „Meine Vorgänge“ (Status de/en);
  - `widget.component.spec` (Chip vorn, `start-replies` gewinnt).
- **Studio:** `weiter-regeln.spec` (lesen, schreiben, Fehler).
- **Backend:** `per_knopf` mit `seite`, `seiten_angebote`, Feld im Boot-Bündel.
- **Läufe:**
  - ui 1368, widget 94, studio 2119, Backend-Auswahl 1445;
  - ESLint sauber;
  - `openapi-v1.json` unverändert.
- **Bündel:** 188,6 kB gzip (vorher 187,5); Angular meldet das Roh-Budget von 650 kB um 90 Byte
  überschritten (nur eine Warnung).

## Review AS-7b (10.11., unabhängig)

0 kritisch, 1 schwer, 8 mittel, 2 klein. Alle wurden am Code geprüft. Befund 1 trifft so nicht zu,
die übrigen sind behoben.

| # | Schwere | Befund | Entscheid / Behebung |
|---|---|---|---|
| 1 | schwer | Der Ping liest den Stand aus der jüngsten wiederhergestellten Antwort. Der Restore überspringt Zeilen ohne Text; ein `seite`-Schritt ohne Text ginge verloren. | **Trifft nicht zu:** Seit Review AS-7a (Befund 6) verlangt die Prüfung bei `seite` einen deutschen Text, eine solche Antwort hat also immer Inhalt. Der Plan nennt jetzt diesen Weg statt `sessionStorage`. |
| 2 | mittel | Die Ausnahme für dieselbe Herkunft galt für jede Navigation, auch für Bot-`navigate` und Lotsen-Chips. | Nur der Führungs-Chip setzt `gleicheHerkunft` (`onGuideQuickReply` → `resolveGuideNavTarget`). Specs für den Resolver und die Shell. |
| 3 | mittel | Waren die Studio-Chips leer, verdrängte der Führungs-Chip die vier Vorgaben. | Die Begrüßung stellt die Chips vor die aufgelösten Chips (Studio oder Vorgabe). Spec. |
| 4 | mittel | Kein Ping nach einer SPA-Navigation; ein Ping, der auf einen laufenden Zug traf, entfiel; der Pfad wurde im `computed` nicht neu gelesen. | `onSpaContextChange` pingt bei wartender Führung neu (statt Gruß), `loadingEnded` holt einen verpassten Ping nach. Die Shell rechnet die Chips beim Zeigen aus dem aktuellen Pfad (Eingabe `fuehrungsAngebote`). Specs. |
| 5 | mittel | Das Widget prüfte Muster anders als das Backend (Leerraum, Zeichensatz, „//“). | Gleicher Zeichensatz, `trim`, „//“ wird leer wie `rstrip`. Gespiegelte Fälle. |
| 6 | mittel | Ohne `persist-session` kommt eine Führung mit `ankunft` nie an. | Im Handbuch vermerkt. |
| 7 | mittel | In der Ablaufliste stand das rohe Wort `seite` (ebenso `extern`). | Beide in de/en. Spec. |
| 8 | mittel | Die Regel für Seitenmuster stand nur im Platzhalter (fest, deutsch). | Platzhalter aus dem Katalog; sichtbare Hilfe, verknüpft über `aria-describedby`, auch mit dem Fehler. |
| 9 | klein | Nur Kommas galten als Muster. | Fehler „Wert fehlt“. Spec. |
| 10 | klein | Kommentare und eine Bedingung, die nach der Änderung tot war. | Mit Befund 2 ist die Bedingung wieder nötig; die Kommentare sind nachgezogen. |
| 11 | mittel | Plan (F-4, F-7) nicht nachgeführt, E2E fehlt. | Plan nachgeführt. **E2E zurückgestellt** zugunsten einer Browser-Abnahme der ganzen Führung gegen ein echtes Backend (AS-7, nach AS-7c); eingetragen in `offene-befunde` §1. |

**Prüfung nach den Behebungen:** ui 1374, widget 94, studio 2121, ESLint sauber.

## Deploy

Backend, Studio und Widget-Bündel neu bauen. Keine Migration, keine neue Variable.
