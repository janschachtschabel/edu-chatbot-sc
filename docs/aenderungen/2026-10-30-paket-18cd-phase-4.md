# Änderungsnotiz — Paket 18C/D, Phase 4: der Schnitt — `debug` nur für die Anlage

Stand 2026-10-30 · Basis `main` `6cadf11` (Phasen 1–3) · Plan
[`docs/plans/2026-10-29-paket-18cd-volle-umsetzung.md`](../plans/2026-10-29-paket-18cd-volle-umsetzung.md)

**Warum:** Bis hierher ging der Debug-Block jeder Antwort an jeden Client — Persona, Signale,
Entitäten, Spur, Kosten. Seit Phase 3 trägt jede Antwort zusätzlich den öffentlichen Teil `ui`.
Jetzt lesen Widget und Studio-Vorschau nur noch `ui`, und den Debug-Block bekommt nur die Anlage
selbst. Das Studio zeigt dafür, was ein Zug tat (Zugakte), und findet ihn über die Fehlernummer.

| Was | Wie |
|---|---|
| Schnitt im Backend | `POST /api/chat`, Strom-`result` und Verlauf: `debug` nur mit `darf_diagnose` (Studio-Proxy nach Anmeldung, gültiger `X-Studio-Key`, reiner Entwicklungsmodus), sonst `debug: null` bzw. im Verlauf kein `debug` |
| Trace-ID je Nachricht | der Verlauf gibt der Anlage `trace_id` je Nachricht mit — daraus liest das Studio die Fehlernummer der Antwort |
| Typ-Fokus live | `ui.type_focus` jetzt auch an der direkten Antwort, nicht nur im Verlauf |
| Widget | liest Muster (Tour, Kontext-Begrüßung), Typ-Fokus, Web-Links, Such-Metadaten, Boxen, Themenseite und vorbereitete Änderung aus `ui`; das Gastgeber-Ereignis `boerdi:routing-debug` ebenso — `persona` und `signals` nur mit Debug-Block, sonst leer |
| Debug-Panel des Widgets | mit Debug-Block wie bisher; ohne ihn Muster, Intent, Zustand und Werkzeuge aus `ui` und der Hinweis, dass die volle Diagnose im Studio steht (de/en) |
| Fehlernummer im Widget | scheitert der Strom, nennt die Fehlerblase die Nummer aus dem `error`-Rahmen (nur Zeichen einer Trace-ID) |
| Studio: Zugakte | im Gesprächsverlauf je Antwort die Fehlernummer und, eingeklappt, die Werkzeugaufrufe (Status, Dauer, Antwortlänge, Fehler; Argumente aufklappbar, die gesendeten nur bei Abweichung) und Umschreibungen (vorher/nachher); leere Akte, kein Abschnitt |
| Studio: Suche | auf der Gesprächsseite das Feld „Fehlernummer“: ein Treffer öffnet den Verlauf an der Nachricht (auch außerhalb der gefilterten Liste), mehrere als Liste; Lade-, Leer- und Fehlerzustand |
| Vertrag | `ChatResponse.debug` nullable in `openapi-v1.json` und `openapi-public.json`; eingetragen in `docs/api/bewusste-vertragszusaetze.md` |

## Was sich im Betrieb ändert

| Was | Muss | Kann |
|---|---|---|
| Image | Backend-Image neu bauen (enthält Widget und Studio) und ausrollen | |
| Migration | `0016` einspielen, falls noch nicht geschehen (kam mit Phase 1; ohne sie fehlt `trace_id` an den Nachrichten, und Suche und Fehlernummer im Studio bleiben leer). Phase 4 bringt keine neue Migration | |
| Browser-Plugin | Bündel neu holen: im Ordner `examples/chrome-plugin` `node scripts/fetch-widget.mjs <backend>` — ein altes Bündel liest `debug` und verliert gegen das neue Backend Tour-Erkennung, Typ-Fokus und die Wiederherstellung von Boxen | |
| Golden-Läufe, Evaluation | `STUDIO_API_KEY` in der Umgebung des Laufs — ohne ihn fehlen Muster, Werkzeuge und Spur im Bericht (der Lauf warnt) | |
| Host-Seiten mit `emit-routing-debug` | | `persona` und `signals` sind jetzt leer; Muster, Intent, Zustand, Werkzeuge und Modulationen kommen wie bisher |
| Eigene Clients | | `ui` statt `debug` lesen (Phase 3) |

## Prüfung

- Backend: `antwort_fuer`/`verlauf_fuer` (anonym nur `ui`, Anlage mit `debug` und Trace-ID),
  `/api/chat` und Strom anonym und mit Schlüssel, Verlauf anonym und über den Studio-Proxy,
  `get_messages` mit Trace-ID (Postgres), Typ-Fokus live an `ui`. Volle Suite grün.
- Widget: Specs je Abnehmer auf `ui` umgestellt (zuerst rot), Debug-Panel ohne Debug-Block,
  Gastgeber-Ereignis ohne Persona und Signale, Fehlernummer aus dem Strom. E2E-Vorlage ohne
  `debug`; Playwright grün; Bündel im Budget, `grep` findet `type_focus`, nicht mehr `_type_focus`.
- Studio: Leser der Zugakte (jedes Feld geprüft), Komponente im Verlauf, Suche mit allen Zuständen,
  Sprung zur Nachricht; `check:contrast` (Feldrahmen) und Lint grün.
