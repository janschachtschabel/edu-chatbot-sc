# ui_strukturabgleich

Paket U4 (Plan `docs/plans/2026-11-08-pakete-m1-u4-u5-u3-5.md`). Der Strukturentwurf der Person (Teil `draft`)
gegen eine bestehende WLO-Sammlung.

- **Art:** `anzeigen`, nachgeladen (`laden: bei_bedarf`), rahmenloses Custom Element `<boerdi-ui-strukturabgleich>`.
- **Dienst:** `strukturabgleich` (`backend/src/boerdi/ui_module/dienst_strukturabgleich.py`). Er arbeitet ohne
  LLM und liest die Sammlung mit `browse_collection_tree` (Tiefe 2, mit Inhaltszahlen). Den Abgleich selbst
  macht `domain/strukturabgleich.py`.
- **Parameter für die KI:** `sammlung` (nodeId), `titel` (nur zur Anzeige), `abdeckung` (U5). Der Entwurf ist
  der zuletzt gezeigte, sonst der aus dem Vorgang (Teil `draft`), nie aus den Argumenten.
- **Abdeckung (U5):** Mit `abdeckung: true` zählt der Dienst je Punkt die Treffer in ganz WLO
  (`services/abdeckung.py`), nur wenn `count_wlo_content_matches` im Zug angeboten ist. Lücken haben höchstens
  2 Treffer.
- **Anzeige:**
  - je Punkt die Art (**vorhanden**, **ähnlich**, **neu**) als Wort, dazu die zugeordnete Sammlung mit der Zahl
    ihrer Inhalte;
  - aufklappbar die Sammlungen, die es nur in WLO gibt.
- **Links** laufen über `host.link` (Fähigkeit `oeffnen`). Titel stehen als `textContent`.
- **Textfassung** für Widgets ohne das Modul: die Zahlen und die neuen Punkte.
