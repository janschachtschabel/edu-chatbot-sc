# Paket U4 — Abgleich eines Entwurfs mit einer WLO-Sammlung (2026-11-08)

Plan: [`plans/2026-11-08-pakete-m1-u4-u5-u3-5.md`](../plans/2026-11-08-pakete-m1-u4-u5-u3-5.md), E-3…E-8.

## Was sich ändert

Neues UI-Modul **`ui_strukturabgleich`**. Es zeigt, was vom Strukturentwurf der Person in einer bestehenden
WLO-Sammlung schon da ist. Es kommt ohne KI aus und ändert nichts.

- **Je Punkt** des Entwurfs (Ebene 1 und 2) zeigt es die Art als Wort (**Vorhanden**, **Ähnlich**, **Neu**) und
  die zugeordnete Sammlung mit der Zahl ihrer Inhalte.
- **Nur in WLO:** aufklappbar die Sammlungen, denen kein Punkt entspricht.
- **Abgleich** (`domain/strukturabgleich.py`, rein):
  - Titel werden normalisiert: ohne Akzente, klein, ohne Satzzeichen und Füllwörter.
  - Gleicher Titel: vorhanden. Token-Jaccard ≥ 0,5: ähnlich, die beste Zuordnung zuerst. Sonst: neu.
  - Jede Sammlung wird höchstens einem Punkt zugeordnet.
  - Ebene 2 wird unter der zugeordneten Sammlung gesucht; hat der Elternpunkt keine, unter allen Sammlungen der
    Ebene 2.
- **Dienst `strukturabgleich`:**
  - Der Entwurf ist der in diesem Gespräch zuletzt gezeigte, sonst der übernommene aus dem Vorgang (Teil
    `draft`). Aus den Argumenten kommt er nie.
  - Die Sammlung liest er über `browse_collection_tree` (Tiefe 2, mit Inhaltszahlen, ohne Cache).
  - Die KI bekommt nur die Zahlen. Titel stehen im Modul, denn sie sind Fremdtext (aus einem Dokument oder
    einer fremden Sammlung).
  - Ohne Entwurf oder ohne lesbare Sammlung gibt es einen Fehlertext an die KI und keinen Block.
- **Werkzeug der KI:** Parameter `sammlung` (nodeId, UUID) und, nur zur Anzeige, `titel`.
  - Angeboten nur, wenn `browse_collection_tree` im Lauf verfügbar ist (neu im Manifest: `dienst.braucht`).
  - Ohne Entwurf antwortet es mit dem Fehlertext. Das weicht von E-8 („nur angeboten mit Entwurf“) ab, weil das
    Angebot den Vorgang nicht kennt.
- **Element:**
  - nachgeladen, ein rahmenloses Custom Element mit 2,5 kB gzip;
  - Texte de/en, Zahlen über `Intl`;
  - Links nur über `host.link`, Titel als `textContent`;
  - die Art steht als Wort, nicht nur als Farbe.
- **Textfassung** für Widgets ohne das Modul: die Zahlen und die neuen Punkte.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 4 hoch, 7 klein, 4 Kleinigkeiten. Behoben:

| Befund | Behebung |
|---|---|
| `parent` ist beim MCP die Kennung (ein Text), kein Objekt; der Titel der Sammlung fehlte immer, der Link auch. | Titel aus dem Argument `titel` (nur Anzeige), Link aus der Kennung wie beim Themenbaum. Hat der Client die Kennung geändert (Selbstheilung über das Fach), gilt die gelesene. |
| Ein Dienst-Modul umging die Sperre auf `browse_collection_tree` (Sicherheit, Studio, Einbettung). | `dienst.braucht` im Manifest-Schema; `_anbietbar` prüft es. Doku §4.2. |
| Ebene 2 ohne zugeordneten Elternpunkt schnappte die Kinder einer zugeordneten Sammlung weg. | Erst die gebundenen Punkte, dann die übrigen gegen freie Sammlungen. |
| Der Server liefert bei Tiefe 2 nur einige Kinder je Sammlung; „Neu“ war dort eine Falschaussage. | „Nicht gefunden“ (`ungewiss`) unter gekürzten Sammlungen. Die Quittung sagt es der KI, das Modul erklärt es. |
| Umlaute (Anfänger/Anfaenger), „für“ und „ø“ wurden verschieden normalisiert. | Umlaute vor dem Zerlegen gefaltet, „fuer“ als Füllwort. |
| „Nur in WLO“ verlor die Hierarchie; das Etikett zeigte nur „1“/„2“. | „Ebene 1/2“ als Wort, „unter …“ mit der Elternsammlung. |
| Ebene 2 war nur optisch eingerückt. | Verschachtelte Liste. |
| Zwei verschiedene Zahlen für „nur in WLO“. | „Nur in WLO (100 von 120)“. |
| Der Entwurf aus dem Vorgang ging vor dem eben gezeigten. | Wie beim Strukturentwurf: erst der gemerkte, dann der aus dem Vorgang. |
| Eine Zeitüberschreitung hieß „Sammlung nicht lesbar“, ohne Latenz. | Status `timeout`, Latenz gemessen. |
| Titel gingen als Markdown in die Textfassung. | Markdown-Zeichen entschärft. |
| Kein Deckel für über 250 Punkte; „Inhalte“ zählt nur Direktes. | Gedeckelt mit `gekuerzt`; der Hinweis sagt „direkt in einer Sammlung“. |
| Testlücken | Tests für alle Punkte oben, im Backend und im Element. |

Offen: `includeContentCounts` kostet einen Aufruf je Sammlung (bis etwa 155). Ob `contentsCount` allein genügt,
klärt eine Messung.

## Geändert

- Manifest-Schema `_vertrag/manifest.schema.json` und `manifest.ts`: `dienst.braucht`;
  `ui_module/werkzeuge._anbietbar` prüft es.
- neu:
  - `backend/src/boerdi/domain/strukturabgleich.py`;
  - `backend/src/boerdi/ui_module/dienst_strukturabgleich.py` (eingetragen in `dienst._DIENSTE`);
  - `frontend/projects/ui-module/src/ui-strukturabgleich/` (Manifest, Element, Texte, Stil, README, Spec).
- erzeugt: `register.generated.ts`, `nachlade-quellen.generated.ts`, `backend/src/boerdi/ui_module/manifeste.json`.
- Studio-Spec `ui-modul-vorschau.component.spec.ts` (Manifest aufgenommen).
- Doku: `docs/ui-module.md` (Tabelle).
- Tests, die die Modul-Menge festschreiben: `test_config_choices.py`, `test_agent_prompt_preview.py`,
  `test_ui_entscheidung*.py`, `test_ui_modul_schalter.py`.

## Tests

- neu `backend/tests/test_strukturabgleich_u4.py`: Normalisieren, Abgleich, Ebene 2 unter der Zuordnung, jede
  Sammlung einmal, kaputte Eingaben, Katalog, Dienst (Aufruf ohne Cache, nur Zahlen an die KI, Textfassung),
  ohne Entwurf, gemerkter Entwurf, Sammlung nicht lesbar, Argumente, Text statt Struktur, gekürzt.
- neu `ui-strukturabgleich.element.spec.ts`: Arten als Wort, Zahlen, Links über den Host, Fremdtext, nur in
  WLO, gekürzt, leer, Englisch, zweimal definieren.
- grün:
  - Frontend: ui-module 317, studio 2043, ui 1215, widget 76;
  - `module:register --pruefen`; Budget 24,4 kB von 60 kB;
  - eslint, `check:tokens`, `check:radii`.

## Betrieb

- Widget, Backend und Studio neu bauen. Das Bündel `ui-strukturabgleich.<hash>.js` kommt mit dem Widget-Build.
- Keine Migration.
