# Paket AS-Db: Prüfung je Weg und Typen der Teile (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), D8 und §5e.

## Was sich ändert

- **`$teil`-Verweise je Weg** (in `daten` und `argumente`):
  - **Befund:** Ein Verweis zeigt auf einen Teil, den weder ein Schritt des Ablaufs noch irgendein Modul
    schreibt. Er fehlt im Lauf dann immer.
  - **Warnung, kein Befund:**
    - Der Teil entsteht im Ablauf erst nach dem Schritt.
    - Der Ablauf schreibt ihn gar nicht, aber ein Modul kann ihn im Gespräch hinterlassen, etwa
      `document` aus `ui_upload`.

    In beiden Fällen muss der Teil schon im Vorgang liegen, sonst gilt „Bei Fehler“. Das sperrt
    nicht, damit bestehende Abläufe, die auf einen vorher im Gespräch hochgeladenen Ordner bauen,
    gültig bleiben.
  - „Prüfen“ im Studio zeigt die Warnungen als Hinweis. Die Liste der Warnungen von
    `POST /api/config/ablauf-pruefen` hatte schon das Format für sie.
- **Typen** (neu `services/ablauf/typen.py`):
  - **Ausgaben:** Jeder schreibende Schritt hat einen bekannten Ausgabetyp:
    - Dienst nach Tabelle;
    - lesendes WLO-Werkzeug `text`;
    - schreibendes Werkzeug `<werkzeug>@1`;
    - Auftrag `wlo.auftrag@1`;
    - Modul nach seinen Teilen (`structure` = `wlo.ordnerbaum@1`, `document` =
      `wlo.dokument-verweis@1`, `draft` = `wlo.sammlungsstruktur@1`), auch beim Modul-Auslöser;
    - Freitext `text`.

    Die Ausgabe eines KI-Schritts hat keinen festen Typ.
  - **Eingaben:** Dienste und Module nennen, was sie als ganzen Teil erwarten:
    - `strukturentwurf_aus_ordnern.struktur` einen Ordnerbaum;
    - `abdeckung_zaehlen.entwurf` eine Sammlungsstruktur;
    - `ui_strukturentwurf` und `ui_strukturabgleich` als ganze `daten` eine Sammlungsstruktur.
  - **Prüfung:** Ein ganzer Teil ohne Pfad und ohne Auswahl, dessen bekannte Typen den erwarteten
    nicht enthalten, ist ein Befund. Ein Beispiel ist der Ordnerbaum statt eines Entwurfs bei
    `abdeckung_zaehlen`. Mit Pfad, Auswahl oder unbekanntem Schreiber gibt es keinen Vergleich.
- **Der mitgelieferte Ablauf** bleibt ohne Befund und ohne Warnung (Test).

## Wo

- `backend/src/boerdi/services/ablauf/typen.py` (neu):
  - Typtabellen;
  - `schritt_ausgaben`, `ausgaben`;
  - `erwartete_eingaben`.
- `services/ablauf/pruefung.py`:
  - `_datenfluss`;
  - `warnungen`.

  Die Teile aus dem Gespräch liefert inzwischen `typen.teile_aus_dem_gespraech` (Review AS-Db).
- `services/ablauf/pruefung_texte.py`.
- `api/config_ablauf.py`: Warnungen zum Datenfluss in „Prüfen“.

## Tests

- `backend/tests/test_ablauf_datenfluss.py` deckt ab:
  - stimmiger Fluss;
  - Teil ohne Schreiber;
  - Teil aus einem Modul im Gespräch;
  - späterer Teil;
  - falscher Typ;
  - kein Vergleich mit Pfad;
  - unbekannter Schreiber;
  - Typtabelle;
  - mitgelieferter Ablauf.
- `test_ablauf_studio_k2c1.py`: erwartet jetzt den Hinweis zu `document` aus dem Gespräch.
- 950 gezielte Backend-Tests grün.

## Betrieb

Keine Migration, keine neue Variable, kein Vertrag geändert. Ein bestehender Ablauf mit `$teil` auf
einen Teil, den nichts schreibt, lässt sich nicht mehr speichern, bis der Verweis stimmt. Laufen
würde er ohnehin nur in `bei_fehler`.

## Review (2026-11-09)

Ein frischer Reviewer fand 2 hoch, 5 klein und 3 Kleinigkeiten. Jeder Befund wurde am Quelltext nachgeprüft und behoben:

| Befund | Behebung |
|---|---|
| Hoch: Der Teil `ablage` stand in keinem Manifest; ihn hinterlässt die Übertragung von `ui_upload`. Genau der Leitfall aus D8 (`$teil: ablage` mit Auswahl für `structure_node_ids`) ließ sich dadurch nicht speichern, obwohl das Studio `ablage` selbst anbot. | `typen.py` ist jetzt die eine Quelle: `MODUL_TEILE` mit `ablage` und `ZUSATZ_TEILE` (`ui_upload` → `ablage`). Prüfung, Warnungen, Typvergleich und die Teil-Auswahl im Studio (`config_choices`) nutzen sie (Tests). |
| Hoch: `ui_strukturabgleich` sollte laut Tabelle einen Entwurf nehmen, bekommt aber ein fertiges Abgleich-Ergebnis. Die Tabelle bestätigte so eine Konfiguration, die nie läuft. | Eigener Typ `wlo.strukturabgleich@1`, den kein Schritt liefert. Ein Entwurf dort ist ein Befund (Test). |
| Der Treiber speicherte für Dienste `<dienst>@1`, die Tabelle nannte andere Typen. | Der Treiber nimmt den Typ aus `typen.dienst_typ`, Speicherung und Prüfung haben also eine Quelle (Test). Niemand las den alten Namen. |
| Ein Teil, den nichts schreibt, bekam zum Befund noch den widersprüchlichen Hinweis „aus dem Gespräch“. | Die Warnungen betrachten nur Teile, die der Ablauf oder ein Modul schreibt (Test). |
| Teile nur aus dem Gespräch wurden nicht auf den Typ geprüft. Ein Schreiber mit unbekanntem Typ neben einem bekannten löste trotzdem einen Vergleich aus. | Der Typ kommt sonst aus dem Gespräch. `None` in der Menge (KI-Ausgabe) hebt den Vergleich auf (Tests). |
| Die Schreiber standen doppelt (`pruefung._schreibt_je_schritt` und `typen.schritt_ausgaben`) und Manifeste wurden an fünf Stellen gelesen. | `_schreibt_je_schritt` nutzt `typen`, die alte Hilfe ist entfernt, `config_choices` nutzt `typen.modul_teile`. |
| Testlücken | Neu getestet: `ablage` nach dem Upload, Strukturabgleich, gespeicherter Typ, keine Doppelmeldung, Gesprächstypen, gemischte Schreiber, Modul-Auslöser, Teil-Auswahl im Studio. Der Später-Test nutzt einen sonst befundfreien Ablauf. |
| Kleinigkeiten | Der Hinweistext sagt „sonst scheitert der Schritt (Bei Fehler, falls gesetzt)“. Docstring und Studio-Kommentar sind nachgezogen, im Plan steht der Auftragstyp `wlo.auftrag@1`. Die gegliederte Ausgabe der Warnungen (Schritt, Nummer) bleibt offen; heute stehen sie als Liste unter „Prüfen“. |

Bekannte Grenze (aus AS-3b, offen): „Davor“ heißt „auf irgendeinem Weg“. Was ein Schritt schreibt, gilt auch für seine `bei_fehler`-Nachfolger, und Teile eines Modul-Auslösers gelten auch bei einem Start per Knopf. Beides kann Hinweise verschlucken, sperrt aber nichts Gültiges.

Prüfung: 1006 gezielte Backend-Tests grün; Studio 170/170 grün.
