# W4-Anbindung — Rolle im Stapel: Strukturdokument oder Inhalt (2026-11-08)

Grundlage: der MCP-Stand vom 2026-11-08 (Auftrag W1–W4, Entwicklerbericht des MCP-Teams; live erst nach dessen
Deploy). Nutzer-Entscheid 2026-11-08: **W4 jetzt**, W1–W3 zusammen mit K2d.

## Was sich ändert

- Das Modul `ui_upload` kannte schon je Datei die Rolle „Inhalt“ oder „Strukturdokument“. Beim Übertragen in den
  persönlichen Bereich geht sie jetzt mit: `wlo_prepare_file_batch` bekommt je Eintrag `role`
  (`content` | `structure`). Die Rolle ist beim MCP Teil der Freigabe und steht im Manifest
  (`wlo.ablage-vorgang@2`).
- Die Vorschau im Modul nennt das Strukturdokument („Strukturdokument“ hinter dem Namen).
- Der Vorgang merkt die Rolle im Teil `ablage` je Eintrag (`rolle`, dazu `rolle_bestaetigt`: stand sie in der
  Vorschau des Servers). So weiß ein späterer Schritt (K2d: Volltext, Metadaten, Struktur), welcher Knoten das
  Strukturdokument ist — auch nach einem ersetzten Stapel (`frueher` trägt die Rolle mit).
- Das Backend prüft die Regel des Moduls selbst: höchstens ein Strukturdokument, und nur PDF, DOCX, TXT oder MD
  (sonst 422 vor jedem MCP-Aufruf).

## Geändert

- **Backend**
  - `api/ui_ablage.py`: `Eintrag.rolle` (`inhalt` | `struktur`, Vorgabe `inhalt`; anderes → 422 vor jedem
    MCP-Aufruf); die Antwort trägt `rolle` je Eintrag.
  - `services/ablage/mcp_ablage.py`: `vorbereiten` schickt `role`. Ein Server vor W4 verwirft das unbekannte Feld
    still (zod ohne `strict`, im MCP-Quelltext nachgesehen) — vor dem MCP-Deploy bricht also nichts.
  - `services/ablage/vorgang_teil.py`: `aus_plan(…, rollen=…)` — die Rolle aus der Vorschau des Servers (sie ist
    die Freigabe); gibt ein Server vor W4 keine zurück, die erbetene, sonst `inhalt`.
  - Vertrag neu erzeugt (ein neues Feld); Eintrag in `api/bewusste-vertragszusaetze.md`.
- **Modul** (`ui-module`)
  - `_vertrag/modul-host.ts`: `AblageEintrag.rolle?`, Typ `AblageRolle` (auch in `public-api.ts`).
  - `ui-upload/upload-uebertragen.ts`: `Kandidat.rolle`, `Plan.eintraege[].rolle`; `upload-uebertragen-ablauf.ts`
    schickt sie; `upload-uebertragen-ansicht.ts`, `-texte.ts`, `upload-stil.ts`: der Hinweis in der Vorschau.
  - README des Moduls.

## Bewusst so

- `wlo_list_my_batches` gibt die Rolle je Eintrag nur mit `nodeId` zurück. Die Liste der letzten Ablagen (M6)
  braucht sie nicht; der Chatbot liest die Rolle aus seinem Vorgang. Den Knoten eines fremden oder alten Stapels
  nach seiner Rolle zu fragen, ist erst in K2d nötig.
- Ein Teil `ablage`, der vor diesem Paket entstand, hat kein `rolle`; niemand liest es dort bisher.

## Review (2026-11-08)

Ein frischer Reviewer: 0 kritisch, 1 hoch, 4 mittel, 3 Kleinigkeiten — alles behoben.

| Befund | Behebung |
|---|---|
| **Hoch:** Vor dem MCP-Deploy (Vorschau ohne `role`) kam die erbetene Rolle nur in die HTTP-Antwort; gespeichert wurde `inhalt`, denn `arbeitsstand.teile_speichern` speichert das Ergebnis von `neu()`. | `neu()` bekommt die Rollen auch; der Endpunkt-Test läuft für beide Server-Stände und prüft den gespeicherten Teil. |
| Ein ersetzter Stapel verlor die Rolle seiner abgelegten Einträge (`frueher`). | `frueher` trägt `rolle` (beide Wege: `_frueher`, `mit_frueher`). |
| Die Regel „höchstens ein Strukturdokument, lesbare Art“ galt nur im Modul. | Modell-Prüfung am Endpunkt (422 vor dem MCP). |
| Vor W4 war die erbetene Rolle weder im Fingerabdruck noch im Manifest, galt aber als „Teil der Freigabe“. | `rolle_bestaetigt` je Eintrag; ein späterer Schritt prüft das Manifest. |
| Kleinigkeiten | Beschreibungen, was die Freigabe trägt (`upload-uebertragen.ts`, `ablage-transport.ts`, `vorgang_teil.py`); Trenner „ – “ vor „Strukturdokument“ für Screenreader; Element-Test mit in der Oberfläche gesetzter Rolle. |

Älter als W4 und notiert: die Antwort von `vorbereiten` ist im Vertrag nicht getippt; ein Strukturdokument über
`max_mb_ablage` zählt still als „zu groß“. Gemeinsame Dateien mit K2a/K2b (`modul-host.ts`, `openapi-*.json`)
gehen mit diesen Paketen zusammen hinaus.

## Tests

- Backend: neu `tests/test_ablage_rolle_w4.py` (an den Server, aus der Vorschau, ohne Rolle vom Server, durch den
  Endpunkt bis in den gespeicherten Teil — vor und seit W4, fremde Rolle und zwei bzw. ein Bild als
  Strukturdokument → 422 ohne MCP-Aufruf, `frueher` behält die Rolle); `tests/test_ablage_mcp.py` (Argumente mit
  `role`); `test_ui_ablage_api.py`, `test_vorgang_teil.py` (`frueher` mit `rolle`).
- Modul: `upload-uebertragen.spec.ts` (Rolle in der Auswahl und im Plan), `ui-upload-uebertragen.element.spec.ts`
  (Freigabe trägt `rolle`, auch eine in der Oberfläche gewählte; Vorschau nennt das Strukturdokument).
- Budget der nachgeladenen Module: `ui-upload` 17,98 kB gzip (Grenze 20 kB).

## Betrieb

Keine Migration und keine neue Variable. Das Widget-Bündel muss neu gebaut werden. Wirksam wird die Rolle erst mit
dem MCP-Deploy; vorher schadet sie nicht.
