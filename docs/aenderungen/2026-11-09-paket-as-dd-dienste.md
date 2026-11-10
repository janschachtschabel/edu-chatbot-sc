# Paket AS-Dd: Dienste `baum_aus_entwurf` und `struktur_mit_nodeids` (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), §5e.

## Was sich ändert

Zwei reine Dienste für `werkzeug`-Schritte (ohne Netz, ohne LLM) bilden die Brücke zwischen einem
Strukturentwurf und dem Anlegen der Sammlungen:

```yaml
- {id: baum, typ: werkzeug, werkzeug: baum_aus_entwurf,
   argumente: {entwurf: {$teil: draft}}, schreibt: baum, bei_fehler: fehler}
- {id: anlegen, typ: werkzeug, werkzeug: wlo_create_collection_tree,
   argumente: {parentCollectionId: …, tree: {$teil: baum}},
   freigabe: {de: "Sammlungen anlegen?"}, schreibt: angelegt, bei_fehler: fehler}
- {id: verbinden, typ: werkzeug, werkzeug: struktur_mit_nodeids,
   argumente: {entwurf: {$teil: draft}, angelegt: {$teil: angelegt}},
   schreibt: draft_mit_ids, bei_fehler: fehler}
```

- **`baum_aus_entwurf`:**
  - Argument `entwurf` (`wlo.sammlungsstruktur@1`).
  - Liefert den Baum für `wlo_create_collection_tree` (`[{title, description?, children?}]`), mit
    genau den Titeln des Entwurfs und höchstens so tief wie ein Entwurf.
  - Ohne Punkte kein Wert.
  - Eine Auswahl reicht hier nicht, denn sie kann `titel` nicht in `title` umbenennen.
- **`struktur_mit_nodeids`:**
  - Argumente: `entwurf` und `angelegt`, das Ergebnis von `wlo_create_collection_tree`
    (`{nodes: [{path, nodeId?, status, code?}]}`) oder dessen Liste `nodes`.
  - Liefert eine Kopie des Entwurfs, in der jeder angelegte Punkt die Kennung seiner Sammlung in
    `wlo_id` trägt. Folgeschritte (Einsortieren, Metadaten) treffen so die richtigen Knoten.
- **Zuordnung:**
  - Über den Titelpfad, wie der MCP-Server ihn bildet (`collection-tree.ts`: getrimmte Titel mit
    „/“ verbunden, unter der Elternsammlung). Je Glied zählen Groß- und Kleinschreibung und
    Leerraum nicht (`normTitle`).
  - Nur Kennungen in UUID-Form. Eine Kennung gilt unabhängig vom Status: `existing` und `failed`
    mit `code: exists` tragen die vorhandene Sammlung.
  - Mehrdeutige Pfade bekommen keine Kennung, lieber keine als eine falsche. Beispiel: „a/B“ als
    ein Titel und „A“ mit dem Kind „B“, die der Server getrennt hält.
  - Alte Kennungen (`wlo_id`, `wurzel_wlo_id`, etwa aus einem Entwurf aus dem Bestand) fallen weg,
    denn sie zeigten auf die Quellsammlung.
- **Kein Wert, also `bei_fehler`:**
  - Entwurf oder Ergebnis fehlen.
  - Kein Punkt bekam eine Kennung, etwa beim Ergebnis eines anderen Baums oder bei geänderten
    Titeln.
- **Schon vorhandene Sammlungen:** Sie kommen nach dem Ja als `existing` mit Kennung. `unveraendert`
  liefert dieses Werkzeug nie, weil der Server immer einen Plan vorlegt.
- **Ergebnis eines Kestra-Flows:** Ein Auftrag hinterlässt `wlo.auftrag@1`. Die Knoten übergibt man
  mit `pfad` (`angelegt: {$teil: x, pfad: "outputs.…"}`); dann vergleicht die Prüfung keinen Typ.
- **Typen (AS-Db):**
  - `baum_aus_entwurf` liefert `baum_aus_entwurf@1`, `struktur_mit_nodeids` liefert
    `wlo.sammlungsstruktur@1`.
  - Erwartet werden `entwurf` als Strukturentwurf und `angelegt` als
    `wlo_create_collection_tree@1`. Das ist der Typ, unter dem der Treiber das Ergebnis nach der
    Freigabe speichert; beide nehmen ihn jetzt aus `typen.dienst_typ`.
- **Studio:** Der Hinweis am Feld „Werkzeug“ nennt alle vier Dienste und dass ein schreibendes
  Werkzeug eine Freigabe braucht.
- **Abweichung vom Plan:** Der Plan nennt das Feld `node_id`. Genommen ist das vorhandene Feld
  `wlo_id` aus dem Vertrag von `ui_strukturentwurf`, das auch ein Entwurf aus dem Bestand trägt. Ein
  zweites Feld läse das Modul nicht.
- **Offen: `ablage_zuordnen`.** Zwei Lücken:
  - Der Teil `ablage` trägt je Eintrag nur den Dateinamen (`name`, beim MCP aus Titel und Endung
    gebildet), keinen Ordnerpfad. Der MCP legt flach in einen Ordner ab.
  - Der Ordnerbaum (`wlo.ordnerbaum@1`) trägt je Ordner nur Zahlen, keine Dateien.

  Selbst eindeutige Namen ließen sich so keinem Ordner zuordnen. Nötig wäre ein Ordnerpfad oder
  Index je Datei im Upload (Modul) und in `ablage`. Der Dienst wartet auf die Teamfrage T1
  (Upload-Weg); siehe offene Befunde §4.

## Wo

- `backend/src/boerdi/ui_module/strukturentwurf_bestand.py`: `baum_aus_entwurf`, `mit_kennungen`
  (neben `aus_bestand`, dieselbe Prüfung der Kennung, jetzt `fullmatch`).
- `backend/src/boerdi/services/ablauf/werkzeuge.py`: zwei Einträge in `DIENSTE`.
- `backend/src/boerdi/services/ablauf/typen.py`: `DIENST_AUSGABE`, `DIENST_EINGABE`, `ANGELEGT`;
  `treiber.py` nimmt den Typ nach der Freigabe aus `dienst_typ`.
- Studio: `i18n/catalogue/fields-ablaeufe.ts` (Feldhinweis, DE und EN).

## Tests

- `backend/tests/test_ablauf_struktur_mit_nodeids.py` (vor der Umsetzung geschrieben, rot → grün),
  13 Tests:
  - Kennung je Punkt; reine Liste;
  - fehlender Entwurf oder fehlendes Ergebnis; Kennung ohne UUID-Form, auch mit Zeilenende;
  - kein Rückgriff auf eine Wurzel; alte Kennungen fallen weg; ohne Treffer kein Wert;
  - mehrdeutige Pfade, auch auf Seiten des Entwurfs; Titel mit „/“; kaputte Punkte;
  - Typ nach der Freigabe gleich dem erwarteten, mit einem echten Ablauf aus Baum, Anlegen und
    Verbinden, sowie ein falscher Typ;
  - `baum_aus_entwurf`.
- Ergebnis: alle Ablauf-, Strukturentwurf-, Freigabe- und Teil-Tests grün (673), ruff sauber.

## Review (Befundhebung)

Unabhängiges Review mit dem MCP-Vertrag (nur gelesen) und dem Schema des Moduls. Ergebnis: 0 kritisch,
2 schwer, 6 kleiner, 2 Kleinigkeiten. Alle behoben.

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Der Rückgriff auf eine „neue Wurzel“ wurde je Punkt entschieden. Trug ein oberer Punkt den Titel des Entwurfs, bekamen die Wurzel und ein gescheiterter Punkt fremde Kennungen. | schwer | Rückgriff gestrichen: Kein Weg erzeugt einen solchen Baum. |
| 2 | Gescheiterte Punkte behielten alte Kennungen (etwa aus dem Bestand), Folgeschritte hätten in die Quellsammlung geschrieben. | schwer | Alte `wlo_id` und `wurzel_wlo_id` fallen weg; nur `angelegt` zählt. |
| 3 | Ohne einen einzigen Treffer kam trotzdem ein Wert. | kleiner | Dann `None`, also `bei_fehler`. |
| 4 | Normalisierte Pfade konnten zusammenfallen, die der Server getrennt hält. | kleiner | Mehrdeutige Pfade, auf beiden Seiten, bekommen keine Kennung. |
| 5 | Kein Weg vom Entwurf zum Argument `tree`; der Weg für ein Kestra-Ergebnis war nicht beschrieben. | kleiner | Dienst `baum_aus_entwurf`; der Weg über `pfad` steht oben. |
| 6 | Die Notiz beschrieb `unveraendert` als Fall dieses Werkzeugs. | kleiner | Richtiggestellt: Vorhandenes kommt als `existing` mit Kennung. |
| 7 | Die Begründung für das offene `ablage_zuordnen` war unvollständig. | kleiner | Beide Lücken genannt (kein Ordnerpfad, keine Dateien im Ordnerbaum). |
| 8 | Tests fehlten für 1, 2, 4, „/“, die Typklammer und `unveraendert`/`complete`. | kleiner | Ergänzt. |
| 9 | Zwei Quellen für den Typ nach der Freigabe (Text und `f"{werkzeug}@1"`). | Kleinigkeit | `typen.dienst_typ` an beiden Stellen. |
| 10 | „gescheitert = keine Kennung“ stimmte nicht immer (`failed` mit `code: exists`). | Kleinigkeit | Doku: Eine Kennung gilt unabhängig vom Status. |

Vorher vorhanden, mit behoben: `_wlo_id` prüfte mit `match` gegen ein Muster mit `$` und ließ ein
Zeilenende durch; jetzt `fullmatch`. Ebenfalls vorhanden und nur verbessert: Dienste sind im Studio
nicht auswählbar (freies Feld). Der Feldhinweis nennt sie jetzt. Eine Auswahlliste und die
Prüfung der Argumentnamen je Dienst stehen in den offenen Befunden.

## Querschnitts-Review AS-D (Da…Dd)

Zusätzliche Review-Schleife über die vier Teilpakete: das Szenario aus §5e (Upload → Entwurf → Baum →
Anlegen mit Freigabe → Kennungen → Folgeschritt mit Auswahl) durch Prüfung, Sicht „Daten“,
Simulation und Treiber. Ergebnis: 0 kritisch, 2 schwer, 6 kleiner, 2 Kleinigkeiten. Logs und
Sicherheit ohne Befund (Dienste schreiben nie, Schreiben nur über die Freigabe).

| # | Befund | Schwere | Behebung |
|---|---|---|---|
| 1 | Die Simulation ersetzte jeden Dienst durch einen Wert des Testfalls, auch die reinen. Die Kette ließ sich nicht abbilden, ein von Hand geschriebenes Ergebnis sagte einen Weg voraus, den es nicht gibt. | schwer | `werkzeuge.REINE_DIENSTE` (alles ohne `DIENST_MCP`) rechnet die Simulation selbst; ein Eintrag in `werkzeuge` des Testfalls, auch `null`, überschreibt. |
| 2 | Pfad oder Auswahl, die in jedem Lauf scheitern, blieben ohne Befund: in einem Text-Teil, als Auswahl an einem Objekt-Argument eines Dienstes, als Auswahl auf eine Liste, die der Typ nicht trägt. | schwer | Befunde `verweis_text` und `dienst_auswahl`; Warnung `auswahl_liste` (Tabelle `typen.LISTEN`). `angelegt` nimmt auch die Liste `nodes` (`typen.LISTE_ERLAUBT`). |
| 3 | Die Simulation reichte das Ergebnis einer Freigabe roh weiter; im Betrieb ohne Schlüssel, und „alle gescheitert“ geht zu `bei_fehler`. | kleiner | Neues Modul `services/ablauf/freigabe_ergebnis.py`, eine Quelle für Zug und Simulation. |
| 4 | Eine Auswahl an einem Argument, das einen einzelnen Wert nimmt (etwa `collectionId`), ergibt eine Liste, die der Server ablehnt; die Simulation zeigte die eingesetzten Argumente nicht. | kleiner | Befund `auswahl_einzeln` nach der lokalen Werkzeugdefinition; die Schein-Vorschau der Simulation nennt die eingesetzten Argumente. |
| 5 | Typen als Text im Treiber; `typen.MODUL_TEILE` ohne Klammer an `arbeitsstand_teile` und `vorgang_teil`. | kleiner | Treiber nimmt `typen.TEXT`/`typen.AUFTRAG`; Wächtertest gegen beide. |
| 6 | Zwei gleichnamige Verweissuchen mit verschiedener Tiefe; ein zu tiefer Verweis schaltete die Vertragsprüfung der Moduldaten ab. | kleiner | `typen.verweise` (bis `TIEFE`, wie der Treiber) entscheidet die Vertragsprüfung; die Suche der Formprüfungen heißt `_alle_verweis_namen`. |
| 7 | Das Studio schlug Freitext-Teile nicht vor. | kleiner | `vorigeTeile` liest auch `freitext.schreibt`. |
| 8 | Das Leitbeispiel im Plan nannte `liste: eintraege`, `feld: nodeId`. | kleiner | `liste: inhalte`, `feld: node_id`. |
| 9 | Doku-Reste (entfernte Funktion in der Notiz Db, Kommentare zu Auswahl und `…`, Warnungen im Vertragsdokument). | Kleinigkeit | Nachgezogen. |
| 10 | Typen in der Sicht „Daten“ roh (`wlo.sammlungsstruktur@1`). | Kleinigkeit | Offen, offene Befunde §4. |

Dazu angepasst: zwei ältere Tests, die das jetzt Gemeldete als Vehikel nutzten
(`test_paket_s`: ein zu breiter Filter auf „schreib“; `test_ablauf_datenfluss`: eine Auswahl am
Objekt-Argument `entwurf` — jetzt an einem Flow-Argument, das eine Liste nimmt). Neue Tests:
`backend/tests/test_ablauf_querschnitt_asd.py` (12).

Volle Backend-Suite danach: 9357 bestanden, 5 übersprungen, 0 Fehlschläge. Studio 171 Dateien / 2113 Tests grün.

## Betrieb

Keine Migration, keine neue Variable. Das Image neu bauen (Studio, Backend).
