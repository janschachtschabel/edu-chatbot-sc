# Paket K1b: `ui_fortschritt` — der Stand eines Ablauf-Auftrags im Widget (2026-11-06)

Plan: [`../plans/2026-11-05-vorgang-und-ablaeufe.md`](../plans/2026-11-05-vorgang-und-ablaeufe.md) §9
(„K1b Feinentwurf“). Baut auf K1a auf ([`2026-11-06-paket-k1a-auftraege.md`](2026-11-06-paket-k1a-auftraege.md)).

## Was entsteht

Startet ein `auftrag`-Schritt einen b-api-Auftrag (Kestra-Flow), musste die Person bisher selbst auf
„Stand prüfen“ tippen. Jetzt zeigt der Treiber dazu das nachgeladene Modul **`ui_fortschritt`**:

- Es **fragt selbst nach** — erste Frage nach 5 s, dann 10, 20, 30 und alle 60 s; nicht, solange die Seite
  verborgen ist; nach 30 Minuten nur noch per „Jetzt prüfen“.
- Ist der Auftrag **fertig oder gescheitert**, lässt es das Ergebnis **im Zug der Person abholen** —
  dieselbe Direktaktion wie der Knopf „Stand prüfen“ (`ablauf_auftrag_pruefen`), ohne Nutzerblase. Dort
  werden die Ausgaben Teil des Vorgangs und der Ablauf geht weiter (K1a).
- Der Knopf „Stand prüfen“ bleibt darunter: ohne JavaScript, mit ausgeschaltetem Modul oder wenn das
  Bündel nicht lädt.
- Die **Job-ID kommt nie in den Browser**: der Block trägt nur `{ablauf, kuerzel, text}` (`kuerzel` = 12
  Hex-Zeichen aus sha256 der Job-ID).

Neuer öffentlicher Endpunkt **`POST /api/ui/auftrag/stand`** `{session_id, ablauf, kuerzel}` →
`{stand: laeuft|fertig|fehler}` — kein Zug, keine KI, **schreibt nichts**. Bremsen vor jeder b-api-Abfrage:
Sitzung (404), bestätigte Anmeldung (403 `nur_angemeldet`), der Lauf **dieser Person** wartet auf genau diesen
Auftrag (409 `kein_auftrag` — ein alter Block im Verlauf hört damit auf), durchgereichter Schlüssel der Person
(503 `nicht_abrufbar`, wie K1a). Endgültige Gründe der b-api (Auftrag unbekannt, Aufträge aus) → 409,
Schlüssel abgewiesen → 403 `abgewiesen`, sonst 503. IP-Drossel.

Neue Modul-Fähigkeit **`auftrag`** (Host-Methode `auftrag({schritt: 'stand'|'abholen', …})`), freigeschaltet
nur für Module, die sie im Manifest nennen.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Backend | `api/ui_auftrag.py` (neu, in `main.py`); `treiber._fortschritt` (Block nur, wenn das Modul aktiv ist; Satz ≤ 300 Zeichen); `auftraege.client.kuerzel`; `namen.FORTSCHRITT`; `config_models.ablauf.ID_FORM`; Text `action.ablauf.auftragGestartet` (DE/EN) |
| Vertrag | Fähigkeit `auftrag` (Schema, `ModulFaehigkeit`), `ModulHost.auftrag`, Typ `AuftragSchritt`, `ElementHost`/Brücke |
| Modul | `ui-fortschritt/` (Manifest, Element, `fortschritt-ablauf.ts` Nachfragen, Texte DE/EN, Stil, README); Register neu erzeugt |
| Widget | `BlockModulHost.auftrag` (Fähigkeit), `WidgetModulHost`/`ShellTreffer.auftrag`, `collection-actions.auftragStand`/`auftragAbholen`, `ChatApiClient.auftragStand`, Text `error.auftragAbholen`; `runCardAction` meldet jetzt, ob der Zug gelang (`boolean`, die anderen Aufrufer unverändert) |
| Studio | Vorschau-Host (`auftrag`: Stand „läuft“, Abholen angesagt), Texte `uiModule.faehigkeit.auftrag` und — bisher fehlend — `uiModule.faehigkeit.hochladen`, Vorschau-Spec kennt das Modul |
| API-Vertrag | `openapi-v1.json`/`openapi-public.json` neu erzeugt, Zusatz in `bewusste-vertragszusaetze.md`, Inventar und öffentliche Routen in `test_openapi_contract.py`, Codes in `test_i18n_messages.py` |
| Doku | `docs/ui-module.md` (Fähigkeit, Host-Tabelle samt `ablegen`, Modulzeile; `ui_upload` mit `oeffnen`, U3-3), Plan §9 |

Budget: Haupt-Bündel 192,31 kB gzip (vorher 191,78; Warnschwelle 190 schon vorher überschritten, Grenze
200); `ui-fortschritt` 3,6 kB gzip, nachgeladen zusammen 19,8 kB (Grenze 60).

## Tests

- Backend: `test_ui_fortschritt.py` (Kürzel, Manifest, Block beim Start, Vorgabetext, Modul aus, im Zug Block
  und Knopf, langer Satz), `test_ui_auftrag_api.py` (Stand ohne Inhalt und ohne Schreiben, nur zum wartenden
  Auftrag dieser Person, anderes Kürzel/Ablauf, andere Person derselben Sitzung, Sitzung, Anmeldung,
  Schlüssel, b-api-Gründe, Eingaben, Verbindung frei vor der Anmeldung).
- ui-module: `fortschritt-ablauf.spec.ts` (Abstände, Abholen, Zug läuft, nicht gesendet, 409/403/503,
  verborgen, 30 Minuten, „Jetzt prüfen“, keine Doppelfrage, Trennen, AbortError, Wiedereinhängen, Neu-Fragen
  vor dem Abholen), `ui-fortschritt.element.spec.ts` (Darstellung, Uhrzeit, `aria-disabled`, Fokus auf den
  Rahmen, Ansagen, nur lesen, Englisch).
- ui: Host-Fähigkeit, `auftragStand`/`auftragAbholen`, `ChatApiClient.auftragStand`.
- E2E `e2e/fortschritt.spec.ts`: echtes Bündel, „Jetzt prüfen“ → Abholen im Zug ohne Nutzerblase und ohne
  Job-ID, Nachfragen von selbst nach 5 s, 409, Tastatur auf 320 px.

Läufe nach den Review-Fixes: ui-module 291, ui 1174, Studio 1969, Widget 76, E2E 100 (fortschritt zehnfach
40/40), Backend 8538 (5 übersprungen); eslint, ruff, Token/Radien/A11y/Kontrast/Doku-Wächter sauber.

## Review K1b (2026-11-06, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 1 MAJOR, 5 MINOR, 3 NIT. Geprüft und in Ordnung: keine Job-ID und keine Ausgaben in der
Antwort; Reihenfolge Sitzung → Anmeldung → Besitz; IDOR über Besitz-Streuwert und `vorgaenge.lesen`; keine
b-api-Abfrage ohne den Schlüssel der Person; Block nur mit aktivem Modul; ein alter Block im Verlauf endet
mit 409.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Nach einem Zug (etwa „Stand prüfen“ getippt) holte `frei()` blind ein zweites Mal ab → „Diesen Ablauf gibt es hier nicht“ | vor jedem späteren Abholen (`frei`, „Ergebnis abholen“) erst neu fragen (`nachpruefen`); ist der Lauf weiter, kommt 409 → „abgeschlossen“ | `Befund 1` (zwei, Ablauf), Element „danach erst neu fragen“ |
| 2 | MINOR | Lese-Transaktion offen während der Anmeldungs-Bestätigung (MCP-Rundlauf) | Verbindung nach der Sitzungsprüfung freigeben | `test_befund_2_keine_verbindung_waehrend_der_anmeldung` |
| 3 | MINOR | Störung im Handbetrieb nicht sichtbar, Störung nie angesagt | eigener Satz im Handbetrieb; Ansage je (Phase, Störung) | zwei Element-Tests `Befund 3` |
| 4 | MINOR | Endgültige b-api-Gründe als 503 → 30 Minuten „versuche weiter“ | `unbekannt`/`aus` → 409, `abgewiesen` → 403 | `test_gruende_der_b_api` |
| 5 | MINOR | Schritt-Text über 300 Zeichen ließ den Block still wegfallen | auf 300 Zeichen gekürzt | `test_befund_5_…` |
| 6 | MINOR | Testlücken (andere Person, Rennen, Wiedereinhängen) | ergänzt | `test_befund_6_…`, `Befund 1`, `Befund 8` |
| 7 | NIT | Satz doppelt (Blase und Modul) | Modul zeigt ihn nicht mehr; er bleibt die Textfassung | Element-Test „nicht doppelt“ |
| 8 | NIT | Wiedereinhängen mitten in einer Frage hielt `prueft`/`holt` fest | `trennen` setzt beides zurück | `Befund 8` |
| 9 | NIT | Prüfung „Lauf wartet auf diesen Auftrag“ dreimal (`pruefen_knopf`, `pruefen`, Endpunkt) | **nicht geändert**: die drei Stellen unterscheiden sich bewusst (nur Verweis ohne DB; mit Abbruch; ohne Schreiben) — ein gemeinsamer Helfer bräuchte drei Schalter | — |

Nebenbefund, älter als K1b, nicht geändert: `runCardAction` lässt bei gewechselter Sitzung (`veraltet()`) den
Laden-Zustand stehen — so seit dem Frontend-Split; in `offene-befunde-und-todo.md` §5 eingetragen.

## Offen

- 403 `abgewiesen` (b-api lehnt den Schlüssel ab) zeigt das Modul wie „nicht angemeldet“ — der Client
  reicht den Code nicht durch (`postChat` kennt nur den Status). Genügt, bis K22 geklärt ist.
- V-4 (Frist eines Vorgangs mit laufendem Auftrag) und K16–K22 unverändert offen.
