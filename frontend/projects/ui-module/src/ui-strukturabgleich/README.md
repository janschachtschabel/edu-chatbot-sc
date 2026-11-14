# ui_strukturabgleich

Paket U4 (Plan `docs/plans/2026-11-08-pakete-m1-u4-u5-u3-5.md`). Der Strukturentwurf der Person (Teil `draft`)
gegen eine bestehende WLO-Sammlung.

- **Art:** `anzeigen`, nachgeladen (`laden: bei_bedarf`), rahmenloses Custom Element `<boerdi-ui-strukturabgleich>`.
- **Dienst:** `strukturabgleich` (`backend/src/boerdi/ui_module/dienst_strukturabgleich.py`). Er arbeitet ohne
  LLM. Führt der MCP-Server `list_collection_tree` (SW-4, Plan `2026-11-14-sammlungsstruktur-werkzeuge.md`),
  liest er den Baum als Liste, so tief wie der Entwurf reicht, und gleicht **bis Ebene 4** ab; sonst liest er mit
  `browse_collection_tree` (Tiefe 2, mit Inhaltszahlen) und gleicht Ebene 1 und 2 ab. Den Abgleich selbst
  macht `domain/strukturabgleich.py`.
- **Parameter für die KI:** `sammlung` (nodeId), `titel` (nur zur Anzeige), `abdeckung` (U5). Der Entwurf ist
  der zuletzt gezeigte, sonst der aus dem Vorgang (Teil `draft`), nie aus den Argumenten.
- **Abdeckung (U5):** Mit `abdeckung: true` zählt der Dienst je Punkt die Treffer in ganz WLO
  (`services/abdeckung.py`), nur wenn `count_wlo_content_matches` im Zug angeboten ist. Lücken haben höchstens
  2 Treffer. Gezählt wird für Ebene 1 und 2 (`abdeckung.nur_bis_ebene`); tiefere Punkte tragen keine Zahl,
  der Abschnitt „Lücken“ sagt es einmal.
- **Anzeige:**
  - je Punkt die Art (**vorhanden**, **ähnlich**, **neu**) als Wort, dazu die zugeordnete Sammlung mit der Zahl
    ihrer Inhalte; tiefere Ebenen eingerückt unter ihrem Punkt. Wurde ein Punkt ohne zugeordneten
    Elternpunkt gefunden, steht dabei, unter welcher Sammlung;
  - „Nicht gefunden“ statt „Neu“, wo die Sammlung gekürzt oder nicht vollständig gelesen ist (`ungewiss`),
    mit dem passenden Hinweis darunter;
  - aufklappbar die Sammlungen, die es nur in WLO gibt.
- **Links** laufen über `host.link` (Fähigkeit `oeffnen`). Titel stehen als `textContent`.
- **Textfassung** für Widgets ohne das Modul: die Zahlen und die neuen Punkte.
