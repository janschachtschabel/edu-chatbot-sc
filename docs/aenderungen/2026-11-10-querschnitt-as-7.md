# Querschnitts-Review AS-7 (Führungen) — Behebungen (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5m. Das Review lief über AS-7a/b/c und folgte
vier Abläufen Ende-zu-Ende durch Backend, Widget und Studio.

- **Was trägt:** Startweg, Speicherung und Wiederherstellung des Stands, Seiten-Ping, Wartestatus,
  F-5 (getippter Text) und die gleiche Mustersemantik in Backend und Widget.
- **Gefunden:** 0 kritisch, 2 schwer, 6 mittel, 3 klein. Alle wurden am Code geprüft und behoben,
  außer Befund 4, der als Grenze festgehalten ist.

| # | Schwere | Befund | Behebung |
|---|---|---|---|
| 1 | schwer | Nach dem Neuladen oder einem anderen Link war der Weg zur Seite weg: Wiederhergestellte Blasen tragen keine Chips, und ein Ping ohne Treffer ist leer. | Der Stand trägt bei `wartet_seite` den Weg (`AblaufStand.weg {label, url}`, `fortschritt._weg`). Die Leiste zeigt ihn als Knopf („Zur Mitmach-Seite“), der wie der Führungs-Chip navigiert. Tests im Backend und in der Leiste. |
| 2 | schwer | Ein Schritt, dessen Ankunft schon erfüllt war, zeigte trotzdem seinen Chip, und zwar vorn („Zur Startseite“ auf `/home/`). | Chip nur ohne `ankunft` oder wenn noch gewartet wird. Test. |
| 3 | mittel | Ein abgeschalteter oder geänderter Ablauf bei `wartet_seite` hing: ohne Stand kein Ping, und das Aufräumen kannte nur `wartet_wahl`. | `wahl_zug.aufraeumen` räumt auch wartende Führungen auf (`seite_zug.wartend`). Test. |
| 4 | mittel | Bei angemeldeten Personen fehlt der Stand nach dem Zeitlimit von 1 s für die Bestätigung (Z-6), und dann pingt das Widget nicht. | **Als Grenze festgehalten** (`offene-befunde` §1): Ist der MCP beim Seitenaufruf langsamer als 1 s, kommt die Ankunft dieses eine Mal nicht an. Der nächste getippte Satz holt den Chip zurück (F-5), der nächste Seitenaufruf pingt wieder. |
| 5 | mittel | Das Begrüßungsangebot zeigte auch Abläufe mit der Voraussetzung „Anmeldung“; anonym gäbe es nur eine Abweisung. | `seiten_angebote` lässt sie weg (das Boot-Bündel kennt die Anmeldung nicht). Test; im Handbuch vermerkt. |
| 6 | mittel | Die Gründe ungültiger Muster standen auch im englischen Befund auf Deutsch; der englische Text nannte den Schlüssel `if_page`. | `seiten_muster.fehler` liefert Codes, die Prüfung übersetzt sie. `wenn_seite` im Text. Test. |
| 7 | mittel | Die Studio-Hinweise zu Auslöser und Schrittart nannten „Seite“ nicht; das Musterbeispiel `/mitmachen*` passte nicht zur Empfehlung im Handbuch. | Texte de/en nachgezogen, Beispiel `/mitmachen/*`. |
| 8 | mittel | Die Texte des Beispiels beschrieben die Zielseite, erscheinen aber vor dem Wechsel. | Als Ankündigung formuliert („Als Nächstes …“); im Handbuch als Regel. Dass die Leiste Verzweigungen mitzählt, bleibt wie für alle Abläufe. |
| 9 | klein | Ein Muster durfte ein Komma tragen, das der Regel-Editor als Trenner liest. | Komma in Backend und Widget nicht mehr erlaubt. Tests. |
| 10 | klein | Auf Seiten mit Kontext-Gruß entfällt die Begrüßung und mit ihr das Angebot. | Im Handbuch vermerkt. |
| 11 | klein | Doku: Plan nannte noch den Endpunkt `ablauf-seiten` und Doku in `ui-module.md`; die Vertragsliste nannte `ablauf_seiten` nicht. | Plan, Vertragsliste und Handbuch nachgezogen. |

**Vertrag:** `openapi-public.json` hat das Feld `AblaufStand.weg` und das Schema `AblaufWeg` dazu
bekommen (`docs/api/bewusste-vertragszusaetze.md`).

**Deploy:** Backend, Studio und Widget-Bündel neu bauen. Keine Migration.
