# Querschnitts-Review der Pakete seit 2026-11-05 (2026-11-06)

Umfang: nur Chatbot-Code (`boerdi-chat`), Pakete V1, V2, A1, A2a, A2b, K1a, K1b, U3-0, U3-1, U3-2a, U3-2b/c,
U3-3a, U3-3b. Jedes Paket hatte schon ein eigenes Review; hier ging es um das **Zusammenspiel**. Vier
unabhängige Prüfer (Vorgang-Kern, Abläufe, Upload-Backend, Frontend), nur lesend. Jeder MAJOR ist danach am
Quelltext nachgeprüft. Noch **nichts behoben** — Reihenfolge entscheidet der Nutzer.

Zählung: 0 CRITICAL, 7 MAJOR, rund 25 MINOR, rund 12 NIT. Gehalten haben: Schreib-Invariante (kein
Ablauf-Weg ruft ein schreibendes Werkzeug), Besitz/IDOR an Vorgang, Ablage und Auftrag, `$teil` nur an
erlaubte Werkzeuge, Job-ID und Schlüssel nie im Browser oder Log, SRI der nachgeladenen Bündel, Fremdtext nur
als `textContent`, Datei-Sicherheit (Rumpf-Grenze, Magic Bytes, Kindprozess mit Speichergrenze und Frist,
keine Dateinamen im Log).

## MAJOR (am Code bestätigt)

| # | Befund | Wo | Folge |
|---|---|---|---|
| M1 | Jeder Zug schließt die offene Frage — auch das automatische Abholen von `ui_fortschritt` | `services/ui_antwort.py:62` (`offene_frage_schliessen`), Frontend `shell-contexts.ts:128` | ein laufender Upload-Stapel wird „Nicht verwendet.“, die übrigen Dateien bekommen 409, `vorgang.json` fehlt; ein Strukturentwurf verliert Bearbeitungen |
| M2 | Ablage `datei`/`abschluss` verlangen die offene Frage | `api/ui_ablage.py:99-102` | ein getipptes „danke“ während der Übertragung bricht den Stapel ab; neuer Stapel → Dubletten |
| M3 | „unklar“ (`unverified`) ist im Backend endgültig, das Modul sendet es aber erneut | `api/ui_ablage.py:68,193`; `upload-uebertragen.ts:162` | erneutes Senden bringt nie den wahren Stand; eine nie angekommene Datei bleibt für immer unabgelegt |
| M4 | Wendungs-Auslöser prüft nur die ersten 500 Zeichen auf Sicherheit | `graph/nodes/preflight.py:184-185` → `direct_actions._direct_action_safety_text` | Krisenäußerung nach 500 Zeichen in einer Nachricht mit Wendung: Ablauf startet, M01 kommt nie (Regression seit A2a) |
| M5 | Frühe Antwortwege speichern den Verweis nicht | `services/ablauf/zug_basis.nur_text` (kein `update_session`), `zug.py`, `auftrag_zug.py` | veralteter Lauf hängt in der Sitzung: Werkzeuge eingeengt, Knopf „Weiter“/„Stand prüfen“ meldet immer „unbekannt“, Wendungen gesperrt — bis `vorgang_tage` |
| M6 | Ein Vorgang wird nie abgeschlossen | `zug_basis.STATUS` (fertig/abgebrochen → `aktiv`), kein anderer Schreiber | jede Person hat faktisch einen ewigen Vorgang: neue Vorhaben landen im alten (Titel, alte Teile, `vorlage` holt alten Entwurf), Frist verlängert sich bei jeder Nutzung, „3 je Person“ greift nie |
| M7 | DB-Verbindung über Netzaufrufe gehalten (Audit H-5 zurück) | `zug.fortsetzen`, `zug.weiter_nach_ki`, `auftrag_zug.pruefen`, `zug.wartet_auf` (über die Moderation) | Verbindungen „idle in transaction“ während MCP-, b-api- und Moderationsaufrufen |

## MINOR (Auswahl, nach Thema)

- **Upload:** `vorbereiten` überschreibt einen laufenden Stapel (zweiter Tab); `teile_speichern` schreibt nach
  `VorgangKonflikt` blind (verlorene Stände in `ablage`); Ordner-Brücke greift über `vorlage` auf einen alten
  `draft` zurück; Moderation sieht nur Übersicht und Anfang, Ebene 2 schickt spätere Abschnitte ungeprüft ans
  LLM (Entwurfslücke); `vorbereiten` prüft `max_mb` nicht.
- **Abläufe:** endgültige b-api-Gründe im Zug (`unbekannt`) → Endlos-Knopf; ein neuer Lauf schließt den Auftrag
  des alten nicht; Wendung ignoriert Voraussetzungen (anonyme Frage bleibt unbeantwortet); `fassung` ändert
  sich mit jedem neuen Schritt-Feld (`exclude_none`) → jeder Deploy bricht wartende Läufe ab; keine
  Längengrenzen für `titel`/`wann` in der Werkzeugbeschreibung.
- **Vorgang:** Verweis wird nie aus der DB aufgefrischt (zweite Sitzung, verlängerte Frist); `uebernehmen`
  verwirft ein gescheitertes Speichern; `$teil` ohne Größengrenze (bis 1 MB in Abnahme-Merkposten).
- **Datenschutz:** Historie (5 Fassungen je Teil) ohne Leser; kein Löschweg für den Vorgang einer Person; Teil
  `document` überdauert die 24 h des Dokuments und dessen Löschen; Datenschutz-Satz in `ui_upload` sagt
  „bleibt auf deinem Gerät“, auch wenn das Übertragen angeboten ist.
- **Frontend:** `modulAntworten` sendet für einen schon geschlossenen Block; Datei-Input wird bei jedem
  `beschaeftigt`-Wechsel neu gebaut (Auswahl geht verloren); zu viele Ansagen (je Datei, `role="alert"` bei
  jedem Zeichnen); unbestimmte Balken ohne Rücksicht auf reduzierte Bewegung.
- **Tests:** Ablauf-, Auftrags- und Ablage-Tests laufen nur gegen Speicher-Attrappen (kein `akte_version`, kein
  Konflikt); fehlend: zwei Sitzungen, Zug mitten im Stapel, zwei Module zugleich (E2E), `ablauf_auftrag_pruefen`
  durch den Preflight.
- **Dateien über 300 Zeilen:** `ablauf/pruefung.py` 361, `ablauf/treiber.py` 355, `arbeitsstand.py` 337,
  `strukturentwurf_dienst.py` 330, `preflight.py` 322, `ui-upload.element.ts` 387.

## NIT (Auswahl)

Totes `timeout` in `mcp_ablage._FEHLER_ARTEN`; zwei Wortschätze für `layout` (`folder`/`ordner`);
`umwandlung.py` schreibt/löscht blockierend in der Ereignisschleife; `MAX_AUSGABE_BYTES` zählt Zeichen;
`wartet_auf` schreibt vor der Sicherheitsprüfung; fehlender Index `vorgaenge.session_id`, Indexname-Drift in
0019; `nachladen.ts` `ERLAUBT` verankert den Pfad (API unter Präfix); Ladetext und Rückfallname `'Dokument'`
fest im Code; Doku nennt die Host-Brücke eine Sicherheitsgrenze; Plan §2 beschreibt `vorgang_auftraege` mit
nicht gebauten Spalten.

## Schon vorher da

- `api/widget.py:213-220` liefert für **jeden** 12-Hex-Digest das aktuelle Bündel, ein Jahr `immutable` — beim
  rollenden Deploy kann alter Inhalt unter neuem Namen im Browser-Cache landen (seit U3-0 mit Modul-Index).
- `services/rag/umwandeln.py:87-89` loggt den Ausnahmetext von markitdown; markitdown 0.1.6, `pip-audit` offen.
- Starlette legt Multipart-Rümpfe vor allen Prüfungen ab; 429 trägt den Satz des Servers als `detail`.
- `merge.py` übernimmt `_`-Entities des Klassifikators (V1 vermerkt).

## Entscheide, die beim Nutzer liegen

- **M6 — wann endet ein Vorgang?** Vorschlag: Ein Ablauf, der `fertig` endet, schließt den Vorgang, den er
  selbst angelegt hat; startet ein Ablauf auf einem Vorgang mit fertigem oder fremdem Lauf, entsteht ein neuer.
  Ohne Ablauf (freie Module) bleibt es beim jüngsten offenen Vorgang, dazu eine Aktion „neues Vorhaben“.
- **M1 — wie wird automatisch abgeholt?** Vorschlag: das Abholen schließt keine fremden offenen Fragen (wie ein
  Hintergrund-Zug), sein Ergebnis erscheint trotzdem als Antwort; `ui_upload` beendet beim Wechsel auf
  „nur lesen“ laufende Übertragungen sichtbar.
