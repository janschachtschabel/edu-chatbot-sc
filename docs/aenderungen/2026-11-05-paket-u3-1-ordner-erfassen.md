# Paket U3-1: Ordner erfassen und als Themenbaum-Entwurf übernehmen (2026-11-05)

Plan: [`../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md`](../plans/2026-11-04-pakete-sammlungsstrukturen-upload-mcp.md)
(Fassung 3, §16.5). Entwicklerdoku: [`../ui-module.md`](../ui-module.md) §2.5, §6;
Modul: [`../../frontend/projects/ui-module/src/ui-upload/README.md`](../../frontend/projects/ui-module/src/ui-upload/README.md).

## Was die Person jetzt kann

Die KI zeigt ein Auswahlfeld „Ordner und Dateien“. Die Person wählt einen Ordner oder legt ihn ab; im
Browser entsteht ein Baum mit Dateizahlen je Ordner. Sie kann Dateien ignorieren, ein Strukturdokument
(z. B. einen Lehrplan) markieren und dann
- „Als Themenbaum-Entwurf übernehmen“: die Ordnerstruktur erscheint **ohne KI-Aufruf** als
  bearbeitbarer Strukturentwurf („Entwurf (aus Ordnern)“, führende Nummern und Unterstriche bereinigt);
- „Befund senden“ oder einfach weiterschreiben: die KI bekommt Ordnernamen und Zahlen, gerahmt.

Hochgeladen wird in diesem Paket **nichts**; Dateinamen verlassen den Browser nicht.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| ui-module | neues Modul `ui-upload/` (Custom Element, nachgeladen, 6,7 kB gzip): Erfassen, Rollen, Antwort, Baum, Texte, Styles, Manifest, README, Specs |
| ui-module | `ui-strukturentwurf`: `quelle` + `ordner`, Marke „Entwurf (aus Ordnern)“ |
| Register | `module-register.mjs` erzeugt zusätzlich `nachlade-quellen.generated.ts` (Element-Quellen **nur fürs Studio**) |
| Studio | Vorschau lädt nachgeladene Module über diese Quellen; Spec liest Shadow-DOM-Text |
| Backend | Dienst `upload_angebot` (`ui_module/dienst_upload.py`); Antwortform `ui_module/upload_antwort.py` (Rahmen `[ORDNER DER PERSON …]`, Übersicht ≤ 3000 Zeichen, Sicherheitsprüfung liest die Ordnernamen); **Verzeichnis der Antwortformen** `ui_module/antwort_formen.py` (Strukturentwurf verhaltensgleich umgezogen), `ui_module/rahmen.py`; Endmarke `ORDNER` in `domain/endmarken.py` |
| Backend | „Ordner → Entwurf“: `ui_module/strukturentwurf_ordner.py` (ohne LLM, drei Ebenen, Deckel), `services/ordner_aktion.py`, Haken in `graph/nodes/preflight.py` hinter dem Sicherheitstor der Direktaktionen; Texte `action.folderDraft.*` (de/en) |
| E2E | `e2e/upload-erfassen.spec.ts` (Nachladen mit SRI, echte Ordnerauswahl, Tastatur, getippte Nachricht, 320 px); Harness liefert `/widget/module/*` mit CORS |

**Verschoben:** der Studio-Bereich `01-base/upload-config` (Schalter „Dokument im Chat“, „Ablage in
WLO“) kommt mit U3-2, wo die erste dieser Funktionen entsteht. Ganz an- und abschalten lässt sich
`ui_upload` schon jetzt über den Modul-Schalter des Studios.

## Review (2026-11-05) — Befunde und Behebung

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Antwort-Schema ohne Tiefen- und Gesamtdeckel (rekursives `$ref`): sehr tiefe Bäume → `RecursionError` im Vorlauf | feste Ebenen `ordner1…ordner9` (Wurzel + 8, letzte ohne Kinder), Gesamtzahl ≤ 500 in `upload_antwort.grund` | `test_ein_zu_tiefer_baum…` (Tiefe 8/9/300), `test_mehr_als_500_ordner…` (vorher rot) |
| 2 | MAJOR | Fokus fiel nach Auswahl / „Andere Auswahl“ auf `body` | Ersatzziel je Zustand (Befund-Zeile, Fehlermeldung, „Ordner wählen“), nur wenn der Fokus im Modul lag | Spec (vorher rot) + „nimmt der Seite den Fokus nicht“ |
| 3 | MINOR | `daten.hinweis` der KI nie gezeigt | Satz der KI über der Fläche, sonst der feste | Spec |
| 4 | MINOR | Textfassung nannte Ordner-Entwurf „Entwurf (KI)“ | `_KOPF` + `ordner` | Backend-Test |
| 5 | MINOR | Hinweis „gekürzt“ sprach von einer WLO-Sammlung | eigener Satz für `quelle: ordner` | Spec |
| 6 | MINOR | Sicherheitsprüfung las nur die gedeckelte Übersicht, der Entwurf nimmt andere Ordner | bei `ordner_als_entwurf` zuerst die Kompaktfassung genau des entstehenden Entwurfs | Backend-Test (vorher rot) |
| 7 | MINOR | Datenschutz-Satz verschwieg den Namen eines markierten Strukturdokuments | Satz ergänzt | Spec |
| 8 | MINOR | „Als Themenbaum-Entwurf übernehmen“ auch ohne Unterordner | Knopf nur mit Unterordnern | Spec |
| 9 | MINOR | Ablegen neben der Fläche öffnete die Datei im Browser; zweite Auswahl während des Lesens; veraltete Erfassung nach Lesefehler | Ziehen/Ablegen im ganzen Modul abgefangen, Knöpfe beim Lesen gesperrt, Erfassung im Fehlerfall verworfen | Specs |
| 10 | MINOR | fehlende Tests (Deckel, `grund`, `vorsatz`/`frage_satz`, Moderation aus, Kürzungsmarke) | ergänzt | Backend-Tests, Vorab-Stufe |
| 11 | MINOR | markiertes Strukturdokument im zugeklappten Ordner nicht mehr sichtbar | Name im Hinweis | Spec |
| 12 | NIT | Mehrzahl per `n === 1` | `Intl.PluralRules` | Texte-Spec |
| 13 | NIT | Kürzen nach UTF-16 zerbrach Emoji | nach Codepunkten | Spec |
| 14 | NIT | toter Text; Rahmentext behauptete einen schon gezeigten Entwurf | entfernt; neutral gefasst | — |
| 15 | NIT | „nur lesend“ ohne Antwort ohne Satz; E2E räumte Temp-Ordner nicht auf | „Nicht verwendet.“; `afterAll` räumt auf | Spec, E2E |

Dazu: acht bestehende Backend-Tests zählten die Modul-Werkzeuge namentlich auf — `ui_upload` ist dort
als neues Agent-Werkzeug nachgetragen (gewollte Änderung).

## Prüfung (nach der Review-Runde)

- Frontend: `ng test` ui-module 214, ui 1150, widget 76, studio 1963 bestanden; Skript-Tests (Register
  14, Bündel 4, Modul-Budget 4); eslint, `check:tokens`/`a11y`/`radii`/`docs` sauber; Playwright
  **90/90** (inkl. `upload-erfassen`, zuvor `--repeat-each 3` 12/12).
- Backend ganz mit Postgres: **8085 bestanden, 4 übersprungen**; ruff sauber.
- Bündel: Haupt-Bündel **190,59 kB gzip** — knapp über der Warnschwelle (190), unter der Grenze (200);
  der Zuwachs gegenüber U3-0 ist der gemeinsame Platzhalter (bis U3-0 wegoptimiert). Modul-Bündel
  `ui-upload` 6,9 kB gzip.

## Deploy

Keine Migration, keine neue Umgebungsvariable. Master-Skill-Regel für `ui_upload` folgt in U3-5.
