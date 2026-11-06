# Paket V2: Datenübergabe über den Vorgang, deklarativ im Manifest (2026-11-05)

Plan: [`../plans/2026-11-05-vorgang-und-ablaeufe.md`](../plans/2026-11-05-vorgang-und-ablaeufe.md) §3, §6.
Baut auf V1 auf ([`2026-11-05-paket-v1-vorgang-kern.md`](2026-11-05-paket-v1-vorgang-kern.md)).

## Was entsteht

UI-Module, Dienste und Werkzeuge geben Daten **ohne Ablauf und ohne Umweg über das Modell** weiter:

- Ein Modul sagt im Manifest, welche Teile seine geprüfte Antwort im Vorgang hinterlässt
  (`vorgang.schreibt`) und welche sein Dienst liest (`vorgang.liest`). Nur erlaubte Teile werden gespeichert;
  ein Modul ohne eigene Normalform hinterlässt seine geprüften Antwortdaten unter dem ersten Namen.
- Die KI übergibt einen Teil an ein Werkzeug als `{"$teil": "<name>"}` (die Namen stehen in der Kennzeile,
  die jetzt auch sagt, wie). Das Backend setzt den Wert **vor** Schreibsperre, Vorschau und Abnahme ein —
  die Person sieht und bestätigt den echten Wert. Fehlt ein Teil, wird das Werkzeug nicht gerufen.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Vertrag | `manifest.schema.json`/`manifest.ts`: Feld `vorgang {schreibt[], liest[]}`; `ui_upload` schreibt `structure, document`, `ui_strukturentwurf` schreibt `draft` und liest `structure, document, draft` |
| Backend | `services/teil_verweise.py` (`einsetzen`, `fehlertext`; nur die reine Form, Namen geprüft, Tiefe ≤ 6); Einbau in die Agent-Schleife (vor `gate.prepare`) und die Muster-Schleife (direkt nach dem Parsen) |
| Backend | `arbeitsstand.teile_aus_antwort` filtert nach `vorgang.schreibt`, allgemeiner Teil für andere Module; Kennzeile endet mit dem Hinweis zur Übergabe |
| Doku | `docs/ui-module.md`: Manifest-Feld `vorgang` |

## Tests

Neu: `test_teil_verweise` (Ersetzen, Verschachtelung, fehlende Teile, Formen, Tiefe, Agent-Schleife setzt ein,
fehlender Teil ruft das Werkzeug nicht); ergänzt: `test_arbeitsstand` (Filter nach Manifest, allgemeiner Teil,
Kennzeile).

## Review V2 (2026-11-05, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 2 MAJOR, 5 MINOR, 4 NIT. Geprüft und in Ordnung: Einsetzen vor `strip_confirm_token`,
`gate.prepare`, Merkposten und `_call_key`; die Abnahme führt die gespeicherten, schon eingesetzten
Argumente aus; Rückweg ins Prompt gerahmt.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | jedes Werkzeug bekam Teile — auch lesende Fremdwerkzeuge ohne Vorschau (Datenabfluss bei Prompt-Injection) | `teil_verweise.darf`: nur kuratierende WLO-Werkzeuge mit Abnahme und Module mit `vorgang.liest`; sonst Fehlertext, kein Aufruf | `test_nur_werkzeuge_mit_vorschau…`, `test_ein_nicht_freigegebenes_ziel…`, `test_die_agent_schleife_gibt_einem_lesenden…` |
| 2 | MAJOR | Muster-Vorrunde setzte bei Modulen nicht ein (Engines verschieden) | `tool_loop_module._ergebnis` setzt nach dem Parsen ein, mit derselben Erlaubnis | `test_die_muster_vorrunde_prueft_teile…` |
| 3 | MINOR | eine Abnahme kann nach Bearbeiten des Entwurfs den gezeigten (älteren) Stand schreiben | **offen, bewusst:** ausgeführt wird genau, was die Person in der Vorschau sah; Verwerfen bei Teil-Änderung kommt mit Paket S (Freigabe) | — |
| 4 | MINOR | Verweis auf oberster Ebene ersetzte das ganze Argument; eingesetzt wurde das Objekt der Akte | oberste Ebene nie Verweis (nur der Treiber, mit geprüfter Definition); `copy.deepcopy` | `test_die_oberste_ebene…`, `test_eingesetzt_wird_eine_kopie` |
| 5 | MINOR | `vorgang.liest` nur Deklaration | jetzt wirksam (Befund 1); der Teil-Lader der Dienste bleibt ungefiltert — einziger Leser ist der Strukturentwurf (`draft`, deklariert) | — |
| 6 | MINOR | allgemeiner Teil ohne Labels, ungenutzt | entfernt (simplify, im Code vermerkt) | — |
| 7 | MINOR | Testlücken | Muster-Weg, Fremdziel, oberste Ebene, Kopie ergänzt; Bestätigungsweg mit `$teil` folgt in Paket S | siehe oben |
| 8 | NIT | Fehlt-Pfad ohne Stillstands-Erkennung | bewusst: die Fehlermeldung nennt den Grund, `max_iterations` begrenzt | — |
| 9 | NIT | Kennzeile kürzte Teil-Namen auf 20 | auf 30 wie `NAME` | — |
| 10 | NIT | Lesefehler erscheinen als „fehlt“ | Fehlertext sagt jetzt „nicht vorhanden oder nicht freigegeben“ | — |
| 11 | NIT | Plan-Status veraltet | Plan §9 nachgezogen | — |
