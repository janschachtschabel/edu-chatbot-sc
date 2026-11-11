# Plan: Themenbaum-Abläufe zuerst anbieten, Wissen aus dem Leitfaden (2026-11-11)

Folgt auf [`2026-11-10-themenbaum-aus-inhalten.md`](2026-11-10-themenbaum-aus-inhalten.md).

## Anlass (Rückmeldung des Nutzers nach dem Deploy vom 10.11.)

- „Ich würde gern einen Themenbaum zu Karate erstellen“ ruft direkt `ui_strukturentwurf` auf
  (46 Punkte). Der Ablauf „Themenbaum · aus einem Thema“ startet nicht.
- Ein Lehrplan-PDF über „Themenbaum aus dem Strukturdokument erstellen“ ergibt einen Entwurf, aber
  einen schlechten. Er nimmt beliebige Abschnitte des PDF statt Lernfelder oder Themenfelder, und
  die Hinweise aus dem Leitfaden fehlen. Auch hier startet kein Ablauf.
- „Befund senden“ im Upload-Modul klingt merkwürdig; „Senden“ ist besser.
- **Nutzer (N16):**
  - Abläufe sollen grundsätzlich zuerst angeboten werden.
  - Die erste Frage im Ablauf bietet an, ihn zu nutzen oder ohne ihn zu arbeiten.
  - Dass man in einem Ablauf ist, ist sichtbar, und man kann ihn verlassen, um direkt mit Modulen
    und Werkzeugen zu arbeiten.
- **Wissen:** Wissen soll hinterlegt werden, „am besten in den Abläufen?“. Grundlage ist das
  Dokument „Themenbäume — Gestaltungsleitfaden“ (eingefügt am 11.11.).

## Ursachen (gemessen am Code)

1. **Wendung:** Die Wendung von „aus einem Thema“ heißt „themenbaum zu einem thema“. „Themenbaum
   zu Karate“ enthält sie nicht. Bei mehreren Treffern gewinnt der erste Ablauf in der Reihenfolge
   der Kennungen, nicht der genaueste.
2. **KI-Weg:** Die KI sieht das Modul `ui_strukturentwurf` und das Ablauf-Werkzeug gleichrangig.
   Nichts sagt ihr, dass ein passender Ablauf vorgeht. Der Auslöser `agent` von „aus einem Thema“
   steht auf `vorschlagen`.
3. **Dokument-Weg:** Ein Ablauf mit Modul-Auslöser auf die Upload-Antwort fehlt. `aktion:
   dokument` heißt laut Manifest immer `ziel: themenbaum`.
4. **Generator:** Die Aufforderung von `strukturentwurf_prompt` kennt keine Formregeln des
   Leitfadens (Ebenen, Breite, Einzelkinder, Benennung, Facetten statt Knoten). Beim Dokument heißt
   es nur „folge der Ordnung des Dokuments, lass Verwaltendes weg“. Lernfelder und Themenfelder
   bevorzugt sie nicht, und Kompetenzlisten, Basiskonzepte und Leistungsbewertung schließt sie
   nicht aus.
5. **Klick nach dem letzten Wahlschritt:** Ein KI-Schritt antwortet erst auf eine getippte
   Nachricht (A2b). Nach dem letzten Wahlschritt fehlt deshalb ein Knopf, der die KI anstößt.

## Entscheide (selbst getroffen, nach Nutzer-Vorgaben N16)

- **E1 Wissen an zwei Orten:**
  - **Feste Form- und Benennungsregeln** stehen in der Aufforderung des Generators (Code). Sie gelten
    für jeden Entwurf, auch für den direkten Modulaufruf. Der Generator ist ein eigener LLM-Aufruf
    und sieht den Master-Skill nicht.
  - **Vorgaben der Redaktion** je Ablauf sind im Studio pflegbar: Feld `vorgaben` am KI-Schritt
    (nur Text der Redaktion). Sie gehen in den Systemteil des Generators, etwa „Zweck → Baumart“
    oder „bei Lehrplänen: Lernfelder oder Themenfelder als Ebene 1“. Das ist der Weg „Wissen in
    den Abläufen“.
  - Was die Person tippt (Thema, Wünsche), bleibt Daten im Nutzerteil.
- **E2 Abläufe zuerst:**
  - Die Beschreibung jedes Ablauf-Werkzeugs sagt: „Passt er, nimm ihn statt eines einzelnen
    Moduls oder Werkzeugs; ohne ihn nur, wenn die Person das will.“
  - „Aus einem Thema“ startet über die KI direkt (`modus: direkt`), denn er schreibt nichts.
  - Ablauf-Werkzeuge kommen im Angebot vor den Modulen.
- **E3 Ausstieg als erste Frage:** Jeder Themenbaum-Ablauf fragt zuerst „mit ein paar Fragen
  (empfohlen) oder gleich ohne“. „Ohne“ beendet den Lauf mit dem Satz, dass es direkt weitergeht.
  Danach arbeitet die KI frei mit `ui_strukturentwurf`. Die Ablauf-Leiste (AS-Ub) zeigt den
  laufenden Ablauf und bietet „Abbrechen“; sie bleibt, wie sie ist.
- **E4 Wendungen:** Der längste passende Treffer gewinnt, nicht die Reihenfolge der Kennungen.
  „Aus einem Thema“ bekommt breitere Wendungen, etwa „themenbaum zu“ und „themenbaum erstellen“.
  Die genaueren Wendungen der anderen Themenbaum-Abläufe gewinnen dann von selbst.
- **E5 Startknopf am KI-Schritt:** Ein optionales Feld `startknopf` (Label je Sprache) erscheint als
  Schnellantwort, solange die KI am Schritt noch nichts getan hat. Das Label geht als Nachricht der
  Person an die KI, also ohne neue Mechanik. Die Seeds nutzen es, etwa mit „Entwurf erstellen“.
- **E6 Neuer Ablauf** „Themenbaum · aus einem Dokument“ (`themenbaum_aus_dokument`):
  - Auslöser: Modul `ui_upload` mit `wenn_teil: document`, Knopf, KI und Wendungen.
  - Fragen: Einstieg, wofür, Ordnungsprinzip (Lernfelder, Themenfelder oder Kapitel des Dokuments).
  - Danach der KI-Schritt mit `aus_dokument` und Vorgaben für Lehrpläne.
- **E7 Beschriftung:** „Befund senden“ wird „Senden“.

## Pakete (je Review mit Behebung, danach ein Querschnitts-Review)

| Paket | Inhalt |
|---|---|
| TW-1 Generator-Wissen | Leitfaden-Regeln in `_SYSTEM`; Dokument-Aufforderung mit Strukturelementen und Ausschlussliste; Tests der Aufforderungen. |
| TW-2 Vorgaben je Ablauf | Feld `agent.vorgaben` (Textarea, ≤ 2000 Zeichen je Sprache); Weitergabe an die Umgebung der Module (Agent- und Muster-Weg); Strukturentwurf hängt sie an den Systemteil; Studio-Texte; Tests. |
| TW-3 Abläufe zuerst | Werkzeugtext mit Vorrang, Ablauf-Werkzeuge vor Modulen; längste Wendung gewinnt; Feld `agent.startknopf`; Tests. |
| TW-4 Seeds | Erste Frage mit Ausstieg und `startknopf` in beiden Themenbaum-Abläufen, „aus einem Thema“ mit `modus: direkt` und breiteren Wendungen; neuer Seed `themenbaum_aus_dokument`; Vorgaben aus dem Leitfaden; Testfälle. |
| TW-5 Beschriftung | „Befund senden“ → „Senden“ (de/en). |

## Stand 11.11.

TW-1 bis TW-5 sind umgesetzt, jedes Paket mit Review und Behebung. Zusätzlich aus den Reviews:

- **Ausstieg** (`ausstieg` am `ende` oder „Abbrechen“, `zug.abgelehnt`): Nach „Ohne Ablauf“
  startet derselbe Ablauf drei KI-Züge lang nicht wieder von selbst. „Doch mit Ablauf“ startet ihn.
- **Querschnitts-Review** (5 MAJOR) und **zweites, unabhängiges Review** (2 MAJOR) sind behoben,
  siehe `aenderungen/2026-11-11-querschnitt-gruppe-tw.md`.
- **Wendungen:** „Aus einem Thema“ kennt nur „themenbaum aus einem thema“. Freie Bitten wie
  „Erstelle einen Themenbaum zu Karate“ entscheidet die KI, die den Ablauf direkt startet.
- **Master-Skill-Regel:** Ein Ablauf geht `ui_strukturentwurf` vor. Die Regel steht in
  `docs/skills/vorgehen-knapp.md`, **den WLO-Knoten zieht der Nutzer nach**.
- **Entscheid:** Beim Dokument-Ablauf kommt die Wahl erst nach dem Lesen, weil der
  Modul-Auslöser dort beginnt.

## Nicht im Umfang

- Strukturprüfungen im Code (TB-4: Tiefe, Breite, Einzelkinder als Warnung) — eigener Schritt.
- Sammlungsart als Pflichtmerkmal, Facetten-Vokabulare, SKOS — Leitfaden-Empfehlungen für später.
