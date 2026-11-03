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
- **Grenzen:** zeigt nur, fragt nichts ab. DOCX-Download kommt später (Entscheid U-F3).
- **Hilfen:** `inhaltsrahmen.ts` — Symbol und Bezeichnung je Art (de/en), Dateiname,
  Inhalt der Markdown-Datei.
