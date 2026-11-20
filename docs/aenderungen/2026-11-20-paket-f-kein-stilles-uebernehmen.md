# Paket F: Ein neues Gespräch übernimmt keinen Vorgang still (2026-11-20)

Plan: `docs/plans/2026-11-20-konto-vorgaenge-und-warten-auf-volltext.md` §6, Fehler F, Entscheid E-F
(ersetzt Review V1, Befund 1). Keine Migration, keine neue Variable, kein Widget-Bau nötig.

## Befund

Mit Anmeldung holte `arbeitsstand.auffrischen` im ersten Zug eines neuen Gesprächs den jüngsten
offenen Vorgang der Person (`vorgaenge.juengster`) in die Sitzung. Wartete dessen Lauf an einer Frage
mit Freitext, wurde die erste Nachricht des neuen Gesprächs („Hallo“, ein Start-Chip) still als
Antwort gespeichert. `/api/ui/vorgaenge/offen` bot den Vorgang dann nicht an (er galt als „schon
hier“). Nachgestellt mit einer Anmelde-Attrappe gegen die Wegwerf-DB (Durchtest R3).

## Änderung

- `services/arbeitsstand.py`
  - `auffrischen`: der Zweig `juengster` fällt weg. Ohne Verweis bleibt das Gespräch ohne Vorgang.
  - `_speichern`: der Rückgriff auf `juengster` fällt ebenfalls weg. Ein Teil aus einem neuen
    Gespräch (Upload, Entwurf) legt einen eigenen Vorgang an, statt still im jüngsten zu landen und
    ihn samt Lauf hereinzuholen.
- `services/ablauf/wahl_zug.py` (`_fortsetzen`, Sicherung): eine Wahl oder ein Freitext zählt nur,
  wenn die Nachricht aus dem Gespräch kommt, in dem der Lauf zu warten begann (`Vorgang.session_id`,
  gesetzt von `zug_basis.festhalten`). Sonst `None` — der Zug geht den gewöhnlichen Weg; am Lauf
  wird nichts gespeichert oder abgebrochen.
- `api/ui_vorgaenge.py` (`/offen`): schließt den Vorgang, auf den ein Verweis des aktuellen Gesprächs
  zeigt, nicht mehr aus — nur noch die Vorgänge des aktuellen Gesprächs (`ohne=session_id`).
  `/liste` und `/loeschen` ebenso seit dem Review (siehe unten).
- `api/ui_auftrag.py` (`/stand`): der Rückgriff R1-d auf den jüngsten offenen Vorgang fällt weg; er
  setzte das alte Verhalten des Preflights voraus. Nur der Vorgang des Verweises zählt.
- Unverändert: ohne Anmeldung gehört ein Vorgang der Sitzung; meldet sich die Person im selben
  Gespräch an, geht er auf sie über (`anonymen_uebernehmen`).
- `vorgaenge.juengster` ist seit dem Review entfernt (NIT 4).

## Tests

- `tests/test_paket_f_kein_stilles_uebernehmen_pg.py` (neu, Postgres): neue Sitzung → kein Verweis,
  „Hallo“ ist kein Freitext, `offene` nennt den Vorgang; nach „Fortsetzen“ (Gespräch des Vorgangs)
  zählt die Antwort; mit einem Verweis aus einem anderen Gespräch wird weder Text noch Chip die
  Antwort.
- `tests/test_arbeitsstand.py`: `test_e_f_eine_neue_sitzung_uebernimmt_keinen_vorgang_still` ersetzt
  den Test zu Review V1, Befund 1.
- `tests/test_ui_vorgaenge_api.py`: `test_e_f_auch_der_vorgang_eines_verweises_wird_angeboten`
  ersetzt den Test zu Review K2a, Befund 1.
- `tests/test_ui_auftrag_api.py`: die beiden R1-d-Tests erwarten jetzt 409.
- Docstrings: Durchtest K (`test_preflight_node.py`), Z-3 (`test_paket_s4_plan.py`).

## Doku

`docs/ablaeufe.md` (neuer Abschnitt „Gespräch und Vorgang“), `docs/ui-module.md` (Begriffe),
Hinweise „überholt“ in den Plänen 2026-11-05, 2026-11-08, 2026-11-09 und 2026-11-12, Nachtrag
„Umgesetzt“ im Plan 2026-11-20 §6.

## Review behoben (20.11.)

- **MAJOR 1 — jeder Weg, nicht nur Wahl/Freitext:** zentral in `arbeitsstand.auffrischen` (läuft im
  Preflight vor allen Ablauf-Wegen): zeigt der Verweis einer angemeldeten Person auf einen Vorgang,
  dessen Lauf in einem anderen Gespräch wartet (`vorgaenge.wartet_woanders`: Status wartend,
  `session_id` gesetzt und anders), fällt der Verweis weg (Log ohne Kennung). In der Tiefe:
  `zug_basis.gehoert_hierher(v, session_id)`; `festhalten` wirft dann `VorgangKonflikt` (der
  Aufrufer rollt zurück, ein eben gestarteter Auftrag endet wie bei jedem Konflikt), `abbrechen`
  mit `session_id` (Abbruch der Person: Freigabe, Auftrag, Leiste) gibt `None` zurück.
  `zug.fortsetzen` (Modul-Antwort) und `zug.nach_uebernahme` (KI-Entwurf) prüfen vorher, weil sie
  Teile vor dem Festhalten speichern. Damit zieht auch `festhalten(..., session_id=...)` die
  `session_id` eines fremden Laufs nicht mehr um.
- **MINOR 2 — Sackgasse im Altbestand** (fremde Chips, Sperre durch fremden Auftrag, „mitten in …“):
  mit 1 erledigt — der fremde Verweis ist nach dem ersten Zug weg.
- **MINOR 3 — „Meine Vorgänge“:** `/liste` und `/loeschen` blenden nur nach `session_id` aus, nicht
  mehr nach dem Verweis; `_angemeldet` liefert nur noch die Besitzerin.
  (`vorgaenge.eigene(ohne_id=…)` bleibt als Abfrage-Möglichkeit mit eigenem Test, wird aber nicht
  mehr genutzt.)
- **NIT 4:** Kommentar in `zug_basis.festhalten` an E-F; `vorgaenge.juengster` samt Test-Attrappen
  entfernt (`test_ablauf_zug.py`, `test_ablauf_auftrag.py`, `test_paket_s_zug.py`,
  `test_ui_auftrag_api.py`, `test_arbeitsstand.py`); `test_vorgaenge.py` prüft nur noch die
  Bereinigung; der Wächter in `test_arbeitsstand.py` prüft, dass es `juengster` nicht mehr gibt.
- Tests: `tests/test_paket_f_review.py` (Altbestand je Lauf-Art; „Stand prüfen“, Auftrag
  abbrechen, „Weiter im Ablauf“, Modul-Antwort, `festhalten` aus einem anderen Gespräch),
  `tests/test_paket_f_review_freigabe.py` (Freigabe erneut/abbrechen, erster Zug in B),
  `test_ui_vorgaenge_liste.py` (zwei Tests an MINOR 3 angepasst).

## Kontrolle behoben (20.11.)

- **1 Seiten-Ping** (`seite_zug.angekommen`, läuft vor dem Preflight ohne `auffrischen`): ein kleiner
  Block vor `_frage_erneut` — wartet der Lauf des Verweises in einem anderen Gespräch, wird nichts
  gerechnet, keine fremde Frage gezeigt, der Verweis still entfernt (`update_session`), Antwort leer.
  (Die Datei bearbeitet G2 parallel; nur dieser Block ist von hier.)
- **2 Verlauf** (`api/sessions._ablauf_stand`): dieselbe Regel — keine Leiste für einen Lauf, der
  woanders wartet; Kommentar an E-F.
- **3 `zug_basis.schliessen(..., session_id=)`**: `VorgangKonflikt` bei fremdem Lauf; Aufrufer
  `vorgang_aktion.neu` und `zug._ziel_vorbereiten` übergeben `req.session_id`.
- Zusätzlich `freigabe_zug._laden`: eine Freigabe aus einem anderen Gespräch (Box eines Auftrags,
  „Vorschau erneut zeigen“, Abbrechen) löst weder eine Vorschau noch einen Start beim MCP aus.
- **5** `wahl_zug._fortsetzen` nutzt `zug_basis.gehoert_hierher` (eine Regel).
- **6** `vorgaenge.eigene(ohne_id=…)` entfernt; der PG-Test prüft nur noch „mehr als drei“.
- **7** Docstring `gehoert_hierher`: welche Aufräum-Wege bewusst ohne Prüfung bleiben und warum.
- **8 (vorbestehend)** `freigabe_zug._festhalten`: nach einem Konflikt `nicht_festgehalten(aus)` —
  ein eben gestarteter Auftrag endet wieder.
- Tests: `test_paket_f_review.py` (Leisten-Abbruch, Wendung, KI-Entwurf übernehmen, neues Vorhaben,
  `schliessen`, ganzer Preflight mit Chip → „gilt nicht mehr“, Punkt 8),
  `test_paket_f_review_seite.py` (Ping an Seite und an Frage einer Führung),
  `test_paket_f_review_auftrag_freigabe.py` (Freigeben/Verwerfen der Box aus B),
  `test_ablauf_leiste_endpunkte.py` (Leiste im Verlauf).

## Beim Deploy

Nur Backend-Image. Sitzungen, die vor dem Deploy still einen Vorgang übernommen haben, verlieren den
fremden Verweis im ersten Zug, solange dessen Lauf woanders wartet — danach keine fremden Chips,
keine Sperre, keine Leiste; „Fortsetzen“ bietet den Vorgang an. Ein Verweis auf einen Vorgang ohne
wartenden Lauf bleibt (freie Arbeit bleibt erreichbar).
