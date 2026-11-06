# Paket A2a: Auslöser ohne Knopf und die Frist des Vorgangs (2026-11-05)

Plan: [`../plans/2026-11-05-vorgang-und-ablaeufe.md`](../plans/2026-11-05-vorgang-und-ablaeufe.md) §4,
§9 (Feinentwurf A2). Baut auf A1 auf ([`2026-11-05-paket-a1-ablaeufe.md`](2026-11-05-paket-a1-ablaeufe.md)).

## Was entsteht

Ein Ablauf startet jetzt nicht nur per Knopf:

- **KI schlägt vor** (`{art: agent}`): Im Agent-Modus bekommt die KI das Werkzeug `ablauf_vorschlagen`,
  wenn ein aktiver Ablauf diesen Auslöser trägt (Titel, „wann“, „wann nicht“ in der Beschreibung, die
  Kennungen als Aufzählung). Es startet nichts: unter der Antwort erscheint ein Knopf
  (`__action__|<Titel>|ablauf_starten|{"ablauf": …}`, die Form kennt das Widget schon), die Person
  entscheidet. Die KI schreibt den Knopf nie selbst; höchstens ein Vorschlag je Zug, keiner unter einer
  offenen Frage.
- **Wendung** (`{art: text, wendungen: [...]}`): Kommt eine Wendung in der getippten Nachricht vor
  (Groß-/Kleinschreibung und Leerraum egal), startet der Ablauf — in beiden Maschinen, im Preflight hinter
  derselben Sicherheitsprüfung wie ein Knopf. **Keine regulären Ausdrücke**: Studio-Text im Zug wäre ein
  ReDoS-Risiko (Befund U3-2).
- **Modul-Antwort** (`{art: modul, modul, wenn_teil}`): Eine geprüfte Antwort dieses Moduls, die zu keinem
  Lauf gehört und den Teil `wenn_teil` bringt, wird Teil des Vorgangs; der Ablauf startet **nach** seinem
  Schritt mit diesem Modul. Geprüft vor der Ordner-Aktion.
- **Frist im Studio:** `01-base/privacy-config` → `logging.vorgang_tage` (1–30 Tage, Vorgabe 3) statt der
  Konstante; eine unlesbare Frist gilt als Vorgabe (verlängert nichts).

Voraussetzungen gelten für jeden Auslöser; bei einer Modul-Antwort ohne erfüllte Voraussetzung geht die
Antwort still den gewöhnlichen Weg. Der mitgelieferte Ablauf trägt jetzt `knopf`, `agent` und `text`
(weiter aus).

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Modell | `Ausloeser.art` + `text`, Feld `wendungen`; `PrivacyLoggingBlock.vorgang_tage` |
| Backend | `services/ablauf/ausloeser.py` (Katalog lesen, `per_text`, `per_modul`, `vorschlaege`), `vorschlag.py` (Werkzeug, Knopf); `zug.starten_mit`/`per_modul_starten`/`text_ausloeser`/`modul_ausloeser`; `treiber.starten(ab=)` |
| Backend | `pruefung`: Wendungen (1–10, je 4–80 Zeichen), Modul-Auslöser braucht einen Schritt mit dem Modul und einen danach, `wenn_teil` gültig |
| Backend | `graph/nodes/preflight.py`: Modul-Auslöser vor der Ordner-Aktion, Wendung bei getippter Nachricht; `agent_tools`/`respond_agent`/`agent_loop` (virtuelles Werkzeug, `AgentRun.ablauf_vorschlaege`); `turn_assembly` setzt den Knopf |
| Backend | `arbeitsstand.tage()` liest die Frist; `zug` und `arbeitsstand` nutzen sie |
| Seed | `06-ablaeufe/katalog.yaml` (Auslöser), `01-base/privacy-config.yaml` (`vorgang_tage: 3`) |
| Studio | Feldtexte `Ausloeser.wendungen`, `art.wahl.text`, `PrivacyLoggingBlock.vorgang_tage` (DE/EN); Hinweise aktualisiert; Schema-Fixture neu |

## Tests

Neu: `test_ablauf_ausloeser` (Katalog, Wendung kein Regex, aus/ohne Auslöser, Modul-Start nach dem Schritt,
ohne Teil kein Start, Prüfung der Auslöser), `test_ablauf_vorschlag` (Werkzeug nur mit Vorschlagbarem,
Aufzählung, Knopf-Form und Sprache, Reihenfolge, Schleife merkt ohne MCP, unbekannte Kennung abgewiesen);
ergänzt: `test_ablauf_zug` (Modul-Auslöser, Voraussetzung, Wendung), `test_preflight_node` (Wendung nach der
Sicherheitsprüfung, hohes Risiko, ohne Wendung gewöhnlich, Modul-Auslöser vor der Ordner-Aktion),
`test_turn_assembly` (Knopf vorn, nicht unter offener Frage), `test_arbeitsstand` (Frist aus dem Studio).

Läufe nach den Review-Fixes: Backend 8362 grün, Studio 1967; ruff und eslint sauber.

## Review A2a (2026-11-05, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 3 MAJOR, 4 MINOR, 2 NIT, 2 Vorbefunde. Geprüft und in Ordnung: jeder Start hinter
`assess_safety` mit durchgereichten Werkzeugsperren, Schreibregel unberührt, offene Schreib-Abnahme vor jedem
Auslöser, Krisenzüge laufen im Agent-Modus über das Muster (kein Vorschlag), unbekannte/abgeschaltete Kennung
vom Modell unmöglich, Knopf-Beschriftung und Parameter ohne Einschleusung, kein doppeltes Speichern,
`vorgang_tage` übersteht `PUT /api/config/privacy`.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Eine Wendung während eines wartenden Laufs ersetzte ihn still | Wendung nur ohne wartenden Lauf (`zug.lauf_wartet`, nur Verweis) | `test_eine_wendung_waehrend_eines_wartenden_laufs_ersetzt_ihn_nicht` |
| 2 | MAJOR | Krisennachricht mit zufälliger Wendung bekam die Abweisung statt M01 | Nur-Wendung bei hohem Risiko oder ohne Prüfung → gewöhnlicher Weg (protokolliert dort) | `test_eine_wendung_bei_hohem_risiko_geht_den_gewoehnlichen_weg` |
| 3 | MAJOR | Modul-Start positionell (`i+1`) statt über `weiter`, Wahl der Antwort verloren | `modul_start` folgt `nachfolger`; `gewaehlt` der Antwort an `treiber.starten` | `test_der_modul_start_folgt_dem_weiter…`, `test_der_modul_start_nimmt_die_wahl…` |
| 4 | MINOR | KI schlug Abläufe mit unerfüllter Voraussetzung vor | `ausloeser.erfuellt` (zentral) filtert `vorschlaege` | `test_die_ki_schlaegt_nichts_vor…` |
| 5 | MINOR | Vorschlag nach einer Frage quittiert, Knopf erschien nie | nach einer Frage wie jedes Werkzeug abgewiesen | `test_nach_einer_frage_kein_vorschlag` |
| 6 | MINOR | Knopf missachtete Chips und Höchstzahl des Gastgebers | nicht unter Gastgeber-Chips, `hoechstens=_host_qr_max` | `test_unter_chips_des_gastgebers…`, `test_der_knopf_achtet_die_hoechstzahl…` |
| 7 | MINOR | Testlücken (Wartender Lauf, `weiter`, Verdrahtung `respond_agent`, Abweisungstext) | ergänzt | `test_ein_vorschlagbarer_ablauf_wird_angeboten…`, `test_ohne_vorschlagbaren_ablauf_kein_werkzeug`, Abweisung prüft den Text |
| 8 | NIT | Handler zwischen J1-Kommentar und seinem Code | verschoben | — |
| 9 | NIT | Leerer Titel → leere Knopf-Beschriftung | Rückfall auf die Kennung | `test_ein_leerer_titel_wird_die_kennung` |
| V1 | Vorbefund | KI-Schnellantworten konnten einen Knopf (`__action__`-Vorsatz) tragen (Klick = Direktaktion) | `filtere_vorschlaege` verwirft `__action__`- und `__auth__`-Vorsätze | `test_ki_schnellantworten_tragen_keine_knoepfe` |
| V2 | Vorbefund | Direktaktion startete jeden aktiven Ablauf, auch ohne `knopf` | nur mit Auslöser `knopf` oder `agent` (`ausloeser.per_knopf`) | `test_der_knopf_startet_nur_einen_ablauf_mit_knopf…` |
| — | Log-Wächter | Kennung eines kaputten Eintrags im Log (`test_log_ohne_inhalt`) | Nummer statt Kennung | `test_logaufrufe_tragen_keine_inhalte` |
