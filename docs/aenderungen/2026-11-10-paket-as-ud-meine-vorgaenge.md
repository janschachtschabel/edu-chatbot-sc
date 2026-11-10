# Paket AS-Ud — „Meine Vorgänge“ (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5j (Entscheide Ud-1 … Ud-5, „Ud-5 neu“).

**Für die Person:** Angemeldet steht neben „Abmelden“ ein Knopf „Meine Vorgänge“ (Symbol Verlauf).
Er klappt über dem Eingabefeld eine Liste der eigenen, offenen Vorgänge aus **anderen** Gesprächen
auf (alle offenen; bis zum Review AS-Ud hieß es „höchstens drei“). Je Vorgang zeigt sie:
- den Titel;
- den Zustand in Worten („Offen“, „Auftrag läuft“, „Wartet auf dich“) und das Datum;
- „Fortsetzen“ (wechselt in das Gespräch wie der Hinweis „Gespräch fortsetzen“);
- „Löschen“ mit Rückfrage im Panel. Gesammelte Daten gehen verloren, ein laufender Auftrag endet.

Laden, Fehler mit „Erneut versuchen“ und eine leere Liste haben je einen Satz. Esc oder × schließt
die Liste, der Fokus geht an den Knopf zurück. Bei schmaler Breite (unter 364 px) bricht die
Eingabezeile um: Das Feld steht oben in voller Breite, die Knöpfe stehen darunter. Gemessen ohne
Umbruch blieben dem Feld bei 320 px nur 76 px.

**Backend:**
- `POST /api/ui/vorgaenge/liste` gibt `{vorgaenge: [{id, titel, ablauf, status, session_id,
  geaendert}]}` zurück: nicht abgeschlossen, mit Gespräch, ohne das aktuelle Gespräch und ohne den
  Vorgang, auf den es verweist. Dazu der Dienst `vorgaenge.eigene` (die jüngsten zuerst, höchstens
  `LISTE_HOECHSTENS` = 20 als Sicherung, seit Review AS-Ud, Befund 3).
- `POST /api/ui/vorgaenge/loeschen` mit `{session_id, vorgang}` gibt `{geloescht: true}` zurück.
  - Fremd, unbekannt oder der Vorgang des aktuellen Gesprächs: 404 `unbekannt`.
  - Ein offener Auftrag endet nach dem Festschreiben auch bei der b-api, mit dem Schlüssel der
    Person.
- Für beide gilt wie bei `/offen`: nur mit bestätigter Anmeldung, `no-store`, IP-Drossel.
- Vertragszusätze und OpenAPI sind nachgeführt.

**Widget:**
- `shell/meine-vorgaenge.ts` ist der Controller ohne DOM. Er lädt, fragt nach und löscht. Eine Antwort
  gilt nur für das Gespräch und den Block, mit denen gefragt wurde. Abmelden, ein neuer Block und ein
  Neustart vergessen alles.
- `shell/meine-vorgaenge.component.ts` ist die Anzeige mit Fokusführung und Live-Region.
- In der Shell gibt es nur die Verdrahtung (Knopf, Panel, Fortsetzen über `_zumVorgang`).
- Neu sind die Texte `vorgaenge.*` (de/en).

**Entscheid nach Messung (Ud-5 neu):**
- „Meine Vorgänge“ kostet +3,15 kB gzip und bleibt trotzdem im Hauptbündel, denn der Knopf steht für
  jede angemeldete Person in der Eingabezeile und ist keine seltene Oberfläche.
- Zum Ausgleich wird das Debug-Panel nachgeladen (BU-3).
- Bis dahin: 190,6 kB gzip, also knapp über der Warnschwelle und deutlich unter der Grenze von 200 kB.

**Prüfung:**
- Backend: `test_ui_vorgaenge_liste` (15) und `test_vorgaenge` (PG, 13). Mit Vertrag und i18n sind
  es 86 grün; ruff sauber.
- Vitest: ui 1302, widget 93, studio 2116.
- Playwright 106/106, darunter `meine-vorgaenge.spec.ts`:
  - 320 px: Umbruch;
  - 400 px: eine Zeile;
  - Tastatur: Öffnen, Rückfrage, Löschen und Esc samt Fokus.
- ESLint sauber.

**Review (10.11., unabhängig):** 0 kritisch, 0 schwer, 8 mittel, 5 klein. Alle sind behoben oder
bewusst entschieden.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Ein Wechsel über den Hinweis „Gespräch fortsetzen“ oder `vorgangFortsetzen` setzte die Liste nicht zurück. Das Panel zeigte das alte Gespräch oder blieb auf „lädt“. | mittel | `_zumVorgang` vergisst die Liste nach jedem Wechsel. Shell-Spec. |
| 2 | Rennen: Löschen mitten in einem Zug, der gerade einen Auftrag anlegt. Ein Fremdschlüssel-Fehler ergab einen 500er, der Job lief verwaist. | mittel | (a) „Löschen“ und „Ja“ sind während eines Zugs gesperrt; (b) `loeschen` sperrt die Zeile (`FOR UPDATE`) vor dem Lesen des Auftrags; (c) `vorgaenge.FESTHALTEN_KONFLIKTE` = `VorgangKonflikt` oder `IntegrityError` an allen sechs `festhalten`-Stellen (zug ×3, auftrag_zug, freigabe_zug, wahl_zug): Rückrollen, Auftrag bei der b-api beenden, Konflikt-Satz. Spec- und Backend-Test. |
| 3 | `LIMIT 3` griff vor dem Ausschluss. Wartende Vorgänge weichen nie, mehr als drei fielen aus der Liste. | mittel | Ausschluss `ohne_id` in der Abfrage; Sicherung `LISTE_HOECHSTENS` (20) statt `MAX_JE_PERSON`. PG-Test mit vier Vorgängen. |
| 4 | Laden, Fehler und leere Liste wurden Vorlesern nicht angesagt (gefüllt eingefügt oder ohne Live-Region). | mittel | EINE ständige Statuszeile für Zustand und Meldung. Spec. |
| 5 | Nach „Erneut versuchen“ fiel der Fokus ins Leere. | mittel | `erneut()` setzt den Fokus nach dem Laden auf den Titel. Spec. |
| 6 | Die Schwelle der Fußzeile rechnete ohne Mikrofon; `order: -1` drehte Sicht- und Tab-Reihenfolge um. | mittel | Kein `order` mehr. Mit Mikrofon gilt die Schwelle 408 px, Mikrofon und Feld teilen die erste Zeile (`box-sizing: border-box` für die Basis). E2E bei 380 px mit Mikrofon. |
| 7 | Testlücken: Verwerfen des Hinweises nach dem Löschen, „Stand prüfen“ nach dem Fortsetzen, Aufruf des Personen-Schlüssels, `no-store` an der 403. | mittel | Specs ergänzt; der Test prüft den Schlüssel-Aufruf mit `pflicht=False` und die Reihenfolge Schlüssel → Sperre → Löschen → Festschreiben → b-api. |
| 8 | Der Vorspann und `lauf → ablauf` standen dreimal da; die 403 von `/offen` hatte kein `no-store`. | mittel | `/offen`, `/wiederkehr`, `/liste` und `/loeschen` teilen `_angemeldet`, `_ablauf_von` und `_als_offener`. Die 403 von `/offen` trägt jetzt `no-store`. Test. |
| 9 | Löschen nahm Abgeschlossenes und Vorgänge ohne Gespräch an, obwohl die Liste sie nicht zeigt. | klein | 404 wie Fremdes (Ud-3). Test. |
| 10 | Esc in der Rückfrage schloss das ganze Panel. | klein | Esc schließt erst die Rückfrage, dann das Panel. Spec. |
| 11 | Ein zweiter Tab des gelöschten Gesprächs zeigt bis zum nächsten Zug eine tote Leiste. | klein | Bewusst hingenommen, dokumentiert in Plan §5j. |
| 12 | Debug-`console.log` im E2E. | klein | Entfernt. |
| 13 | Der Kommentar an `OffenerVorgang.status` nannte `/liste` nicht. | klein | Nachgezogen. |

**Prüfung nach den Behebungen:**
- Backend: 859 Tests (Abläufe, Vorgänge, Arbeitsstand, Vertrag, i18n); ruff sauber.
- Vitest: ui 1309, widget 93, studio 2116.
- Playwright 107/107.
- ESLint sauber.
- Budget 190,6 kB gzip; BU-3 folgt.
