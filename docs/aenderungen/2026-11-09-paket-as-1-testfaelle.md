# Paket AS-1 — Testfälle eines Ablaufs, simuliert (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5c,
Entscheid E4 („Testfälle plus Widget-Probe“, hier der erste Teil).

## Was sich ändert

- **Testfälle am Ablauf** (`tests`, höchstens 20).
  - **Was ein Testfall nennt:**
    - die Teile vor dem Start;
    - das Ergebnis je Werkzeug-Schritt (`null` = liefert nichts);
    - je wartendem Schritt eine Eingabe, höchstens 30: die Antwort eines Moduls, Auftrag fertig
      oder gescheitert, Freigabe ja oder nein, oder die Teile, die die KI hinterlässt;
    - was danach gelten soll: Weg, Status, Ende, Teile.
  - **Fassung:** Tests ändern die Fassung eines laufenden Ablaufs nicht, denn die hängt nur an den
    Schritten.
- **Simulation** (`services/ablauf/simulation.py`): der echte Treiber mit einer Attrappen-Umgebung.
  Kein LLM, kein MCP, kein Auftrag, keine Vorlage beim Server. Sie ist wiederholbar und kostet
  nichts.
  - **Antworten** werden wie im Zug zu Teilen.
  - **Ein „nein“** zur Freigabe lässt den Lauf warten.
  - **Abweichungen** stehen je Testfall als Text da: anderer Weg, Status oder Ende, fehlender Teil,
    eine Eingabe für einen anderen Schritt, eine nicht verbrauchte Eingabe.
- **Treiber:** drei Nähte der `Umgebung`, im Betrieb ohne Wirkung:
  - `ersatz`: Werkzeug-Ergebnis je Schritt statt Dienst oder MCP;
  - `simulation`: Module ohne Dienst; passen die Daten nicht zum Vertrag, steht ein Platzhalter-Block
    da;
  - `protokoll`: jeder besuchte Schritt.
- **Endpunkt** `POST /api/config/ablauf-testen`: Rumpf ein Ablauf, Antwort
  `{ergebnisse: [{name, ok, status, weg, ende, abweichungen}]}`. Studio-Schlüssel, schreibt nichts.
- **Studio:** In „Prüfen und Schrittfolge“ steht der Knopf „Tests ausführen“.
  - Je Testfall „Bestanden: …“ oder „Abweichung: …“ mit den Abweichungen.
  - Die Live-Region sagt „2 Testfälle: 1 bestanden, 1 abweichend.“
  - Eine Änderung macht das Ergebnis alt.
  - Ohne Testfälle steht ein Hinweis, wo man sie anlegt.
  - Die Testfälle selbst stehen im Formular unter „Tests“; Feldtexte gibt es auf Deutsch und Englisch.

## Wo

- **Backend:**
  - Modelle: `domain/config_models/ablauf.py` (`AblaufTest`, `TestEingabe`, `TestErwartung`).
  - Treiber: `services/ablauf/treiber.py` (Nähte) und `services/ablauf/treiber_bloecke.py`
    (`simulation`).
  - Simulation und Endpunkt: `services/ablauf/simulation.py` (neu) und `api/config_ablauf.py`.
- **Studio:**
  - Testlauf: `core/ablauf-api.service.ts` (`testen`) und `schema-form/ablauf-pruefen.component.ts`.
  - Schema-Typ: `schema-form/json-schema.ts` (`minLength`).
  - Texte: `i18n/catalogue/ablaeufe-seite.ts` und `i18n/catalogue/fields-ablaeufe.ts`.
- **Vertrag:** `docs/api/openapi-*.json` und `docs/api/bewusste-vertragszusaetze.md`.

## Tests

- **Backend** `tests/test_ablauf_simulation.py`:
  - Weg mit Werkzeug und Auftrag;
  - Werkzeug ohne Ergebnis und gescheiterter Auftrag, je nach `bei_fehler`;
  - Freigabe ja mit Teilen der KI und Freigabe nein;
  - ohne Eingabe am wartenden Schritt;
  - Abweichungen und eine Eingabe am falschen Schritt;
  - Fassung bleibt gleich, Deckel, alle Testfälle, Endpunkt.

  Eine Attrappe lässt jeden echten Dienst- und MCP-Aufruf scheitern.
- **Studio** `ablauf-pruefen.component.spec.ts`: ohne Testfälle, Ergebnisse mit Ansage und „geändert“,
  Fehler des Servers. Dazu `schema-to-fields.spec.ts` (fünf Felder mit freiem JSON, begründet).

## Review (2026-11-09)

Ein frischer Reviewer: 2 hoch, 7 klein, dazu Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| Hoch: Der Platzhalter-Block galt für jedes Modul. Bei falschen Daten wartete die Simulation, wo der Betrieb zu `bei_fehler` geht; ein grüner Test sagte also einen anderen Weg voraus. | Platzhalter nur für Module, die der Betrieb über ihren Dienst baut (`ui_upload`). Sonst wie im Betrieb: kein Block. |
| Hoch: Ein lesendes MCP-Werkzeug durfte in der Simulation ein Objekt liefern, im Betrieb liefert es Text. | Ein Nicht-Text-Ergebnis eines lesenden MCP-Werkzeugs wird zu JSON-Text. |
| Nach „nein“ war kein „ja“ mehr möglich. | „nein“ legt neu vor, wie „Vorschau erneut“; ein folgendes „ja“ gilt der neuen Vorlage. |
| Eine Eingabe ohne das, was der Wartepunkt braucht, galt still als „nein“ oder als leerer Erfolg. | Neue Abweichung „passt nicht zum Wartepunkt — erwartet: …“. |
| Ein Ablauf ohne Schritte ergab 500; ein nicht speicherbarer Ablauf konnte „bestehen“. | Vorher „Prüfen“: Mit Befunden besteht kein Testfall (Abweichung nennt den ersten Befund). Je Testfall abgefangen. |
| Startwege fehlten: Modul-Auslöser, ohne Anmeldung. | `ab` und `gewaehlt` (Beginn nach einem Modul); `angemeldet` (Voraussetzung, Aufträge und Freigaben); Status `nicht_gestartet`. |
| Der Hinweis zu `ergebnis` nannte die Form nicht. | Der Hinweis nennt `{outputs, dateien, texte}` und Pfade wie `outputs.x`. |
| Ein Wechsel des Ablaufs während eines Testlaufs ließ den Knopf gesperrt. | `leeren()` setzt auch den Testlauf zurück (Spec). |
| Last: kein Budget, große Rümpfe. | Rumpfgrenze 2 MiB für `ablauf-testen`, Zeitbudget 5 s je Ablauf („nicht ausgeführt“). |
| Kleinigkeiten | Eigener Fehlertext „Testen ging nicht“. Status in Worten statt Codes. Kennungen in `erwartet` gedeckelt. Die Testattrappe sperrt auch Modul-Dienste und Aufträge. |

**Bekannte Grenzen:**
- „Nichts zu ändern“ einer Freigabe-Vorschau ist nicht abbildbar.
- Werkzeuge, die die Sicherheitsprüfung eines Zugs sperrt, sind nicht abbildbar.
- Die Simulation schreibt ins gewöhnliche Log (nur Kennungen).
- `minLength` am Namen prüft erst der Server.

## Betrieb

Keine Migration. Studio- und Backend-Bild neu bauen. Eigene Rumpfgrenze für `POST /api/config/ablauf-testen`
(2 MiB).
