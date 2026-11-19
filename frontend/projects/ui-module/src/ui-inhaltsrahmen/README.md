# ui_inhaltsrahmen

Zeigt ein fertiges Arbeitsergebnis als gerahmte Box: Verlaufsplan, Unterrichtsreihe,
Arbeitsblatt, Lernpfad, Zeugnis, Brief, Fachtext, Volltext eines Materials oder eine
vorgeschlagene Änderung an WLO. Nachfolger der Dokument-Box (bis U1-b3 `ui/src/inline-doc/`, Paket U1-b),
gleiches Aussehen, gleiche Klassen (`.inline-document*`).

- **Eingabe:** `titel`, `art`, `markdown` (`manifest.json`). `volltext` und `schreib_vorschau`
  setzt nur das System, nie die KI.
- **Kann:** Drucken (Druckansicht, daraus auch PDF) und Herunterladen als Markdown
  (`<titel>.md`, Titel als Überschrift). Beides über den Modul-Host.
- **Schriftgröße:** `kontext().schriftSkala` aus den Anzeige-Regeln
  (`inline_documents.font_size_percent`, 70–100 %).
- **Freigabe-Box (Paket N4):** Mit dem Feld `freigabe` (nur System, `x-nur-system`) zeigt die Box
  die Vorschau eines Kestra-Flows über den MCP: Zahl, überschriebene Felder (beim Metadaten-Flow;
  sonst „Dieser Auftrag schreibt in WLO: {Flow}“), Probleme getrennt, Liste eingeklappt (nach Ordner
  gruppiert, bei mehr als 20 Einträgen Filter und „Weitere zeigen“, je 20) und die
  Knöpfe „Freigeben“/„Abbrechen“ (Fähigkeit `auftrag`). Nach der Entscheidung eine Zeile
  „Entscheidung gesendet: …“ (`role="status"`), nach dem nächsten Zug „nicht mehr offen“.
  Hilfen: `freigabe.ts`, `freigabe-liste.component.*`.
- **Grenzen:** fragt sonst nichts ab. DOCX-Download kommt später (Entscheid U-F3).
- **Hilfen:** `inhaltsrahmen.ts` — Symbol und Bezeichnung je Art (de/en), Dateiname,
  Inhalt der Markdown-Datei.
