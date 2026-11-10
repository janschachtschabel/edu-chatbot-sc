# Paket AS-7c — Beispiel „Führung“ und Handbuch (2026-11-10)

Plan: `docs/plans/2026-11-09-ablaeufe-im-studio.md` §5m (F-8, D7).

- **Beispiel-Ablauf** `backend/seeds/06-ablaeufe/fuehrung.yaml` („Kurze Führung durch WLO“):
  - im Werkszustand **aus**;
  - zeigt `wenn_seite` (schon auf der Mitmach-Seite?), drei `seite`-Schritte mit `ankunft` und den
    Auslöser `seite` auf `/home/*`;
  - Pfade wie die bestehende Tour, die unverändert bleibt;
  - drei Testfälle: der ganze Weg, schon am Ziel, wartet auf den Seitenwechsel.
- **Wächter** `test_as7c_das_beispiel_fuehrung_besteht_pruefung_und_eigene_tests`: Das Beispiel ist
  aus, besteht die Prüfung, und alle eigenen Testfälle bestehen in der Simulation.
- **Modell:** `AblaufArea.beschreibung` ist Fließtext bis 600 Zeichen und bekommt deshalb eine
  Textfläche (`Textarea()`, Wächter ST-2f). Im Studio-Formular gilt das für alle Abläufe. Schema-Abzug
  und OpenAPI sind neu erzeugt; geändert hat sich nur `x-widget: textarea`.
- **Handbuch** `docs/ablaeufe.md` (D7) ist angelegt, mit dem Kapitel „Führungen“:
  - Schritt `seite`, `wenn_seite`, Auslöser `seite`;
  - Pfadmuster, Testen, Beispiel;
  - der Hinweis zu `persist-session`.
  - Die Beispiele „Sammlung aus Ordnern“ und „Sammlung prüfen“ folgen mit AS-8.

**Deploy:** Backend neu bauen. Für das neue Beispiel `boerdi import-config --werksabgleich`, wie bei
jedem neuen Seed-Bereich. Keine Migration.
