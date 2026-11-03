# ui_linkbox

Zeigt die Webseiten, auf die sich eine Antwort stützt, als Linkliste — Nachfolger der Box
`boerdi-web-links` (Paket U1-c1), gleiches DOM, gleiches Stil-Partial
(`ui/src/grouping/_result-group.scss`).

- **Entsteht automatisch:** das Backend leitet den Block an der API-Grenze aus `web_links` ab
  (`backend/src/boerdi/ui_module/abgeleitet.py`), live und im Verlauf mit derselben Kennung; kein
  Werkzeug der KI (`agent: false`). Höchstens `display_rules.groups.webseiten_max` Links, nur
  http/https, keine Führungs-Nachrichten. Ein Muster schaltet ihn mit `ui_module: []` ab.
- **Links:** Adresse und Warnhinweis liefert der Host (`link(url)`: Sitzungs-Kennung bei
  vertrauten Seiten, Hinweis bei fremden); geöffnet wird in neuem Fenster (`noopener noreferrer`).
- **Platz:** `unten` — nach den Trefferboxen, wie die bisherige Box.
- `web_links` bleibt im Vertrag (Entscheid „Blöcke zusätzlich“); mit Block schweigt die alte Box.
