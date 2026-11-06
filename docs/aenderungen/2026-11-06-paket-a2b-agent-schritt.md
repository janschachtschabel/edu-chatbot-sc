# Paket A2b: der Schritt „KI-Abschnitt“ (`agent`) im Ablauf (2026-11-06)

Plan: [`../plans/2026-11-05-vorgang-und-ablaeufe.md`](../plans/2026-11-05-vorgang-und-ablaeufe.md) §4,
§9 (Feinentwurf A2b). Baut auf A1/A2a auf ([`2026-11-05-paket-a1-ablaeufe.md`](2026-11-05-paket-a1-ablaeufe.md),
[`2026-11-05-paket-a2a-ausloeser.md`](2026-11-05-paket-a2a-ausloeser.md)).

## Was entsteht

Ein Ablauf kann jetzt einen freien Abschnitt enthalten, in dem die KI mit der Person arbeitet:

```yaml
- id: umbau
  typ: agent
  text: {de: "Jetzt bauen wir den Baum gemeinsam um."}
  agent:
    werkzeuge: [ui_strukturentwurf, search_wlo_all]   # lesende WLO-Werkzeuge, UI-Module mit Agent-Freigabe
    hinweis: {de: "Hilf beim Umbau; nichts anlegen."}
    ausgabe: draft                                    # muss vorliegen, bevor „Weiter“ fortsetzt
    zuege: 5                                          # danach verweist die KI auf „Weiter“
```

- Der Treiber hält am Schritt an (`wartet_ki`), zeigt dessen Text und den Knopf **„Weiter im Ablauf“**.
- Solange gilt jeder getippte Zug der KI: im **Agent-Modus** nur mit den Werkzeugen des Schritts (plus
  Antwort, Inhaltsrahmen, Ergebnis), in **beiden** Maschinen mit der Zeile `[ABLAUFSCHRITT — …]` vor der
  Nachricht (Ablauf, Schritt, Hinweis, Werkzeuge, Ziel-Teil, Zug n von m). Kein Ablauf-Vorschlag mitten im
  Schritt. Unter jeder Antwort steht „Weiter im Ablauf“.
- **„Weiter im Ablauf“** ist die Direktaktion `ablauf_weiter {ablauf}` — hinter derselben
  Sicherheitsprüfung, mit deren Werkzeugsperren. Fehlt der Teil `ausgabe`: `bei_fehler`, sonst ein Hinweis,
  und der Lauf wartet weiter.
- **Budget:** die Züge zählen je Schritt in der Sitzung; nach `zuege` sagt die Zeile der KI, dass das Budget
  erschöpft ist. Kein automatisches Weitergehen — die Person bleibt am Steuer (Abweichung vom ersten Entwurf,
  Plan §9).
- Ist der Ablauf aus oder sind seine Schritte geändert, engt nichts mehr ein, und „Weiter“ meldet „gibt es
  nicht“. Dafür trägt der Verweis in der Sitzung jetzt auch die `fassung` des Laufs.

Nebenbei behoben: ein Lauf, der ohne UI-Block endete (z. B. Nachricht → Ende), scheiterte an
`ChatResponse(ui=None)` — seit A1.

## Was sich ändert

| Bereich | Änderung |
|---|---|
| Modell | `AgentSchritt` (`werkzeuge`, `hinweis`, `ausgabe`, `zuege`), `Schritt.agent`, Art `agent` |
| Backend | `pruefung`: Block Pflicht, 1–10 Werkzeuge (lesend oder Modul mit Agent-Freigabe, nie schreibend), 1–20 Züge, Ausgabe-Teil gültig; `agent` zählt als Halt |
| Backend | `treiber`: `WARTET_KI`, Halt am Schritt, `weiter_ki`, `Ausgabe.fehlt_teil` |
| Backend | `services/ablauf/ki_schritt.py` (`aktueller`, `zeile`, `zaehlen`, `einengen`, `knopf`, `weiter_knopf`); `zug.weiter_nach_ki`, Knopf in der Antwort des Treibers, `lauf_wartet` auch für `wartet_ki` |
| Backend | `preflight`: Direktaktion `ablauf_weiter`; `respond_agent`: Zeile, Zählung, Einengung, kein Vorschlag im Schritt; `respond` (Muster): Zeile; `turn_assembly`: „Weiter im Ablauf“ (nicht unter offener Frage oder Gastgeber-Chips) |
| Backend | `arbeitsstand.verweis_fuer` mit `fassung`; Kennzeile nennt `wartet_ki`; `i18n`: `action.ablauf.weiterKnopf`, `action.ablauf.fehltNoch`, `action.ablauf.fertig` |
| Studio | Feldtexte `AgentSchritt.*`, `Schritt.agent`, `Schritt.typ.wahl.agent` (DE/EN); Schema-Fixture neu |

## Tests

Neu: `test_ablauf_ki_schritt` (Prüfung, Halt, Weiter mit/ohne Ausgabe, `bei_fehler`, nur aus dem wartenden
Schritt, aktueller Schritt, geänderte Schritte, Zeile samt Budget, Sprache und Klammern, Zählung je Schritt,
Einengung, Knopf, Kennzeile); ergänzt: `test_ablauf_zug` (Weiter bis zum Ende ohne Block, Hinweis ohne
Ausgabe, kein/anderer Lauf), `test_preflight_node` (Direktaktion mit Sperren), `test_respond_agent`
(Einengung, Zeile, Zählung), `test_turn_assembly` (Knopf, nicht unter offener Frage).

Läufe nach den Review-Fixes: Backend 8401 grün, Studio 1967; ruff und eslint sauber.

## Review A2b (2026-11-06, unabhängiger Prüfer) — Befunde und Behebung

Zählung: 0 CRITICAL, 3 MAJOR, 5 MINOR, 1 NIT. Geprüft und in Ordnung: die Einengung läuft **nach** Sperre,
Schreibregel und Modulmeldung (kann nur kürzen), nicht Angebotenes weist die Schleife ab; `ablauf_weiter` mit
Besitz, passender Kennung, `aktiv`, Status und Fassung; keine Doppelzählung zwischen den Maschinen; Budget-Grenze
richtig; Knopf nicht doppelt; Statusabbildung in der Datenbank konsistent.

| # | Schwere | Befund | Behebung | Test |
|---|---|---|---|---|
| 1 | MAJOR | Krisen-/Ablehnungszug (M01/M02) bekam die Ablaufzeile und zählte mit | `ki_schritt.fuer_zug`: nicht bei vorgegebenem Muster oder hohem Risiko (beide Maschinen) | `test_kein_ablaufschritt_unter_einem_vorgegebenen_muster` |
| 2 | MAJOR | Eine Modul-Antwort im agent-Schritt konnte per Modul-Auslöser den Lauf ersetzen | Modul-Auslöser nur ohne wartenden Lauf | `test_eine_modul_antwort_im_wartenden_lauf_startet_keinen_neuen` |
| 3 | MAJOR | Lange Hinweise schnitten den Budget-/Knopf-Satz ab | fester Kern vorn, Hinweis ≤ 200 und Titel ≤ 60 Zeichen; Prüfung weist längere Hinweise ab | `test_budget_und_knopf_ueberstehen_einen_langen_hinweis`, `test_ein_zu_langer_hinweis_ist_ein_befund` |
| 4 | MINOR | Zähler überlebte einen Neustart desselben Ablaufs | `starten_mit` setzt ihn zurück | `test_ein_neuer_lauf_zaehlt_seine_ki_zuege_neu` |
| 5 | MINOR | Wissensregel ohne Werkzeug; Zeile nannte gesperrte/nicht gemeldete Werkzeuge | im Schritt kein `wissen_suchen` samt Regel; Zeile nach der Einengung gebaut | `test_im_agent_schritt_bleibt_die_sperre_und_kein_wissen` |
| 6 | MINOR | Knopf-Name in der Zeile fest deutsch | `bot_text` wie der Knopf | `test_der_knopf_heisst_in_der_zeile_wie_im_widget` |
| 7 | MINOR | „Weiter“ nach Ausschalten/Ändern ließ den Lauf ewig warten (Wendungen blockiert) | Lauf wird `abgebrochen` | `test_weiter_nach_dem_ausschalten_bricht_den_lauf_ab` |
| 8 | MINOR | Testlücken (Muster-Weg, Sperre + Schritt, Abbruch, Zähler) | ergänzt (siehe 1, 4, 5, 7) | — |
| 9 | NIT | Muster-Weg sagte „Nur diese Werkzeuge“, engt aber nicht ein | dort „Bevorzuge diese Werkzeuge“ | `test_die_zeile_nennt_nur_angebotene…` |
