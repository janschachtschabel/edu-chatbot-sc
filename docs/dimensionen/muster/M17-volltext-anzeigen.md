# M17 — Volltext anzeigen

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

| Feld | Wert |
|---|---|
| `id` | M17 |
| `label` | Volltext anzeigen |
| `short_purpose` | Den Inhalt EINES konkreten Materials im Chat zeigen — Arbeitsblatt & Co. als Text, nicht nur die Kachel. |
| `priority` | 488 |
| `default_tone` | kollegial |
| `default_length` | kurz |
| `response_type` | answer |

### Kernregel

> Der Volltext wird UNVERÄNDERT gezeigt — in einer Dokument-Box, nicht
> nacherzählt. Die Begleitzeile ist kurz (1 Satz) und wiederholt den Inhalt
> nicht. Ist kein Volltext verfügbar, wird der Grund benannt statt still auf die
> Metadaten zurückzufallen.

### Werkzeuge

- get_wlo_content_text
- get_node_details
- search_wlo_content

### Quellen

- mcp

### Wann anwenden

- User will den INHALT eines bestimmten, bereits bekannten Materials sehen ("zeig mir das Arbeitsblatt", "was steht da drin?")
- User steht auf einer Materialseite und fragt nach deren Inhalt
- User klickt „Inhalt anzeigen" an einer Material-Kachel
- User will mit dem Inhalt weiterarbeiten (kürzen, umschreiben, drucken) und braucht ihn dafür erst einmal vor sich

### Wann nicht

- User sucht noch Material zu einem Thema → M05 (mit Filter) / M06 (ohne)
- Inhalte einer Themenseite → M16
- Aufbau einer Sammlung → M08
- User will etwas NEU erstellen lassen → M10
- Der Text liegt schon in der Box und soll geändert werden → M11

### Auslöser-Phrasen

- Zeig mir den Inhalt
- Was steht in dem Arbeitsblatt
- Öffne das Material
- Zeig mir den Text davon
- Kann ich den vollen Inhalt sehen

### Anti-Muster

- Den Text zusammenfassen, obwohl der User ihn sehen will
- Bei fehlendem Volltext so tun, als wäre die Beschreibung der Inhalt
- Materialsuche zu einem Thema → M05/M06

### Abgrenzung gegen Nachbarmuster

- **vs**: M05
- **rule**: EIN bereits bekanntes Material aufmachen → M17. Material zu einem Thema erst suchen → M05.
- **example**: Zeig mir den Inhalt dieses Arbeitsblatts → M17. Arbeitsblätter zu Brüchen für Klasse 5 → M05.

- **vs**: M16
- **rule**: Volltext eines Einzelmaterials → M17. Schwimmlinien einer Themenseite → M16.
- **example**: Was steht in dem Arbeitsblatt? → M17. Was ist auf der Themenseite Brüche? → M16.

- **vs**: M10
- **rule**: Bestehenden Inhalt zeigen → M17. Neuen Inhalt erzeugen → M10.
- **example**: Zeig mir das Arbeitsblatt → M17. Erstell mir ein Arbeitsblatt → M10.

- **vs**: M11
- **rule**: Text erstmals holen → M17. Bereits gezeigten Text überarbeiten → M11.
- **example**: Zeig mir den Inhalt → M17. Mach den Text kürzer → M11.

## Anweisung

# M17 — Volltext anzeigen

## Wann aktiv
- „Zeig mir den Inhalt", „Was steht in dem Arbeitsblatt?", „Öffne das Material"
- Klick auf „Inhalt anzeigen" an einer Material-Kachel
- Nutzer:in steht auf einer Materialseite und fragt nach deren Inhalt

## Pipeline
1. **Ist die Node-ID bekannt** (Kachel-Klick oder Seitenkontext), holt das
   Backend den Text deterministisch über die Direkt-Aktion
   `show_content_text` → `get_wlo_content_text(nodeId)`. Der Text geht
   **unverändert** in die Dokument-Box; es läuft kein Antwort-LLM dazwischen.
2. **Ist noch unklar, welches Material gemeint ist**, zuerst
   `search_wlo_content` — dann den Treffer mit „Inhalt anzeigen" anbieten,
   statt den Text selbst abzutippen.

## Warum der Text nicht durch das Sprachmodell läuft
Zwei Gründe, beide gemessen:
- **Wortlaut.** Wer ein Arbeitsblatt einsetzen will, braucht es so, wie es ist.
  Eine Nacherzählung wäre ein anderes Dokument.
- **Länge.** Der Server liefert bis zu 50 000 Zeichen (~15 000 Token). Das passt
  in keine Antwort-Länge — ein Modell dazwischen *müsste* kürzen.

## Wenn kein Volltext da ist
Der Server nennt den Grund; er wird benannt, nicht verschluckt:

| Grund | Was der Bot sagt |
|---|---|
| `access_denied` | Material ist nicht frei zugänglich — Rechtefrage, kein zweiter Versuch hilft |
| `no_text_no_url` | Es gibt schlicht keine Textfassung |
| `extraction_failed` | Technischer Fehlschlag — ein erneuter Versuch kann klappen |
| `node_not_found` | Material ist weg (zurückgezogen/verschoben) |

In jedem dieser Fälle stehen zwei Auswege bereit: **ein eigenes Material per KI
erstellen** (→ M10) oder **frei zugängliche Alternativen suchen** (→ M05/M06).

## Verhalten
- **Begleitzeile kurz** (1 Satz): nennt Titel und ggf. Quelle. Der Inhalt steht
  in der Box, nicht zusätzlich im Fließtext.
- Ist der Text **gekürzt** (`truncated`), wird das gesagt — wer damit arbeiten
  will, muss wissen, dass das Ende fehlt.
- Weiterarbeiten am Text übernimmt **M11**. Grundlage ist nicht die Box, sondern
  die **Gesprächshistorie**: der Volltext wird mit dem Zug gespeichert, damit ein
  „mach das kürzer" etwas zum Überarbeiten hat. Es bleibt fremdes Material —
  beim Überarbeiten die Quelle nennen, nicht als eigenes ausgeben.
