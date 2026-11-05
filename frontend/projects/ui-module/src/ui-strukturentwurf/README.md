# ui_strukturentwurf

Eine **neue** Gliederung (Themenbaum), die es so in WLO noch nicht gibt — von der KI entworfen
oder aus einer WLO-Sammlung übernommen —, die die Person im Chat bearbeitet, herunterlädt und
übernimmt (Paket U2, Plan [`docs/plans/2026-11-04-paket-u2-themenbaum-entwurf.md`](../../../../../docs/plans/2026-11-04-paket-u2-themenbaum-entwurf.md)).
Den **Bestand** zeigt `ui_themenbaum` (`../ui-themenbaum/`); beide teilen Baum, Tasten, Ansage und
Aussehen über `../_baum/`. Der Kopf sagt „Entwurf (KI)“ bzw. „Entwurf (aus WLO)“ — ein Entwurf
sieht nie aus wie Bestand.

- **Art:** abfragend (`antworten`, `herunterladen`). Erstes Modul mit **Dienst**
  (`dienst: {name: strukturentwurf, parameter}`): die KI nennt nur den Auftrag — `thema`, `fach?`,
  `bildungsstufe?`, `anzahl_oben` (5–20, sonst 10), `tiefe` (1–3, sonst 2), `hinweise?`,
  `vorlage?`, `vertiefen?`, `erneut_zeigen?` —, das Backend erzeugt die Ebenen von oben nach unten
  (`backend/src/boerdi/services/strukturentwurf_dienst.py`): Ebene 1 in einem Aufruf, Ebene 2 je
  Punkt parallel (höchstens die Hälfte des Anbieter-Deckels, höchstens 5 zugleich), Ebene 3 nur bei `tiefe: 3` und nur, wo das Modell sie
  vorsieht. Was die Frist nicht schafft, steht als `ausstehend` („Unterthemen fehlen noch“).
- **Eingabe** (`wlo.sammlungsstruktur@1`, Teilmenge): `titel`, `quelle` (`ki`/`wlo`), `thema?`,
  `fach?`, `bildungsstufe?` (WLO-Label), `wurzel_wlo_id?`, `gekuerzt?`, `knoten[]` — je Punkt
  `id`, `titel` (≤ 120), `beschreibung?` (≤ 300), `keywords[]?` (≤ 8 × ≤ 40), `fach?`,
  `bildungsstufe?`, `wlo_id?`, `ausstehend?`, `kinder[]`. Deckel: oben ≤ 30, Kinder ≤ 15, Tiefe ≤ 4
  (im Schema als `ebene1` … `ebene4`), gesamt ≤ 250 (Backend und `entwurf-regeln.ts`).
- **Bearbeiten:** Baum nach APG „Tree View“ wie der Bestand; Leiste für den aktiven Punkt
  (Unterpunkt, Punkt danach, Hoch, Runter, Einrücken, Ausrücken, Löschen, Rückgängig mit 20
  Schritten) und Detailfeld (Titel, Beschreibung, Schlagworte durch Komma). Keine Eingabefelder im
  Baumeintrag. Tasten im Baum: F2 oder Enter (Blatt) → Titelfeld, Enter/Esc dort → zurück
  (Esc schließt nicht das Chat-Fenster), Entf oder Rücktaste löschen, Alt+Umschalt+↑/↓
  verschieben, Alt+Umschalt+→/← ein-/ausrücken, Strg+Z rückgängig. Jede Aktion sagt die
  Statuszeile an, ein unmöglicher Schritt seinen Grund. Aus der Leiste bleibt der Fokus am Knopf,
  nach Rückgängig am Punkt (oder seinem Geschwister/Elternpunkt), nach „Übernehmen“ auf der
  Statuszeile. Scheitert der Zug, bleibt der bearbeitete Stand.
- **Antwort:** „Übernehmen“ → `host.antworten({…Stand, uebernommen: true, bearbeitet})`, Blase
  „Entwurf „…“ übernommen (N Punkte).“ Außerdem merkt das Modul den Stand bei jeder Änderung vor
  (`host.vormerken`): tippt die Person eine Nachricht, solange der Entwurf offen ist, geht er mit
  (`uebernommen: false`) und der Block wird `beantwortet` statt `veraltet`. Leere Titel werden vor
  dem Senden „Neuer Punkt“ (das Schema verlangt einen).
- **An die KI:** im Zug, der den Entwurf zeigt, nur eine Quittung (Zahlen und erste Ebene); im
  Folgezug der mitgeschickte Stand **kompakt** (Titel und Einrückung, ≤ 6000 Zeichen), gerahmt
  `[ENTWURF DER PERSON …]`; genau diese Kompaktfassung liest auch die Sicherheitsprüfung, vor der Nachricht. Beschreibungen und Schlagworte der Person gehen an kein Modell (beim Vertiefen nur Titel aus dem sichtbaren Teil).
- **Später im Gespräch:** die Sitzung merkt sich den letzten Entwurf (nach der
  Sicherheitsprüfung: die Antwort der Person oder ein erzeugter Entwurf; nie ein Brücken-Entwurf,
  den die Person nicht zurückgeschickt hat — die Brücke vergisst sogar einen älteren) für die fünf
  Züge nach dem Antwort-Zug — als `vorlage` und als Rahmen `[DEIN LETZTER ENTWURF]`;
  `erneut_zeigen` zeigt ihn unverändert wieder zum Bearbeiten. Ein sehr großer Entwurf (über
  60 000 Zeichen) wird ohne Beschreibungen und Schlagworte gemerkt; dann lehnt `erneut_zeigen` ab
  (Vertiefen geht weiter).
- **Herunterladen:** JSON (`{"typ": "wlo.sammlungsstruktur@1", …}`) und Markdown — auch nur lesend.
- **Nur lesend** (`beantwortet`/`veraltet`): zeigt die Antwort der Person bzw. den ursprünglichen
  Entwurf mit „Übernommen.“, „Mit deiner Nachricht gesendet.“ oder „nicht mehr offen“.
- **Grenzen / offen:** keine Übergabe an Kestra/B-API (die Datei ist die Übergabe), kein Drag &
  Drop, kein „Unterthemen vorschlagen“ je Punkt ohne Zug (Sicherheitsprüfung), keine URIs für
  Fach und Bildungsstufe, Wurzel-Titel nicht bearbeitbar.

Beispiel (Block-Daten):

```json
{ "titel": "Optik in Klasse 8", "quelle": "ki", "fach": "Physik", "bildungsstufe": "Sekundarstufe I",
  "knoten": [ { "id": "k1", "titel": "Ausbreitung des Lichts", "keywords": ["Lichtstrahl"],
                "kinder": [ { "id": "k1-1", "titel": "Lichtquellen" } ] },
              { "id": "k2", "titel": "Reflexion", "ausstehend": true } ] }
```
