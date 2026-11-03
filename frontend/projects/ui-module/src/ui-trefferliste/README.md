# ui_trefferliste

Die WLO-Treffer einer Antwort — Themenseiten, Sammlungen, Materialien, Such-Absprung (Paket U1-c2).

- **Entsteht automatisch:** das Backend leitet den Block an der API-Grenze aus `cards`,
  `query_metas` und `pagination` ab (`backend/src/boerdi/ui_module/abgeleitet.py`; im Verlauf aus
  der Kartenspalte und `_query_metas`). Bei Typ-Fokus ohne Karten, nur mit dem Such-Absprung; bei
  Führungs-Nachrichten nicht. Ein Muster schaltet ihn mit `ui_module:` ohne `ui_trefferliste` ab.
- **Adapter:** das Modul baut aus seinen Daten die Nachricht, die `boerdi-result-groups` erwartet,
  und zeigt die bisherigen Boxen — gleiche Darstellung und Regeln (Gruppen-Grenzen aus
  `kontext().anzeigeRegeln`, Typ-Fokus, Such-Absprung). Web-Links zeigt die Linkbox; fehlt sie, zeigt
  die Shell die bisherige Web-Link-Box nach den Treffern.
- **Kacheln (U1-c2b):** im Kachel-Modus dieselbe Brücke zu `boerdi-card-list`. „mehr anzeigen“
  zählt das Modul selbst (+5, scrollt zur ersten neuen Kachel); „mehr laden“ bittet den Host
  (`aktion('mehrLaden', { blockId })`), die Shell lädt die nächste Seite und schreibt die neuen
  Karten in den Block — das Modul bekommt sie als neue Daten und deckt alle auf.
- **Host:** `treffer()` (Kontext der Trefferboxen, Kacheln ja/nein, Zug läuft), `aktion()` mit
  `volltext`, `sammlung`, `lernpfad` (`{ nodeId, title }`) und `mehrLaden` (`{ blockId }`).
- `cards` bleibt im Vertrag (Entscheid „Blöcke zusätzlich“); mit Block schweigen die bisherigen Boxen.
