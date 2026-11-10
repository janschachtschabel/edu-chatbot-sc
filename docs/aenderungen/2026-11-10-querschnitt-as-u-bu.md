# Querschnitts-Review AS-U + BU — Behebungen (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5k (Befunde Q-1 … Q-20 mit Entscheid und Stand).

**Anlass:** Die Pakete AS-Ua/Ub/Ud und BU-1…3 waren einzeln reviewt. Der Blick über alle zeigte
4 schwere, 12 mittlere und 4 kleine Befunde. Weil es mehrere schwere waren, folgt ein zweites,
unabhängiges Review.

**Schwer:**
- **Q-1 — Leiste nach dem Neuladen auch für Angemeldete.**
  - Der Verlaufsabruf trug keinen Zugangsblock, der Verweis gehört aber der Person. Die Leiste fehlte
    also nach Neuladen, „Fortsetzen“ und Wiederkehr.
  - Jetzt schickt das Widget den Block mit (`accessBlockHeaders`). `_ablauf_stand` übernimmt ihn
    und bestätigt die Anmeldung, aber nur mit Block. Anonyme Abrufe kosten also keinen MCP-Rundlauf.
  - CORS ist global offen.
- **Q-2 — Kein Schreiben ohne Lauf.**
  - Löschte „Meine Vorgänge“ den Vorgang, blieb ein offener Schreib-Plan im anderen Gespräch
    liegen. „Plan fortsetzen“ hätte weiter in WLO geschrieben.
  - `plan_fortsetzen.weiter` setzt einen Plan mit Ablauf-Marke jetzt nur fort, solange der Verweis
    auf einen Lauf dieses Ablaufs in `wartet_freigabe` zeigt. Sonst verwirft es ihn
    (`write.planNone`).
- **Q-3 — Trusted Types.**
  - Der nachgeladene Strukturentwurf setzte seine Symbole per `innerHTML`. Auf Seiten mit
    `require-trusted-types-for 'script'` wirft das.
  - Jetzt sind die Symbole Daten (`viewBox`, `d`) und werden mit `createElementNS` gebaut. Eine
    Spec lässt String-Zuweisungen an `innerHTML` werfen.
- **Q-4 — Das Eingabefeld bleibt erreichbar.**
  - Debug-Panel, Leiste, „Meine Vorgänge“ und Hinweis stapelten sich und schoben bei wenig Höhe
    die Eingabe weg.
  - Jetzt stehen sie in einem Bereich `.ueber-eingabe`: höchstens die halbe Widget-Höhe, er scrollt
    selbst. Die `vh`-Grenzen entfallen.
  - Solange die Liste offen ist, ruht der Hinweis (Q-18).
  - E2E bei 320 × 360 px. Gegen den Stand ohne Behebung ist der Test nicht gelaufen; die
    Rechnung stammt aus dem Review.

**Mittel und klein:**
- **Q-5:** „Arbeitsstand löschen“ sperrt die Vorgänge der Besitzerinnen vor dem Lesen der Aufträge
  (`vorgaenge.alle_sperren`, `FOR UPDATE`), wie `/loeschen`. Dazu ein PG-Test.
- **Q-6:** `/loeschen` meldet `auftrag_laeuft_weiter`, wenn ein Auftrag ohne den Schlüssel der
  Person bei der b-api weiterläuft. Das Widget sagt das in einem eigenen Satz.
- **Q-7:** `/liste` liefert `lauf_status`. Die Liste nennt den Laufstatus („Wartet auf deine
  Freigabe“, „Die KI ist dran“, „Ablauf beendet“) statt des gröberen Vorgangsstatus.
- **Q-8:** `/liste` und `/offen` nehmen `sprache`. Der Titel eines Ablaufs kommt in ihr, sofern der
  Vorgang von diesem Ablauf stammt (`zweck`).
- **Q-9:** Der Plantext ist berichtigt; der nächste Zug übernimmt den jüngsten offenen Vorgang
  (bewusst, Review V1).
- **Q-10:** Die Hülle des Debug-Panels setzt erst die Werte und hängt dann ein, wie der
  Element-Vertrag. Einen gemeinsamen Helfer mit dem Modul-Platzhalter gibt es nicht: zwei Nutzer
  mit verschiedenem Rückfall.
- **Q-12:**
  - Der Leisten-Knopf heißt „Einklappen“ / „Collapse“ (vorher „Später fortsetzen“). „Fortsetzen“
    heißt jetzt überall: in das Gespräch wechseln.
  - Ein Glossar steht in `docs/ui-module.md`.
- **Q-13 bis Q-15, Q-19:** Doku berichtigt:
  - `offene-befunde` §1 und §4; das Chip-Problem steht jetzt in §1;
  - BU-a als überholt markiert;
  - „höchstens drei“ durch „alle, Sicherung 20“ ersetzt;
  - `ui-module.md` Z. 33/426;
  - 190,6 kB.
- **Q-16:** Tests an den Nahtstellen:
  - Kontrast-E2E für Leiste und Liste (hell/dunkel);
  - E2E bei 320 × 360 mit allen drei Bereichen;
  - Trusted-Types-Spec;
  - Backend-Tests für Q-1, Q-2, Q-5, Q-6, Q-7, Q-8.
- **Q-11, Q-17, Q-20:** schon mit dem Review von BU-3 erledigt.

**Prüfung:**
- Vitest: ui 1330, ui-module 347, widget 93, studio 2116.
- Playwright 110/110.
- ESLint und ruff sauber; `module:register --pruefen` aktuell.
- Budget: 187,3 kB gzip.
- Backend: volle Suite 9564 bestanden, 5 übersprungen (24:43 min).

**Deploy:** Backend und Widget-Bündel neu bauen. Keine Migration, keine neue Variable.

**Zweites, unabhängiges Review (10.11., Plan §5l):** 17 von 20 Behebungen stimmten am Code; Q-6,
Q-8 und Q-16 waren unvollständig. Neu: 0 kritisch, 1 schwer, 7 mittel, 3 klein. Alle sind behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| Z-1 | `fetchHistory` wartete nicht auf den Ticket-Tausch; nach einer Anmeldung lud niemand den Stand neu. In einem neuen Tab fehlte die Leiste weiter. | schwer | `fetchHistory` wartet auf die Anmeldung. Nach gelungener Anmeldung holt die Shell den Stand einmal nach (`_standNachladen`); er gilt, bis eine neue Serverantwort kommt, und fällt bei einem Wechsel weg. Specs. |
| Z-2 | `/offen` bekam keine Sprache. | mittel | Mitgeschickt. Spec. |
| Z-3 | Die Plan-Prüfung verglich nur Ablauf und Status; ein übernommener anderer Vorgang desselben Ablaufs hätte den alten Plan weiterschreiben lassen. | mittel | Auch Schritt und Freigabe-Kennung (neu im Verweis: `freigabe_id`). Tests. |
| Z-4 | `alle_sperren` ohne Reihenfolge, ein Deadlock endete als Fehler. | mittel | `ORDER BY id`; ein Deadlock (40P01) in „Arbeitsstand löschen“ antwortet als Konflikt. Test. |
| Z-5 | Ein anderswo gelöschter oder beendeter Vorgang zeigte auch nach dem Neuladen eine tote Leiste. | mittel | Der Verlauf liest den Vorgang einmal; fehlt er oder ist er abgeschlossen, kein Stand. Tests. |
| Z-6 | Die Bestätigung im Verlauf konnte bis zu 5 s warten. | mittel | Frist 1 s, danach ohne persönlichen Stand. Test. |
| Z-7 | Der Satz nannte „ohne deine Anmeldung“ als Ursache; die Rückfrage versprach das Ende ohne Bedingung. | mittel | „läuft bei der b-api weiter … dieser Zugang darf ihn dort nicht beenden“; Rückfrage „wird hier beendet“. |
| Z-8 | Nach dem Abmelden blieb die Leiste mit Abbruch und Daten stehen. | mittel | `ui.ablauf.persoenlich`; ohne Zugangsblock blendet das Widget eine persönliche Leiste aus. Spec. |
| Z-9 | `/loeschen` prüfte vor der Sperre. | klein | Erst sperren, dann lesen und prüfen. Test. |
| Z-10 | Stände in §5k, Zahl 186,9, alte Kommentare. | klein | Angeglichen. |
| Z-11 | Zwei verschachtelte Scrollflächen (Debug-Panel im Bereich über der Eingabe). | klein | Das Panel begrenzt sich nicht mehr selbst. |

**Prüfung nach dem zweiten Review:**
- Vitest: ui 1336, ui-module 347, widget 93, studio 2116.
- Playwright 110/110.
- Backend: 1233 Tests der berührten Bereiche grün; ruff und ESLint sauber.
- Budget 187,5 kB gzip.
