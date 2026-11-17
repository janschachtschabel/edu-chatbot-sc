# Themenbaum erstellen: erst bereitstellen, dann entscheiden (2026-11-16)

## Anlass

Rückmeldung des Nutzers vom 16.11.:

- **Sackgasse:** „Themenbaum · aus Ordnern“ mit drei losen Dateien endet mit „Ohne Unterordner
  gibt es noch keinen Themenbaum.“ Frage: Braucht es einen eigenen Ablauf, oder ist er falsch
  verdrahtet?
- **Generisch:** Das Upload-Feld (und andere UI-Module) soll Daten nur bereitstellen. Was damit
  geschieht, entscheiden die nachfolgenden Schritte. Feste Knöpfe wie „Themenbaum aus dem
  Strukturdokument erstellen“ gehören nicht ins Upload-Feld.
- **Leitfragen:** Den Abläufen fehlen viele der vorgesehenen Fragen. Zur Orientierung dienen:
  - die beigelegten Use-Case-Abläufe (Ordner und Dateien, Thema, Website);
  - das Bild „Leitfragen für die Themenbaum-Erstellung“: Wofür? Für wen? Welches Gerüst? Soll
    oder Ist?
  - das Prozessbild in Phasen: Einstieg, Inhalte erschließen, Struktur bilden, Prüfen und
    anlegen, Befüllen, Erschließen;
  - die Wissenssammlung zu Themenbäumen: 3–4 Ebenen, 5–15 oben, 3–20 Kinder, keine
    Einzelkinder, Eingangsstruktur ist nicht Zielstruktur, Soll/Ist, Facetten statt Ebenen.

**Antwort auf die Frage:** falsch verdrahtet, kein eigener Ablauf nötig.
`strukturentwurf_aus_ordnern` liefert ohne Unterordner nichts, und der Fehlerzweig endet. Den Weg
für lose Dateien gibt es als „aus eigenen Inhalten“, aber nur über die Ablage in WLO mit
Anmeldung. Ab Werk ist er aus, und die Dateien gehen nicht mit.

## Ist-Stand (Bestandsaufnahme 16.11.)

### Wo die Kopplung an den Themenbaum sitzt (nicht im Speichern der Teile)

- **Frontend `ui_upload`:**
  - `DokumentZiel = 'themenbaum'` und `DOKUMENT_ZIELE` (`upload-dokument.ts:16-17`) mit dem
    Knopf „Themenbaum aus dem Strukturdokument erstellen“;
  - der Knopf „Als Themenbaum-Entwurf übernehmen“ (`ordner_als_entwurf`);
  - die Lehrplan-Automatik (`upload-rollen.ts:302,323-335`).
- **Manifest:** Enums `zweck: [sammlungsstruktur]` und `dokument.ziel: [themenbaum]`, die Aktion
  `ordner_als_entwurf`, `einzeldatei_als_struktur`.
- **Backend:**
  - `upload_antwort._ZIEL` weist die KI an, `ui_strukturentwurf` mit `aus_dokument` zu rufen;
  - `nicht_gelesen_satz`, `services/ordner_aktion.py`;
  - der neue Vorgang trägt fest `zweck="sammlungsstruktur"`.
- **Abläufe:** Der Modul-Auslöser `wenn_teil: document` von „aus einem Dokument“, Texte, die den
  Knopf nennen, und die Umlenkung von `ui_upload` (`vorschlag.py`).

### Sackgassen

- „aus Ordnern“ und „Sammlung prüfen“ mit nur Dateien enden bei `ohne_ordner`.
- „aus Ordnern“ mit gelesenem Dokument endet ebenfalls bei `ohne_ordner`: Der Modul-Auslöser
  greift nicht, solange ein Lauf wartet.
- „aus eigenen Inhalten“ endet bei `ohne_ablage`, wenn nichts nach WLO übertragen wurde. Die
  Ablage ist ab Werk aus. Mit gelesenem Dokument endet er bei `nach_dokument`.
- Jeder Ablauf mit Upload beginnt immer mit dem Upload, auch wenn die Daten schon im Vorgang
  liegen.

### Leitfragen heute

| Frage | Ablauf |
|---|---|
| Wofür (`zweck`) | Dokument, Inhalte, Thema |
| Stufe (`stufe`) | Inhalte, Thema |
| Thema | Inhalte, Thema |
| Gerüst/Ordnung (`ordnung`) | nur Dokument |
| Tiefe (`tiefe`) | nur Thema |
| Für wen, Soll/Ist, Umfang oben, Schwerpunkte | nirgends (nur Freitext an die KI) |

„aus Ordnern“ fragt gar nichts. Die Antworten erreichen den Generator nur über die KI
(`[ABLAUFDATEN]`). Der Code ordnet keinen Teil einem Feld des Auftrags zu, `tiefe` wird nicht in
eine Zahl umgerechnet.

### Wiederverwendbar

- Die Teile `structure`, `document` und `ablage` werden ohne Ziel gespeichert.
- Die Aktion `erfasst` ist zielneutral.
- Das Dokument hängt an der Sitzung, nicht am Vorgang.
- `wenn_teil`, `wenn_wert` (`gleich`, `enthaelt` …) und `$teil` stehen zur Verfügung.
- Ein Ablauf übernimmt freie Arbeit samt Teilen.
- `metadaten.als_dokument` nimmt jeden Teil im Format `wlo.metadaten@1`. „aus Inhalten“ braucht
  also nicht zwingend WLO, nur Titel und Beschreibung je Inhalt.
- `ui_entscheidung` kann Mehrfachwahl, schreibt aber keinen Teil. Das wird hier nicht gebraucht.

## Datenmodell (Nutzer 16.11., Grafik „Übergabe an den Chatbot“, mit Optimierung)

Grundsätze des Nutzers:
- Binärdaten gehören nie in den Datenstrom. Nach dem Hochladen zählen nur die node_ids.
- Nach dem Kestra-Flow braucht der Chatbot die beschreibenden Metadaten: Titel,
  Beschreibungstext, Schlagworte, Fach, Bildungsstufen, Lizenz.
- Volltexte bleiben am Knoten und werden bei Bedarf gezogen.
- Ordnerstrukturen bleiben erhalten, mit den Dateinamen bzw. node_ids je Ordner, damit sich beides
  verknüpfen lässt.
- Strukturdokumente sind von Inhalten getrennt, weil man von ihnen später den Volltext
  verarbeitet, von Inhalten meist nur die Metadaten.
- Anonym, ohne WLO-Anmeldung, wandelt der Chatbot einzelne Dokumente selbst um.

**Teile im Vorgang.** Kein Teil trägt Binärdaten. Große Texte werden über Verweise geholt.

| Teil | Wann | Inhalt | Ist-Stand → Änderung |
|---|---|---|---|
| `struktur` (`wlo.auswahl@1`) | sofort beim „Senden“, auch anonym | Ordnerbaum; je Ordner seine Dateien mit `i` (feste Nummer in der Auswahl), Name, Endung, Größe, Rolle (`inhalt`/`struktur`/`ignorieren`); dazu `zahlen` und `warnungen` (das ist der „Befund“, kein eigener Teil) | heute `structure` nur mit Ordnern und Zahlen → voller Baum mit Dateien. `structure` bleibt eine Zeit lang als abgeleitete Sicht für laufende Abläufe. |
| `ablage` (`wlo.ablage@1`) = **Zuordnung** | nach dem Übertragen nach WLO (MCP) | je Datei `index` → `node_id`, Rolle, Stand | gibt es → `index` muss gleich `i` aus `struktur` sein, damit Ordner und Knoten verknüpfbar sind (heute zählt der Index die gefilterte Übertragungsliste; offener Punkt T1/`ablage_zuordnen`). Kein eigener Teil `zuordnung`. |
| `inhalte` (heute `metadaten`, `wlo.metadaten@1`) | nach Kestra-Flow und `metadaten_lesen` | je Knoten `node_id`, `i`, Titel, Beschreibung, Schlagworte, Fächer, Stufen, Arten, **Lizenz** | gibt es, aber höchstens **50** Knoten und ohne Lizenz und `i` → in Blöcken zu 50 lesen bis 500; Lizenz und `i` ergänzen. Den Namen `metadaten` behalten, um keinen Bruch zu riskieren. |
| `strukturdokument` | anonym: nach „Lesen lassen“ (Umwandlung im Chatbot); mit WLO: Knoten mit Rolle `struktur` aus `ablage` | Name, Quelle (`chatbot` \| `wlo`), Verweis: `dokument:<id>` (Text an der Sitzung, 24 h) oder `node_id` (Volltext des Repositoriums) | heute `document` nur für den Chatbot-Weg → ein Teil mit zwei Quellen. Ein Leser (`strukturdokument.text()`) liefert den Markdown-Text je nach Quelle, bei Bedarf. |
| Volltext eines Inhalts | nur auf Anforderung | GET über die node_id (das Repositorium wandelt um, nie selbst schreiben) | kein eigenes Feld: die node_id ist der Verweis. |

**Optimierungen gegenüber der Grafik:**

1. **`zuordnung` und `befund` sind keine eigenen Teile.** Die Zuordnung ist `ablage` (gibt es
   schon, braucht nur den gemeinsamen Index `i`), der Befund steht in `struktur`. Zwei Teile
   weniger, die auseinanderlaufen könnten.
2. **Das Strukturdokument wird nicht dauerhaft als Markdown mitgeführt, sondern als Verweis** mit
   einem Leser für beide Quellen.
   - Anonym ist der umgewandelte Text ohnehin 24 Stunden an der Sitzung; mit WLO zieht der
     Leser den Volltext über die node_id.
   - Der Generator ruft `text()` und muss die Quelle nicht kennen.
   - Größere Texte bleiben so aus dem Vorgang (Grenze 64 KB je Teil).
3. **Der Markdown-Text bekommt eine einzige Stelle der Umwandlung je Quelle.** Im Chatbot ist das
   die vorhandene Umwandlung, in WLO macht es das Repositorium bzw. Kestra. Ein dritter Weg
   entsteht nicht.
4. **Der Generator bleibt vorerst im Chatbot**, mit der Schnittstelle „Teile rein, Entwurf raus“.
   So kann er später als Kestra-Flow laufen („Themenbaum-Generator über Kestra“ in der Grafik),
   ohne dass sich die Abläufe ändern.
5. **Die KI bekommt Zusammenfassungen und Verweise**, nie ganze Listen oder Texte im Prompt.
   Werkzeuge lesen die Teile.

**Wer liest was** (die Abnehmer greifen heraus, was sie brauchen):

| Abnehmer | liest |
|---|---|
| Entwurf aus Ordnern | `struktur` (Ordner) |
| Entwurf aus losen Dateien (anonym) | `struktur` (Dateinamen der Rolle `inhalt`) |
| Entwurf aus Inhalten (WLO) | `inhalte`, optional `struktur` (Ordner als Herkunft) |
| Entwurf aus Strukturdokument | `strukturdokument.text()` |
| Kestra-Metadaten-Flow | `ablage` (node_ids der Rolle `inhalt`) |
| Später: Sammlungen 1:1 befüllen | `struktur` + `ablage` (Ordner ↔ node_id) |

## Ziel

**Ein geführter Ablauf „Themenbaum erstellen“:**
1. erst die Leitfragen;
2. dann, je nach Grundlage, die Daten bereitstellen (Upload-Feld, zielneutral);
3. dann der passende Generator;
4. dann der Prüfpunkt (Entwurf bearbeiten).

Keine Sackgasse: Jede Datenlage hat einen Weg weiter. Das Upload-Feld kennt kein Ziel mehr.

## Ansätze

- **A: Mehrere Abläufe behalten, dazu eine Schrittart `ablauf`** (Wechsel mit Übergabe der
  Teile). Jeder Ablauf bekommt die Leitfragen.
  - Vorteil: Die Abläufe bleiben einzeln startbar.
  - Nachteil: Die Leitfragen stehen viermal. Die Schrittart ist neu in Engine, Prüfung, Leiste,
    Simulation und Studio. Das ist groß.
- **B: Ein Ablauf „Themenbaum erstellen“ mit Verzweigung nach der Grundlage**, gebaut mit den
  vorhandenen Schrittarten (geschätzt rund 30 von 40 Schritten).
  - Die vier alten Abläufe bleiben als Werksfassung, ab Werk aus. Sie werden nicht gelöscht.
  - Vorteil: Die Fragen stehen einmal, und keine neue Schrittart ist nötig. Das entspricht dem
    Prozessbild des Nutzers (eine Einstiegsfrage, dann die Grundlage).
  - Nachteil: Ein großer Ablauf. Das Studio zeigt ihn als ein Dokument.
- **C: wie B, dazu die Schrittart `ablauf`** für spätere Phasen (Anlegen, Befüllen).
  - Nachteil: Dafür gibt es heute keinen Bedarf (YAGNI).

**Empfehlung: B.** Die Phasen Befüllen und Erschließen kommen später als eigene Abläufe. Die
Teile im Vorgang tragen dorthin. Fragt jemand konkret nach einem Unterablauf, wird er später
nachgezogen.

## Entscheide

G-E1 bis G-E3 hat der Nutzer am 16.11. beantwortet. Die übrigen sind selbst getroffen, mit
Begründung.

- **G-E1 (Nutzer): Dateinamen fließen immer mit, getrennt nach Rolle.** Präzisiert durch das
  Datenmodell oben (Nutzer, 16.11. später): ein voller Teil `struktur` mit Rollen statt drei
  Teilen; Binärdaten nie; Inhalte nach der Ablage nur als node_id und Metadaten. Die
  Unterpunkte hier gelten nur noch für Hinweistext und Log.
  - Wortlaut: „die sollten immer mitfließen — wenn man sie getrennt verfügbar macht, also
    Strukturdokumente von Inhaltsdokumenten und Struktur getrennt betrachtet“.
  - Bei „Senden“ (`erfasst`) schreibt das Upload-Feld drei getrennte Teile:
    - `structure`: nur die Ordner, wie heute;
    - `dateien` (neu, `wlo.dateiliste@1`): die Inhaltsdateien mit Name, Endung, Größe und
      Ordnerpfad; höchstens 500, Namen auf 120 Zeichen gekürzt;
    - `strukturdokument` (neu): Name und Endung der als Struktur markierten Datei. Ihr gelesener
      Text bleibt der Teil `document`.
  - Ignorierte Dateien gehen nicht mit. Es gibt keinen eigenen Knopf.
  - Der Hinweis im Feld lautet neu: „Ordner- und Dateinamen gehen an den Chat. Inhalte erst, wenn
    du ein Dokument lesen oder Dateien nach WLO übertragen lässt.“
  - Dateinamen kommen nicht ins Log.
- **G-E2 (Nutzer): ein Ablauf**, „wenn es sinnvoll möglich ist“, damit Verzweigungen und Optionen
  nah beieinander stehen. Also Ansatz B: „Themenbaum erstellen“. Die vier bisherigen
  Themenbaum-Abläufe bleiben als Werksfassung erhalten, ab Werk aus. „Sammlung prüfen“ (aus)
  bleibt unverändert.
- **G-E3 (Nutzer): Wo verarbeitet wird.**
  - **Größere Dateimengen** gehen über WLO: Upload, Knoten anlegen, Volltexte und Metadaten
    entstehen dort, und die Daten kommen für den Themenbaum zurück.
    - Das ist gebaut (U3-3, K1/R1): Die Ablage läuft über die Stapel-Werkzeuge des MCP
      (`wlo_prepare_file_batch`, `wlo_store_batch_file`, `wlo_store_batch_manifest`), den
      Volltext erzeugt das Repository selbst.
    - Die Metadaten erzeugt der Kestra-Flow `edusharing.chatbot/node-metadata-write` als Auftrag,
      in Blöcken zu 50. `metadaten_lesen` holt sie zurück, `aus_inhalten` baut daraus den
      Entwurf.
    - Ab Werk ist das aber dreifach aus: der Schalter `ablage_in_wlo` (Studio), die Freigabe des
      Flows (Studio, „Abläufe“) und der Ablauf „aus eigenen Inhalten“. Er braucht die Anmeldung.
    - **Abweichung zur Vorstellung des Nutzers:** Hochladen und Anlegen macht heute das MCP, nicht
      der Kestra-Flow. Kestra erzeugt nur die Metadaten. Das ist so dokumentiert.
  - **Im Chatbot selbst, ohne Anmeldung und ohne Kestra:**
    - **Das Strukturdokument:** wie bisher eine Datei mit der Rolle „Struktur“, je Sitzung ein
      Dokument, lokal gelesen. Der Knopf heißt neutral „Lesen lassen“.
    - **Lose Inhaltsdateien:** nur über ihre Namen (G-E1, G-E9), schnell, ohne Lesen der Inhalte.
  - Der allgemeine Fall „Dokument hochladen und zu einem neuen Inhalt verarbeiten“ ist ein eigener
    Ablauf, später. Das Bereitstellen hier ist so gebaut, dass er dieselben Teile nutzen kann.
- **G-E4: Das Upload-Feld verliert die Zielknöpfe.**
  - Es entfallen „Als Themenbaum-Entwurf übernehmen“ (`ordner_als_entwurf`, samt
    `ordner_aktion` im freien Chat) und „Themenbaum aus dem Strukturdokument erstellen“
    (`ziel`).
  - Es bleiben „Senden“ (`erfasst`), „Lesen lassen“ (`dokument`, ohne `ziel`), die Ablage nach
    WLO (wenn eingeschaltet) und, nach G-E1, „Dateinamen mitgeben“.
  - Die Lehrplan-Automatik markiert weiter vor, liest aber nicht von selbst.
  - **Alte Antworten:** Antworten mit `ziel` oder `ordner_als_entwurf` aus einem offenen Verlauf
    nimmt das Backend noch einen Release lang an und behandelt sie wie `dokument` bzw. `erfasst`.
- **G-E5: Die KI bekommt einen neutralen Rahmen.**
  - `[DOKUMENT …]` und `[ORDNER …]` sagen nur, was bereitliegt, und ersetzen die Anweisung „rufe
    ui_strukturentwurf“.
  - Im freien Chat fragt die KI, was die Person damit machen will, und schlägt den Ablauf
    „Themenbaum erstellen“ vor, wenn das passt.
  - Der Master-Skill bekommt einen Absatz dazu.
- **G-E6: Bereitgestellte Daten werden übernommen.**
  - Liegen beim Start schon `structure`, `document` oder `dateien` im übernommenen Vorgang,
    fragt der Ablauf: „Deine Auswahl ‚…‘ verwenden?“ (Ja / Andere wählen). Er lädt nicht neu
    hoch.
  - Der Modul-Auslöser `wenn_teil: document` entfällt. Ein gelesenes Dokument startet nichts von
    selbst. Die KI schlägt vor (G-E5).
- **G-E7: Leitfragen** nach Leitbild, Use Cases und Wissenssammlung. Ein Teil je Frage, immer
  mit Freitext, Pflicht nur, wo der Generator es braucht:

  | Frage | Teil | Optionen | Pflicht |
  |---|---|---|---|
  | Was möchtest du tun? | `vorhaben` | neue Struktur mit Unterstützung · ohne Führung | ja |
  | Worauf baut die Struktur auf? (Gerüst) | `grundlage` | ein Thema · ein strukturgebendes Dokument (Lehrplan, Systematik) · meine Ordner · meine Dateien oder Inhalte | ja |
  | Wofür ist der Baum? | `zweck` | Unterricht planen · Material finden (Pool) · Teilen oder Redaktion · Überblick für eine Webseite | ja |
  | Für wen? | `publikum` | nur ich · Team oder Organisation · öffentlich | nein |
  | Stufe/Fach | `stufe` | Grundschule · Sek I · Sek II · Beruf · Hochschule · allgemein | nein |
  | Thema (nur bei Grundlage Thema, sonst vorbelegt aus Ordner- oder Dokumentname) | `thema` | Freitext | bei Thema |
  | Soll oder Ist? | `soll_ist` | vollständig nach Stoff (Soll) · nur was meine Inhalte tragen (Ist) | nein; nur bei Dateien/Ordnern gefragt, sonst Soll |
  | Wie fein? | `umfang` | kompakt (1 Ebene, etwa 6) · mittel (2 Ebenen) · ausführlich (3 Ebenen) | nein, Vorgabe mittel |
  | Muss etwas vorkommen oder wegfallen? | `hinweise` | nur Freitext, überspringbar | nein |

  - Facetten (Stufe, Format, Zielgruppe) werden nie Knoten. Die `vorgaben` am KI-Schritt sagen
    das (Wissenssammlung: „keine Facettenwerte als Knoten“).
- **G-E8: Feste Zuordnung der Teile zum Auftrag** in `ki_schritt`/`dienst`, nicht über die KI:
  - `umfang` → `tiefe` (1/2/3) und `anzahl_oben` (6/10/12);
  - `stufe` → `bildungsstufe`;
  - `thema` → `thema`;
  - `zweck`, `publikum`, `soll_ist` und `hinweise` gehen als Zeilen in `hinweise`.

  Die KI kann einen Wert überschreiben, wenn die Person ihn im Gespräch ändert.
- **G-E9: Lose Dateien ohne WLO.**
  - Das neue Werkzeug `inhalte_aus_dateien` macht aus dem Teil `dateien` einen Teil `metadaten`
    (`wlo.metadaten@1`): Titel aus dem Dateinamen, Ordnerpfad als Beschreibung.
  - Danach `aus_inhalten` wie heute.
  - Mit Ablage in WLO und Anmeldung bleibt der bessere Weg über `metadaten_lesen` (G-E3). Ist die
    Ablage eingeschaltet und die Person angemeldet, fragt der Ablauf: „Gründlich über WLO
    (ablegen, Volltexte und Metadaten erzeugen; dauert einige Minuten)“ oder „Schnell aus den
    Dateinamen“. Sonst nimmt er ohne Frage den schnellen Weg und sagt das in einem Satz.
- **G-E10: Ordner sind Herkunft, nicht Ziel** (Wissenssammlung).
  - Der Weg „meine Ordner“ übernimmt die Ordner als Vorschlag. Der Prüfpunkt sagt das ausdrücklich
    („Ordner sind dein Ausgangspunkt — benenne und ordne um, was nicht fachlich ist“).
  - Ordner ohne Unterordner wechseln auf den Weg „Dateien“.
- **Später, nicht in diesem Plan:** Sammlungen anlegen, befüllen (WLO-Filter Fach/Stufe/Qualität,
  Inhalte aus WLO), Rechte, kompendiale Texte, Websites und Crawler, mehrere Dokumente je Sitzung,
  Mehrfachwahl der Grundlage.

## Ablauf „Themenbaum erstellen“ (`06-ablaeufe/themenbaum.yaml`)

```
einstieg (vorhaben) ── ohne ──► frei (ausstieg)
   │ neu
vorhanden? (verzweigung: wenn_teil structure|document|dateien) ── ja ──► uebernehmen (Ja/Andere)
   │
grundlage ─┬─ thema ──────► thema ─┐
           ├─ dokument ───────────┤
           ├─ ordner ─────────────┤
           └─ dateien ────────────┤
wofuer → publikum → stufe → [soll_ist nur bei ordner/dateien] → umfang → hinweise
   │
daten? (verzweigung nach grundlage + vorhandenen Teilen)
   ├─ thema ───────────────────────────────► entwurf_thema (agent)
   ├─ dokument: document da? ─ nein ─► hochladen (ui_upload) ─► wieder daten?
   │                          └ ja ──► entwurf_dokument (agent, aus_dokument)
   ├─ ordner: structure mit Unterordnern? ─► aus_ordnern (werkzeug) ─► pruefen (ui_strukturentwurf)
   │          └ sonst ─► wie dateien
   └─ dateien: dateien da? ─ nein ─► hochladen ─► wieder daten?
              └ ja ─► [angemeldet + Ablage an: gründlich über WLO? ─ ja ─► Ablage im Upload-Feld
                       ─► metadaten (Kestra-Auftrag) ─► metadaten_lesen ─┐]
                      inhalte_aus_dateien (werkzeug) ─────────────────────┴► entwurf_inhalte
                       (agent, aus_inhalten)
entwurf_* ─► ende (Entwurf gespeichert; nächste Schritte als Text)
Fehlerzweige: ohne_entwurf (Nochmal / Frei weiter), nie ein stummes Ende
```

- Etwa 30 Schritte, darin Tests für jeden Zweig.
- Ab Werk an.
- Auslöser: Knopf, KI direkt, Wendungen der vier alten Abläufe zusammengefasst.

## Pakete

Jedes Paket beginnt mit Schritt 0: `/better-coding-workflow` aufrufen (bei UI zusätzlich
`/better-coding-frontend`). Danach ein unabhängiges Review mit Behebung.

- **TG-0 WLO-Weg ab Werk an** (Nutzer 16.11.: „aktivieren und die Voraussetzungen
  kommunizieren“), fertig:
  - ab Werk an: Ablage, Freigabe des Metadaten-Flows, Ablauf „aus eigenen Inhalten“;
  - Schalter `ablage_nach_anmeldung` mit Hinweis im Feld;
  - Texte zu den Voraussetzungen.
  - Notiz: `docs/aenderungen/2026-11-16-wlo-weg-ab-werk.md`.
- **TG-1 Upload zielneutral (Frontend und Manifest)** — G-E3, G-E4:
  - `DOKUMENT_ZIELE` und `alsEntwurf` entfernen;
  - „Lesen lassen“ für jede lesbare Datei;
  - Texte de/en neu;
  - Manifest: `ziel` und `ordner_als_entwurf` aus dem Schema, `zweck` neutral `bereitstellen`
    (alt `sammlungsstruktur` bleibt gültig);
  - Specs in `ui-module`.
  - **Gebaut (16.11.), noch ohne unabhängiges Review:** Notiz
    `docs/aenderungen/2026-11-16-upload-zielneutral.md`.
    - `DokumentZiel`, `DOKUMENT_ZIELE`, `alsEntwurf`, `blaseEntwurf` und die Aktion
      `ordner_als_entwurf` sind weg; ein Knopf „Lesen lassen“ (`data-dokument="lesen"`), nach dem
      Lesen „Weiter“, wenn gerade ein Zug läuft; „Senden“ ist immer der Hauptknopf.
    - Datenschutzsatz in vier Fassungen je nach Angebot, alle beginnend mit „Ordner- und
      Dateinamen gehen an den Chat“.
    - Manifest: `zweck` `[bereitstellen, sammlungsstruktur]` in Dienst und Eingabe, Beispiele mit
      `bereitstellen`, Beschreibung und `wann` ohne Themenbaum.
    - Neue Specs: Textkatalog de/en ohne „Themenbaum“/„topic tree“ (auch die Übertragen-Texte),
      Element in allen Zuständen ohne „Themenbaum“, Manifest ohne Ziel, Lehrplan-Automatik liest
      nicht von selbst.
  - **Feinentscheide TG-1:**
    - „Lesen lassen“ gilt nur für das als Struktur markierte Dokument (Auftrag 16.11.), nicht für
      jede lesbare Datei wie oben geplant — mehrere Dokumente kommen mit TG-3e.
    - Nach dem Lesen „Weiter“ statt „Senden“: daneben steht schon der Knopf „Senden“ der Auswahl,
      zwei gleich beschriftete Knöpfe wären nicht unterscheidbar.
    - Die Blase heißt „Dokument „…“ lesen lassen“.
- **TG-2 Upload zielneutral (Backend)** — G-E4, G-E5:
  - `upload_antwort` mit neutralen Rahmen;
  - `nicht_gelesen_satz` neutral;
  - `ordner_aktion` nimmt alte Antworten wie `erfasst`;
  - der Vorgang trägt den Zweck `bereitstellen`;
  - der Modul-Auslöser in `themenbaum_aus_dokument` entfällt;
  - Master-Skill-Absatz;
  - Tests.
  - **Gebaut (16.11.), noch ohne unabhängiges Review:**
    - Rahmen `[ORDNER …]`/`[DOKUMENT …]`: „Bereit: …“ und die Bitte, zu fragen und Abläufe
      vorzuschlagen, „ruf kein Werkzeug von selbst“ (`upload_antwort._FRAGEN`); `_ZIEL` ist weg.
    - Alte Antworten: neues Feld `Form.rueckwaerts` (`antwort_formen`), angewandt in
      `antwort.antwort_pruefen` **vor** der Schema-Prüfung (`upload_antwort.rueckwaerts`).
    - `services/ordner_aktion.py` samt Test, `Ausloeser.ordner`, `ist_ordner_als_entwurf`, der
      Zweig im Preflight und die Texte `action.folderDraft.*` sind gelöscht.
    - `arbeitsstand`: neuer Vorgang mit `ZWECK_BEREITSTELLEN`.
    - Seed „aus einem Dokument“: Modul-Auslöser weg, Texte nennen „Lesen lassen“, Tests ohne
      `ziel`.
    - Master-Skill (`docs/skills/vorgehen-knapp.md`): `zweck: bereitstellen`, neuer Punkt
      „Nach dem Hochladen“.
    - Studio-Hinweise zum Lesen neutral (`fields-upload.ts`).
  - **Feinentscheide TG-2:**
    - Die alte Form wird **angehoben**, nicht neben der neuen behandelt: Danach gibt es nur noch
      die neue Form, und das Schema bleibt streng. Angehoben wird nur genau `ziel: themenbaum`;
      ein unbekanntes Ziel verwirft das Schema weiter.
    - `ordner_aktion.py` ist ganz entfallen statt umgebaut: Nach dem Anheben erreicht sie keine
      Antwort mehr, und eine `erfasst`-Antwort geht den gewöhnlichen Weg (`persist` übernimmt die
      Teile).
    - **Umlenkung (`vorschlag.umlenkung`):** `ui_upload` mit `zweck: bereitstellen` lenkt nicht
      mehr auf einen Ablauf um — das Feld dient ebenso dem Dokument oder dem Übertragen nach WLO,
      und nach dem Hochladen schlägt die KI vor (G-E5). Der alte Zweck `sammlungsstruktur` (und
      ein Aufruf ohne Zweck) lenkt weiter um; so wirkt der Schutz aus TW-6, bis der neue
      Master-Skill im Repositorium steht.
    - Die Seeds der übrigen Abläufe behalten `zweck: sammlungsstruktur` (gültig); TG-6 setzt sie
      ohnehin auf aus.
    - Der Master-Skill-Absatz steht nur in der Kurzfassung — die Langfassung `vorgehen.md` kennt
      `ui_upload` nicht.
- **Review TG-1/TG-2 (16.11.), behoben:** 4 MAJOR, 7 MINOR, 4 NIT; Notiz ergänzt.
  - **M1:** Playwright `e2e/upload-erfassen.spec.ts` auf „Senden“ bzw. „Lesen lassen“ ohne `ziel`;
    die übrigen E2E-Specs nennen die alten Knöpfe nicht.
  - **M2:** `upload_antwort.sicherheit` stellt bei Unterordnern immer alle Punkte von
    `aus_ordnern` voran, gleich welche `aktion`; Test für `erfasst` wieder da.
  - **M3:** Wortlaut des Coordinators in Rahmen (`_fragen`), Master-Skill und Tests;
    `nicht_gelesen_satz` zeigt das Feld erst auf Wunsch.
    - **(c), Feinentscheid:** Den Verlauf sieht die Umlenkung nicht sauber, darum zählt die
      Nachricht des Zugs. `vorschlag.themenbaum_bezug` (weite Wortliste: Themenbaum, Struktur,
      Gliederung, topic tree, structure, outline) setzt je Zug `THEMENBAUM_KEY` (in `respond` und
      `respond_agent`, neben `GRUNDLAGE_KEY`). Mit `bereitstellen` lenkt `umlenkung` nur mit
      diesem Bezug um. Weit gefasst, weil im Zweifel das TW-6-Netz wie vor TG-2 greifen soll.
  - **M4 (Variante 1):** „aus einem Dokument“ und „aus Ordnern“ fragen nach `einstieg` über
    `vorhanden`/`uebernehmen`, ob sie den vorhandenen Teil verwenden. Ohne Namen im Text: der
    Platzhalter-Wächter lässt nur Teile zu, die ein Schritt davor schreibt.
  - **m7:** `gelesen_frage` und `frei` blieben auch mit M4 tot (`einstieg` schreibt `vorgehen`
    immer) — entfernt; `nach_lesen` geht sonst zu `ordnung`.
  - **m1:** Datenschutzsatz nennt bis TG-3 genau „Ordnernamen, Zahlen und der Name des
    Strukturdokuments“; Manifest und `docs/ui-module.md` stimmig. **m2:** Möglichkeiten im Rahmen
    nach `dienst_upload.schalter()`. **m3:** Ordner → Themenbaum ohne Ablauf:
    `ui_strukturentwurf` mit Ordnername als Thema und oberen Ordnern als `hinweise` (G-E10:
    Ordner sind Ausgangspunkt) — „sag, dass es geführt geht“ hilft nicht, wenn kein Ablauf
    angeboten ist. **m4:** `aria-label` an „Weiter“, `aria-describedby` an „Lesen lassen“. **m5:**
    „Lesen lassen“ ist Hauptknopf, wenn lesbar. **m6:** `docs/ablaeufe.md`, `docs/ui-module.md`.
  - **n1–n4:** „Read document“; Studio „oder ein Ablauf führt weiter“;
    `ui_module/namen.ZWECK_BEREITSTELLEN`; `test_arbeitsstand` ohne `ziel`, doppelter
    Preflight-Test zusammengelegt.
  - Beim Kürzen aufgefallen: Die Manifest-Beschreibung lag über 600 Zeichen; das fing erst der
    Katalog im Backend ab, nicht `module:register`.
- **Zweites Review TG-1/TG-2 (16.11.), behoben:** 2 MAJOR, 6 MINOR, 3 NIT. Die Mechanik ist
  generisch gebaut, damit TG-6 sie nutzt.
  - **MAJOR 1, `verwirft`:** neues Feld an `Schnellantwort` (Liste von Teilnamen, Vorgabe `None`,
    Fassung unverändert). `treiber.weiter_wahl` blendet die Teile sofort aus und meldet sie in
    `Ausgabe.verworfen`; `zug_basis.festhalten` entfernt sie vor `neue_teile` mit dem neuen
    `vorgaenge.teil_entfernen` (samt Ablage und Historie, Konflikt wie beim Setzen). Die
    Simulation verwirft ebenso. Die Prüfung meldet unbekannte Teile und `start` (Text
    `verwirft`). Studio: Schema-Fixture, OpenAPI und Feldtexte de/en (`fields-ablaeufe.ts`). In
    beiden Seeds an „Andere wählen“.
  - **MAJOR 2** (in der Nachprüfung ersetzt, siehe unten): `arbeitsstand._speichern` legte für freie Arbeit (nicht `nur_dieser`) einen neuen
    Vorgang an, wenn der aktuelle — oder der jüngste einer angemeldeten Person — einen Lauf mit
    Status in `treiber.BEENDET` trägt. Die Grenze von drei Vorgängen regelt `vorgaenge.anlegen`
    wie bisher; der Verweis zeigt auf den neuen.
  - **MINOR 3:** Wortliste mit Wortgrenzen (Themenbaum, Sammlungsstruktur, Sammlungsbaum, topic
    tree, Struktur/Gliederung als ganzes Wort samt Mehrzahl); `structure`/`outline` gestrichen.
  - **MINOR 4–6, Dienst `bereitgestellt`:** neuer reiner Dienst. Dienste bekommen dazu einen
    optionalen `DienstKontext` (Teile ohne `$teil`-Pflicht, Sprache, Kennung des lesbaren
    Dokuments; `Umgebung.dokument_id` aus `arbeitsstand.lesbares_dokument`). Typ `wlo.bereit@1`,
    Teil `bereit` mit `{dokument: {name, lesbar} | null, ordner: {name, unterordner} | null}`.
    Beide Seeds beginnen mit `bereit` → `vorhanden` (`wenn_wert` auf `lesbar` bzw.
    `unterordner`) → `einstieg` oder `einstieg_mit`. Den Namen nennt der Text per
    `{teil.bereit.…}`; der Platzhalter-Wächter lässt ihn zu, weil `bereit` davor geschrieben wird.
    `uebernehmen` ist entfallen.
    - **Feinentscheid:** Ohne Lader (Simulation) gilt ein Dokument im Vorgang als lesbar.
    - **Feinentscheid:** Mit Daten führt „Ja, … verwenden“ im Dokument-Ablauf immer zu den Fragen;
      „gleich entwerfen“ gibt es nur im Einstieg ohne Daten. Drei Knöpfe reichen.
  - **MINOR 6, Leiste:** Ohne Daten zählt sie 1, 2, 3, … ohne Lücke, mit gleichem `m`; mit Daten
    steht der Einstieg an derselben Stelle (2), und es geht nur vorwärts. Übersprungene Schritte
    (Upload) bleiben eine Lücke, das ist die Regel „längster Weg“.
  - **MINOR 7:** `vorschlag.zug_merken` setzt Grundlage und Themenbaum-Bezug je Zug und vergisst
    die Umlenkung; beide Antwort-Knoten rufen nur noch es. Integrationstests im Harness von
    `test_ablauf_zug`: beendeter Lauf → freier Upload → Start → Übernahme (Ordner und Dokument),
    unlesbares Dokument, „Anderes wählen“ + „Senden“ → `ohne_dokument`.
  - **MINOR 8:** Deploy-Notiz zu eigenen Studio-Fassungen und zum gleichzeitigen Übertragen des
    Master-Skills.
  - **NIT 9:** Wortlaut „die Punkte, die auch die KI sieht (gedeckelt)“. **NIT 10:** Nach einem
    endgültigen Lesefehler ist „Senden“ der Hauptknopf. **NIT 11:** „einen Themenbaum daraus“ nur,
    wenn `ui_strukturentwurf` (Studio-Schalter) oder ein Ablauf mit Entwurf angeboten ist.
  - **Nebenbei:** Der Teil `bereit` erschien unter „Gesammelte Daten“ als `dict`
    (`treiber._zusammenfassung` kennt nur `titel`). Jetzt gibt es eine Kurzbeschreibung je Dienst
    (`werkzeuge.ZUSAMMENFASSUNG`), für `bereit` etwa „Dokument „…“, Ordner „…““ bzw. „—“.
- **Nachprüfung TG-1/TG-2 (16.11.), behoben:** Ergebnis „merge-reif: ja“ mit 5 MINOR und 4 NIT,
  dazu 1 Fehler der vollen Suite.
  - **0:** `wlo.bereit@1` hat im Studio einen Namen („Bereitgestellte Daten“ / „Provided data“;
    `TYP_NAMEN` in `ablauf-daten.component.ts`, `ablaufDaten.typName.bereit`).
  - **1–4, Regel umgedreht:** Die Trennung in `arbeitsstand._speichern` ist zurückgenommen; freie
    Arbeit landet wieder im aktuellen Vorgang.
    - Stattdessen übernimmt `zug._ziel_vorbereiten` beim Schließen (Lauf beendet, fremd oder
      `frisch`) die Bereitstellungs-Teile in den neuen Vorgang.
    - Konstante `arbeitsstand_teile.BEREITSTELLUNG = ("structure", "document")`; TG-3 ergänzt sie
      um einen Eintrag je Teil.
    - Übernommen wird nur Vorhandenes, mit Typ, Wert (über `teil_wert`, auch aus der Ablage) und
      Kurzbeschreibung. Ohne Historie, Entwurf, Lauf und Antworten.
    - `document` bleibt ein gültiger Verweis (`dokument:<id>` auf das Sitzungsdokument); auch das
      Aufräumen (`dokument_teile_entfernen`) findet ihn im neuen Vorgang über die Akte.
    - **Feinentscheid:** Auch beim `frisch`-Start (ein schreibender Ablauf schließt jede freie
      Arbeit) gehen `structure`/`document` mit; `ablage` steht bewusst nicht in der Konstante
      (N14).
    - **Tests im Ablauf-Harness:** Ablauf beendet → freier Upload → Start → Übernahme (Ordner und
      Dokument); Fall 3: wartender fremder Lauf → Dokument gelesen → anderer Start → Übernahme.
      Fall 1: zweiter Tab, freie Arbeit → der wartende Lauf bleibt unverändert, kein neuer
      Vorgang. Fall 2: Entwurf nach dem Ende bleibt im selben Vorgang. Fall 4: freie Arbeit legt
      keinen Vorgang an. Nur Bereitstellung wird übernommen (kein `draft`).
  - **5:** `typen.NICHT_VERWERFBAR = {"ablage"}` (erweiterbar); die Prüfung meldet
    `verwirft_repo` (de/en).
  - **6 (NIT, beabsichtigt):** `verwirft: [document]` nimmt nur den Teil aus dem Vorgang; das
    Dokument bleibt an der Sitzung lesbar (24 h). Im freien Chat könnte `ui_strukturentwurf` mit
    `aus_dokument` es also noch lesen — das Verwerfen gilt dem Ablauf, nicht der Sitzung.
  - **7:** Wortliste um `themen[\s-]*baum`, `topic[\s-]*trees?` und `collection
    (structure|tree)s?` ergänzt; Testfälle dazu.
  - **8:** „einen Themenbaum daraus“ prüft den Weg je Art: Dokument → ein Ablauf mit
    `dokument_lesen` und Entwurf per `ui_strukturentwurf`; Ordner → einer mit
    `strukturentwurf_aus_ordnern`; `ui_strukturentwurf` an gilt für beide.
  - **9:** `werkzeuge.Dienst` ist ein `Protocol` mit `(args, k=None, /)`.
- **TG-3 Datenmodell** (siehe „Datenmodell“; ersetzt die drei Teile aus G-E1):
  - **TG-3a:** `struktur` (`wlo.auswahl@1`) mit Dateien je Ordner und festem `i`.
    - Manifest: Antwortschema und `vorgang.schreibt`;
    - `teile_aus_antwort`, `structure` als abgeleitete Sicht;
    - Grenzen (500 Dateien, Namen 120 Zeichen), kein Log der Namen, neuer Hinweistext.
  - **TG-3b:** `ablage.index` = `i` aus `struktur`. Die Übertragung schickt die feste Nummer,
    nicht die Position in der gefilterten Liste. Das schließt T1 (`ablage_zuordnen`).
  - **TG-3c:** `metadaten`:
    - Lizenz und `i` ergänzen;
    - in Blöcken zu 50 lesen bis 500 Knoten, unter der Grenze von 64 KB je Teil;
    - was nicht passt, steht in `fehlend`.
  - **TG-3a bis TG-3c gebaut (16.11.), noch ohne unabhängiges Review:** Notiz
    `docs/aenderungen/2026-11-16-datenmodell-struktur.md`.
    - **TG-3a:** `ui_upload` schickt je Ordner `dateiliste` (`i`, Name, Endung, Größe, Rolle);
      Manifest mit `$defs.datei`, Warnung `namen_gekuerzt`, `vorgang.schreibt` um `struktur`.
      `teile_aus_antwort` schreibt `struktur` (`wlo.auswahl@1`: `{struktur, zahlen, warnungen}`) und
      `structure` ohne `dateiliste`; `BEREITSTELLUNG` = `structure`, `struktur`, `document`. Die KI
      sieht „Dateien: 12 Dateien in 3 Ordnern, davon 1 Strukturdokument“; die Sicherheitsprüfung
      liest die Namen bis 3000 Zeichen. `bereitgestellt` meldet `dateien` und `inhaltsdateien`.
      Studio-Typname „Auswahl mit Dateien“ / „Selection with files“. Datenschutzsatz „Ordner- und
      Dateinamen gehen an den Chat …“.
    - **TG-3b:** Die Freigabe trägt `i` je Eintrag (`AblageEintrag.i`, `Eintrag.i` im Backend,
      eindeutig); der Teil `ablage` speichert `i` neben `index`. T1 in `offene-befunde-und-todo.md`
      erledigt.
    - **TG-3c:** `metadaten_lesen` liest in Blöcken zu 50 bis 500 Nodes, je Node `lizenz` und `i`;
      der ganze Teil samt `fehlend` bleibt unter 60 000 Bytes.
  - **Feinentscheide TG-3a bis TG-3c:**
    - **`i` ist die Stelle in `Erfassung.dateien`** (nach Pfad sortiert, über der Höchstzahl
      gekappt). Rollenwechsel ändern sie nicht; eine neue Auswahl vergibt neu.
    - **Systemdateien** (`.DS_Store`, `Thumbs.db` …) stehen nicht in `dateiliste` — wie im Baum der
      Ansicht. Ihre Nummern bleiben frei. Ignorierte Dateien (leer, zu groß, von Hand) stehen mit
      Rolle `ignorieren` darin; `zahlen.dateien` zählt weiter alle.
    - **Feldname `dateiliste`**, weil `dateien` je Ordner schon die Zahl ist (Rückwärts).
    - **`struktur` nur, wenn das Widget Dateien schickt:** Eine Antwort ohne `dateiliste` (Widget vor
      TG-3a) ergibt wie bisher nur `structure` — sonst meldete `bereitgestellt` 0 Dateien als
      Wahrheit.
    - **Keine 64-KB-Grenze für `struktur`:** wie `structure` geht der Teil über 8 KB in die Ablage
      des Vorgangs. 500 lange Namen (bis rund 100 KB) sind möglich. Dienst- und Modul-Schritte eines
      Ablaufs bekommen den ganzen Teil; an ein Werkzeug der KI geht über `$teil` höchstens 64 KB
      (`teil_verweise.MAX_BYTES` — sonst fehlt der Teil, keine stille Kürzung).
    - **Sicherheitsprüfung:** Dateinamen zuletzt im Vorsatz, gedeckelt auf 3000 Zeichen wie die
      Ordner-Übersicht. Der Vorsatz bleibt so unter rund 13 000 Zeichen und damit weit im ganz
      geprüften Teil der Moderation (8 Abschnitte zu 4000). Namen hinter dem Deckel sieht kein Modell
      ungeprüft: Die KI bekommt nur die Zusammenfassung; wer Namen später an ein Modell gibt (TG-4),
      moderiert selbst (`metadaten.moderationstext`).
    - **„Andere wählen“ in „aus Ordnern“ verwirft auch `struktur`**, sonst bliebe die Auswahl der
      abgelehnten Ordner liegen. „Anderes wählen“ in „aus einem Dokument“ bleibt bei `document`:
      Eine neue Auswahl überschreibt `struktur` ohnehin. TG-6 regelt das im neuen Ablauf.
    - **`dateien` in `bereitgestellt`** zählt nicht ignorierte Dateien (Inhalt und Struktur) aus
      `struktur`; ohne `struktur` 0, weil der Weg über die Dateinamen dann nicht trägt.
    - **TG-3b: `index` bleibt die Stelle in der Freigabe.** Das MCP zählt `entries` nach der Stelle
      (`wlo-mcp-server-sc`, `curation-batch.ts`: `map((e, index) => …)`); `/datei` und
      `wlo_store_batch_file` brauchen sie. `i` steht daneben und geht nicht an das MCP. Ohne `i`
      (Widget vor TG-3b) fehlt das Feld — kein Raten. `frueher` (Einträge eines ersetzten Stapels)
      trägt kein `i`: eine neue Auswahl hätte andere Nummern.
    - **TG-3c: Lizenz** ist `license` aus `get_nodes_details` (lesbare Bezeichnung aus
      `ccm:commonlicense_key`, etwa „CC BY-SA“), auf 60 Zeichen gekürzt; leer ohne Angabe.
    - **TG-3c: Blöcke nacheinander**, nicht parallel (Last am MCP). Ein gescheiterter Block hält an;
      der Rest steht in `fehlend`. Scheitert schon der erste, entsteht kein Teil (wie vorher).
    - **TG-3c: Kürzung** in dieser Reihenfolge: Beschreibung auf 100, Beschreibung leer, Listen auf
      2, Listen leer, Titel auf 80, leere Felder weglassen, zuletzt Inhalte vom Ende nach `fehlend`.
      Leser nehmen `get` (`als_dokument` geprüft). Mit kurzen Titeln passen rund 500 Nodes.
  - **TG-3d:** Teil `strukturdokument` mit Quelle `chatbot` oder `wlo` und dem Leser
    `strukturdokument.text()`. `aus_dokument` liest darüber. `document` bleibt als Alias.
  - Specs und Tests je Teilpaket.
- **TG-3e Mehrere Strukturdokumente** (Nutzer 16.11.: „aus einem oder mehreren
  Strukturdokumenten“):
  - **Anonym:** bis zu 5 Dokumente je Sitzung. Migration: `dokument_uploads.session_id` ist nicht
    mehr eindeutig, nur noch indiziert. `speichern` ersetzt nur das älteste über der Grenze.
  - **Mit WLO:** jeder Knoten mit der Rolle `struktur` in `ablage`.
  - Der Teil `strukturdokument` wird eine Liste. Der Generator `aus_dokument` nimmt mehrere:
    Jedes Dokument wird zu einem Abschnitt oberster Ebene, die Kennungen bekommen einen Präfix
    (`d1-a3`), Fundstellen nennen Dokument und Abschnitt.
- **TG-3f Ordnerstruktur mit Inhalten** (Nutzer 16.11.: „enthaltene Inhalte werden erschlossen
  oder/und gemerkt“):
  - `aus_ordnern` schreibt je Knoten die Inhalte seines Ordners als Verweise in den Entwurf: `i`,
    Name und, nach der Ablage, `node_id`.
  - „Gemerkt“ heißt: Dateinamen je Ordner, auch anonym.
  - „Erschlossen“ heißt: nach Übertragung und Kestra-Flow `node_id` und Metadaten.
  - `ui_strukturentwurf` zeigt je Knoten die Zahl seiner Inhalte. Das spätere Befüllen
    („Sammlungen 1:1“) liest diese Verweise.
- **TG-3d bis TG-3f gebaut (16.11.), noch ohne unabhängiges Review:** Notiz
  `docs/aenderungen/2026-11-16-strukturdokumente-und-ordnerinhalte.md`.
  - **TG-3d:** Teil `strukturdokument` (`wlo.strukturdokumente@1`,
    `services/dokumente/strukturdokument_teil`) mit Einträgen `{name, quelle, ref}`; geschrieben nach
    dem Lesen (Antwort von `ui_upload`, vom Server bestätigt) und nach der Ablage
    (`ablage/vorgang_teil.speichern`, Knoten mit Rolle `struktur`). In `BEREITSTELLUNG`. Leser
    `services/dokumente/strukturdokument` (`text`, `staende`, `im_vorgang`): anonym aus
    `dokument_uploads`, mit WLO über `get_wlo_content_text` (nur lesend). Der Lader
    (`dokumente/stand.lader`) nimmt die Einträge des Vorgangs, sonst alle lesbaren der Sitzung.
    `document` bleibt Rückwärts-Teil. Studio-Typname „Strukturdokumente“ / „Structure documents“.
  - **TG-3e:** Migration 0023 (Sitzung nur indiziert), `ablage.MAX_JE_SITZUNG = 5`, das sechste
    ersetzt das älteste. Upload-Feld: bis fünf Strukturdokumente, „Lesen lassen“ liest nacheinander,
    Fortschritt und Fehler je Dokument, „Ohne dieses weiter“. Antwort: `dokument` (erstes) und bei
    mehreren `dokumente`. Generator: `dokument_gliederung.zusammenfuehren`, `stand.vereint`, eigene
    Aufgabe für Ebene 1, Fundstelle „Dokument › Abschnitt“. `bereitgestellt` meldet
    `strukturdokumente` und `lesbare_strukturdokumente`. Die Ablage nimmt bis fünf Strukturdokumente.
  - **TG-3f:** `strukturentwurf_aus_ordnern` liest `struktur` (gleiche Ordner), sonst `structure`; je
    Punkt `inhalte: [{i, name, node_id?}]`, `node_id` aus `ablage`. Entwurfsformat und Manifest mit
    optionalem `inhalte`, höchstens 500 im Entwurf. `ui_strukturentwurf` zeigt „n Dateien“; die
    Kompaktfassung an die KI nur die Zahl.
- **Feinentscheide TG-3d bis TG-3f:**
  - **Wert des Teils `strukturdokument` ist ein Objekt** `{"dokumente": [...]}`, keine nackte Liste —
    alle anderen Teile sind Objekte (Kurzbeschreibung, Titel, Prüfung lesen `dict`).
  - **Ein Verweisfeld `ref` für beide Quellen** (`dokument:<id>` bzw. die node_id) — so findet das
    Aufräumen die Einträge mit derselben JSON-Abfrage wie beim Teil `document`.
  - **Die letzte Bereitstellung gilt:** ein neues Lesen ersetzt die `chatbot`-Einträge (wie eine neue
    Auswahl `struktur` ersetzt); die `wlo`-Einträge bleiben. Ohne Teil (Vorgang vor TG-3d) gelten alle
    lesbaren Dokumente der Sitzung.
  - **Mehrere Dokumente werden ein Dokument mit `d1`, `d2` … als oberster Ebene** — „Jedes Dokument
    wird ein Abschnitt oberster Ebene“ gilt der Gliederung, nicht dem Entwurf. Die Dokumente selbst
    werden keine Punkte; dasselbe Ordnungselement aus mehreren Dokumenten wird ein Punkt.
  - **Der Anfang für Ebene 1** ist bei mehreren je Dokument ein gleich langes Stück (insgesamt 1500),
    die Übersicht zeigt eine Ebene mehr (bis 4), damit die Kapitel unter jedem Dokument sichtbar
    bleiben.
  - **Ein Volltext aus WLO gilt als ungeprüft:** vor Ebene 1 durch die Moderation wie bei
    `aus_inhalten`; ein Sitzungsdokument wurde schon beim Hochladen geprüft.
  - **Ein Dokument aus WLO braucht den Studio-Schalter „Dokument im Chat“ nicht**, ein
    Sitzungsdokument schon (unverändert).
  - **In `bereitgestellt` gilt ein Knoten in WLO als lesbar** — ob das Repositorium schon einen
    Volltext hat, weiß erst der Leser (sonst müsste der Dienst je Knoten das MCP fragen).
  - **`dokument.lesbar` und `_dokument_bestaetigt` prüfen gegen alle lesbaren Dokumente:** mit
    mehreren ist das erste gelesene (Teil `document`) nicht mehr das jüngste.
  - **Nach einem Lesefehler** hält der Ablauf an; „Noch einmal“ liest dasselbe Dokument, „Ohne dieses
    weiter“ das nächste. Geantwortet wird einmal mit allen gelesenen; ist nach dem Auslassen nur eins
    gelesen, ist die Antwort die von vorher (ohne `dokumente`).
  - **Ein sechstes Strukturdokument ist im Feld gesperrt**, statt still ein anderes zu verdrängen.
  - **TG-3f: Dateien tieferer Ordner** gehören zum tiefsten Punkt darüber; Dateien direkt in der
    Wurzel haben keinen Punkt; nur Rolle `inhalt`. `node_id` nur aus `stored`-Einträgen mit `i`.
  - **TG-3f: Der Dienst liest `struktur` nur, wenn er dieselben Ordner trägt** wie das Argument
    (`structure`) — sonst stammte die Dateiliste aus einer anderen Auswahl.
  - **TG-3f: Ein zu großer gemerkter Entwurf** (`entities`, über 60 000 Zeichen) verliert mit den
    Texten auch die `inhalte`; sie stehen im Teil `draft`.
  - **Offen:** der WLO-Weg des Lesers ist nur mit Attrappen getestet. Gegen das echte Repositorium
    (eigener Testknoten, angemeldet) misst TG-7; offen ist dort, ob das Repositorium den Volltext
    einer frisch abgelegten Datei schon hat (sonst `reason: not_extracted`, der Eintrag fällt dann
    für diesen Entwurf weg).
- **TG-4 Werkzeug `inhalte_aus_dateien`** — G-E9: `werkzeuge.py`, `typen.py`, Prüfung und Katalog,
  Tests.
- **TG-5 Feste Zuordnung Teile → Auftrag** — G-E8: `ki_schritt` und `dienst._strukturentwurf`;
  Tests für `umfang`, `stufe` und die Hinweiszeilen.
- **TG-6 Ablauf `themenbaum.yaml`** — G-E2, G-E6, G-E7, G-E10:
  - Seed mit Tests je Zweig;
  - die vier alten Abläufe auf `aktiv: false`, im Kopf „abgelöst durch themenbaum“;
  - Seed-Regeln (Freitext an Fragen);
  - `werksabgleich`;
  - Studio-Schema bei Bedarf.
- **TG-4 bis TG-6 gebaut (16.11.), noch ohne unabhängiges Review:** Notiz
  `docs/aenderungen/2026-11-16-ablauf-themenbaum-erstellen.md`.
  - **TG-4:** Dienst `inhalte_aus_dateien` (`services/ablauf/inhalte_aus_dateien`): `struktur` →
    `metadaten` (`wlo.metadaten@1`), nur Rolle `inhalt`, je Eintrag `i` ohne `node_id`, Titel aus
    dem Dateinamen, „Ordner: a / b“ als Beschreibung, `block_id` der Auswahl. In `DIENSTE`,
    `DIENST_AUSGABE`/`DIENST_EINGABE`, Studio-Katalog und Feldhinweis; Hinweis `metadaten_teil`
    wie bei `metadaten_lesen`.
  - **TG-5:** Feld `agent.vorbelegen` (Vorgabe `None`), `services/ablauf/vorbelegung`; die
    Vorbelegung reist über `Umgebung.vorbelegung` (Muster-Weg: `VORBELEGUNG_KEY`; Agent-Weg:
    `modul_vorbelegung`) und wird in `dienst.aufruf` vor der Schema-Prüfung eingesetzt. Zeile
    `[VORBELEGT — …]` für die KI.
  - **TG-6:** Seed `06-ablaeufe/themenbaum` (40 Schritte, 19 Selbsttests), ab Werk an, ohne
    Voraussetzung; die vier alten aus, ihre Fehler-Enden mit Ausweg (auch „Sammlung prüfen“).
    `bereitgestellt` meldet `art`, `name`, `wlo_ablage`. Neuer Prüfhinweis „Ende ohne Ergebnis“
    (`stumme_enden`), Test über alle Seeds. Master-Skill, `docs/ablaeufe.md` nachgezogen.
- **Feinentscheide TG-4 bis TG-6:**
  - **TG-4: Was nicht unter 60 000 Bytes passt,** fällt vom Ende weg und steht als Zahl in
    `ausgelassen` — `fehlend` trägt nach dem Format nodeIds, die es hier nicht gibt. Vorher werden
    Pfade gekürzt, dann weggelassen, dann Titel gekürzt (500 lange Namen passen so).
  - **TG-4: Kein eigener Moderationsschritt** — die Namen gehen erst im Strukturentwurf an ein
    Modell, und `aus_inhalten` prüft Übersicht und Anfang schon (`_ebene_eins_pruefen`).
  - **TG-5: Die KI geht vor.** Die Vorbelegung füllt nur Argumente, die der Aufruf nicht setzt;
    Hinweise werden zusammengeführt (Ablauf zuerst). Begründung: „Die KI darf überschreiben, wenn
    die Person es im Gespräch ändert“ — ein fester Vorrang des Ablaufs machte das unmöglich. Gegen
    das Überschreiben aus Gewohnheit nennt `[VORBELEGT — …]` die gesetzten Argumente (nur Namen und
    Zahlen, keine Eingaben) mit der Bitte, sie nur bei einer Änderung anzugeben.
  - **TG-5: Nur mit `agent.vorbelegen`** und nur für Antworten dieses Laufs (`lauf.antworten`) —
    die alten Abläufe schreiben `stufe`, `thema`, `zweck` auch; sie bleiben, wie sie sind.
  - **TG-5:** Die Vorbelegung wird **vor** der Schema-Prüfung eingesetzt — so zählt ein
    vorbelegtes `thema`, und die Werte sind geprüft (auf die Längen des Manifests gekürzt).
  - **TG-6: Gründlich erkennt der Ablauf an `bereit.wlo_ablage`** = `schalter()["ablage_in_wlo"]`
    des Upload-Dienstes (Studio-Schalter, MCP, Anmeldung), gelesen beim Start. In der Simulation
    die Anmeldung des Testfalls.
  - **TG-6: Keine Voraussetzung „Anmeldung“** — Aufträge und `metadaten_lesen` dürfen ohne sie
    stehen, wenn sie einen Ersatzweg haben (Prüfung angepasst; ohne Anmeldung starten sie nicht).
  - **TG-6: Direktstart** über `werkzeuge.ablauf_schreibt_ungefragt`: ein Auftrag mit Rückfrage
    direkt davor zählt nicht (wie TW-6 beim Upload-Feld). Der frische Vorgang (N14) hängt weiter an
    `ablauf_schreibt_selbst`.
  - **TG-6: Verzweigt wird auf das deutsche Label** der Grundlage (`enthaelt` Thema, Dokument,
    Ordner, Datei), nach „Ja, verwenden“ auf `bereit.art`; nach einem Upload auf die Teile selbst
    (`structure.struktur.kinder`, `struktur.zahlen.inhalte`, `strukturdokument`, `ablage`), nicht
    auf ein neu gerechnetes `bereit`. Getippte Grundlagen treffen über `synonyme`; sonst gelten sie
    als Thema.
  - **TG-6: Jede Grundlage hat ihr eigenes Upload-Feld** (Dokument, Ordner, Dateien) mit eigener
    Prüfung danach, Rückwege nur zu `daten`. Ein geteilter Upload mit gemeinsamer Prüfung machte
    den Graphen kreisig, und die Leiste („längster Weg“) zählte rückwärts. Dafür entfallen „Andere
    Grundlage“ in den Fehlerwegen (Auswege sind „Nochmal“ und „Frei weiter“) und ein eigener Satz
    vor dem schnellen Weg (er steht im Text des Upload-Felds).
  - **TG-6: Ordner erschließen** nach dem Prüfpunkt über dieselbe Frage wie bei Dateien
    („Gründlich über WLO“ / „Nur die Dateinamen“); danach Metadaten, und der Lauf endet (der
    Entwurf bleibt, die node_ids bindet das Speichern des Entwurfs, MINOR 8 aus TG-3d–f).
  - **TG-6: „Ende ohne Ergebnis“ ist ein Hinweis, kein Befund** — eigene ältere Abläufe sollen
    weiter speichern; die Seeds hält ein Test frei.
  - **TG-6: Wendungen:** alle 23 der vier alten, verteilt auf drei Text-Auslöser (je höchstens 10).
  - **TG-6: Leiste** zählt jede Kante einmal (`fortschritt._Suche`): Regeln mit demselben Ziel
    vervielfachten die Wege über das Besuchsbudget hinaus.
- **TG-7 Durchtest und Doku** (Nutzer 16.11.: alle Optionen testen):
  - **Durchtest gegen eine Wegwerf-DB mit dem lokalen Backend:** natives OpenAI `gpt-6-luna`,
    MCP und Repositorium auf Staging. Je Option ein vollständiger Durchlauf im Chat:
    1. **Themenbaum aus Thema**, anonym.
    2. **Nach Ordnerstruktur**, Inhalte gemerkt (anonym) und erschlossen (angemeldet: Ablage,
       Kestra, Metadaten).
    3. **Aus loser Inhaltsmenge:** anonym über die Dateinamen; angemeldet über WLO-Ablage und
       Kestra-Flow.
    4. **Aus einem und aus mehreren Strukturdokumenten:** anonym im Chatbot umgewandelt;
       angemeldet über die Knoten.
    5. **Anonym hochladen und weiterverwenden:** Dokument lesen lassen, dann frei im Chat damit
       arbeiten. Keine Kestra-Umwandlung.
  - **Sicherheitsregeln für den Durchtest:**
    - Angemeldet nur mit dem Testkonto (`deploy/.env.wlo-testuser`) gegen Staging-Hosts.
    - Selbst angelegte Knoten werden danach wieder entfernt. Nichts Bestehendes wird gelöscht.
    - Metadaten nur an den eigenen Testknoten.
    - Der Kestra-Auftrag läuft mit dem Staging-Schlüssel als durchgereichtem Schlüssel.
  - **Ergebnis:** Protokoll je Option (Weg, Teile, Entwurf, Zeiten) in der Änderungsnotiz.
- **TG-7b Abschluss:**
  - Simulation aller Zweige;
  - ein Chat-Smoke je Grundlage gegen die Wegwerf-DB;
  - Änderungsnotiz mit Umstieg;
  - `offene-befunde-und-todo.md` (O-26 erledigt, Sackgassen erledigt).

Reihenfolge: TG-1/TG-2, dann TG-3/TG-4, dann TG-5, dann TG-6, dann TG-7. TG-3 und TG-4 lassen
sich parallel bauen.

## Prüfung

- **Jeder Zweig** in den Selbsttests der Datei: Thema, Dokument (neu und schon da), Ordner mit
  und ohne Unterordner, Dateien, Ausstieg, Fehler.
- **Keine Sackgasse:** Ein neuer Test prüft, dass jedes `ende` ohne `ausstieg` entweder „fertig“
  bedeutet oder einen Knopf zum Weitermachen hat. Das gilt für alle Seeds.
- **Upload:** Im Frontend nennt kein Text und kein Knopf mehr einen Themenbaum. Ein Spec prüft
  den Zielkatalog. Alte Antworten werden angenommen (Rückwärtstest).
- **Auftrag:** `umfang: ausführlich` ergibt `tiefe=3`.
- **Regression:** Backend-Suite, `ui-module`, `ui`, `studio`, ESLint, ruff.

## Risiken

- **Großer Ablauf, 40 Schritte als Grenze:** Der Ablauf ist auf etwa 30 Schritte geplant.
  Werden es mehr, wandert die Grundlage-Verzweigung in den KI-Schritt.
- **Der neutrale Rahmen kann die KI unschlüssig machen.** Der Master-Skill-Absatz und ein
  Chat-Smoke prüfen das.
- **Laufende Läufe der alten Abläufe brechen beim Werksabgleich ab** (Fassung). Das steht in der
  Notiz.
- **Dateinamen können personenbezogen sein** („Zeugnis_Müller.pdf“). Deshalb nur auf Klick
  (G-E1), mit Hinweis im Feld, und nicht ins Log.

## Offene Fragen

Keine. G-E1 bis G-E3 hat der Nutzer am 16.11. beantwortet.

**Offen bleibt die Bedingung „angemeldet und Ablage an“ am Ablauf.** Eine Verzweigung kennt heute
keine Bedingung auf die Anmeldung. Gelöst wird das beim Bau von TG-6 über den Teil, den das
Upload-Feld nach der Ablage schreibt (`ablage`): Der Ablauf fragt nach dem gründlichen Weg nur,
wenn das Feld die Ablage anbietet. Er liest dafür die Systemfelder des Dienstes, nicht die
Anmeldung selbst.

### Review TG-3a–c (16.11.) — Entscheide, Behebung nach TG-3d–f

1 MAJOR, 4 MINOR, 2 NIT. Entscheide:
- **R3-1 (MAJOR):** Ordner- und Dateinamen gehen nur an die Moderation (Stufe 2), nicht an die
  Krisen- und Drohungsmuster (`regex_gate`). Eine Datei „Suizid-Prävention.pdf“ löste sonst die
  Krisenantwort aus und verwarf den Upload. In `quality_events` kommen keine Namen. Für
  Ordnernamen galt das schon vorher und wird mit behoben.
- **R3-4:** Ausgeschlossene Dateien (Rolle `ignorieren`) gehen ohne Namen mit, nur `i`, Endung und
  Größe (Datensparsamkeit).
- **R3-2:** `struktur` trägt die `block_id` der Auswahl. Leser verknüpfen `struktur` und `ablage`
  nur bei gleicher `block_id`. `grund` prüft `i < zahlen.dateien`.
- **R3-3:** `struktur` ist von der Pauschalfreigabe für bestätigbare Werkzeuge ausgenommen, nur
  über `liest`.
- **R3-5:** `verwirft` koppelt Alias-Paare im Treiber: `structure` ↔ `struktur`, `document` ↔
  `strukturdokument`.
- **NIT:**
  - Ein Name nur aus Leerzeichen wird „(ohne Namen)“.
  - Doku: Kopf von `upload_antwort.py`, Lizenz-Beispiel „CC BY-SA“, „bis 500“ praktisch 200 je
    Stapel.

**Behoben (16.11., nach TG-3d–f), noch ohne Nachprüfung:** Notiz
`docs/aenderungen/2026-11-16-datenmodell-struktur.md`, Abschnitt „Review-Behebung“.
- **R3-1:** `antwort.sicherheits_teile` trennt freien Text und Namen (`PruefText`);
  `Form.sicherheit_nur_namen` sagt je Antwort, ob `sicherheit` nur Namen liest. `assess` und
  `preflight` geben dem Regex-Gate nur den freien Text, die Namen an
  `assess_safety(…, nur_moderation=…)`. Ins Protokoll (`log_safety_event` in `preflight` und
  `build._log_turn_safety`) kommt `antwort.protokoll_text`: der freie Text ohne zitierte Namen.
  - **Feinentscheid:** Die Injection-Muster lesen die Namen weiter mit (sie heben nur auf `medium`,
    und Ordnernamen sieht die KI); die Rechtsprüfung bekommt nur den freien Text.
  - **Feinentscheid `ui_strukturentwurf`:** nur ein **unbearbeiteter** Entwurf (`bearbeitet:
    false`) gilt als Namen — seine Titel stammen aus Ordnern, WLO oder der KI (sonst löste ein
    Entwurf aus dem Ordner „Suizid-Prävention“ beim Übernehmen die Krisenantwort aus). Hat die
    Person bearbeitet, kann ein Titel ihr eigener Satz sein: dann alle Stufen wie bisher.
  - **Feinentscheid Protokoll:** Die Blase einer Antwort per Knopf nennt den Namen in
    Anführungszeichen („Ordner „Physik“ erfasst“); mit einer Auswahl im Zug ersetzt
    `protokoll_text` zitierte Stellen durch „…“. Eine getippte Nachricht ohne Auswahl bleibt, wie
    sie ist.
- **R3-4:** Das Upload-Feld schickt ausgeschlossene Dateien ohne Namen; das Schema verlangt den
  Namen nur ohne Rolle `ignorieren` (`if/then/else`). Ein altes Bündel verliert ihn in
  `upload_antwort.rueckwaerts` vor der Prüfung.
- **R3-2:** Der Teil `struktur` trägt `block_id`; `arbeitsstand_teile.gebunden` verknüpft
  `struktur` und `ablage` nur bei gleicher `block_id` (`strukturentwurf_aus_ordnern`); der Teil
  `metadaten` trägt die `block_id` seiner Ablage. `grund` prüft `i < zahlen.dateien`.
- **R3-3:** `teil_verweise.NUR_UEBER_LIEST = {"struktur"}`. **Feinentscheid:** `document` und
  `strukturdokument` bleiben frei — nur Namen der Dokumente, die die Person selbst hat lesen
  lassen, und Verweise; ein schreibendes Werkzeug zeigt sie in der Vorschau.
- **R3-5:** `typen.ALIAS_PAARE` und `mit_aliassen` im Treiber (`weiter_wahl`); die Simulation folgt
  über `Ausgabe.verworfen`. Die Seeds bleiben, wie sie sind (`[structure, struktur]` bzw.
  `[document]` — das verwirft jetzt auch `strukturdokument`).
- **NIT:** Ein Dateiname nur aus Leerzeichen wird „(ohne Namen)“ / „(no name)“
  (`antwortDaten(…, ohneName)`); Doku nachgezogen.
- **Nachtrag aus Review TG-3d–f, MINOR 1:** Der Schnitt aus R3-1 ist ersetzt. Namen laufen wieder
  durch die Krisen- und Drohungsmuster, aber nur als Hinweis ohne Sperre (siehe dort).

### Review TG-3d–f (samt R3, 16.11.) — behoben

1 MAJOR, 8 MINOR, NITs und 1 Fehler der vollen Suite. Entscheide des Koordinators, umgesetzt;
noch ohne Nachprüfung. Notizen: `docs/aenderungen/2026-11-16-strukturdokumente-und-ordnerinhalte.md`
(Abschnitt „Review-Behebung“) und `2026-11-16-datenmodell-struktur.md` (R3-1 überholt).
- **0, Suite:** Der Leser loggt keinen Servertext mehr, nur feste Gründe
  (`strukturdokument.GRUENDE`; ein unbekannter wird `ohne_text`).
- **M1 (MAJOR), TB-E1:** Der Leser liest Sitzungsdokumente über `ablage.alle_fuer_aufrufer` und
  filtert nach den Kennungen des Teils. Wer anonym liest und sich anmeldet, übernimmt die Dokumente.
  Eine Abfrage statt einer je Eintrag.
- **MINOR 1, Hinweis statt Sperre:** `safety.namen_pruefung` (Gründe `crisis_signal_in_names`,
  `threat_signal_in_names`) läuft in `assess` und `preflight` über die Namen, in jeder Stufe, auch
  „regex“.
  - Krise: `TurnContext.krisenhilfe`. `build.run_turn` hängt `safety.krisenhilfeNamen` (de/en,
    Nummern wie M01) an die Antwort, auch an die eines Ablaufs.
  - Drohung: nur der Grund.
  - Upload und Teile bleiben (`risk_level` unverändert).
  - Der Grund steht im Sicherheitsprotokoll, ohne Namen (`safety_log` loggt ihn auch bei
    niedrigem Risiko, `preflight` vor einem frühen Ende).
  - Studio-Hinweis zur Sicherheitsstufe de/en.
  - **Feinentscheid:** Die Hilfsnummern stehen nicht im gespeicherten Verlauf — ein fester
    Sicherheitssatz, kein Teil des Gesprächs für die KI.
  - **Feinentscheid:** Bei hohem Risiko im freien Text keine zweite Zeile, denn M01 antwortet selbst.
- **MINOR 2:** Der Leser schreibt die Sitzungsdokumente (berühren) fest und gibt die Verbindung
  frei, bevor er das MCP fragt. WLO-Volltexte liest er parallel (höchstens 3) mit Gesamtfrist.
  - **Feinentscheid:** Die Frist ist fest, 30 s. Der Lader ist ohne Argument gebaut, die Frist des
    Entwurfs kennt er nicht. `staende(…, frist_ende=…)` nimmt eine, wenn ein Aufrufer sie hat.
- **MINOR 3:** `Lesung.fehlend` mit `(Name, Grund)`.
  - Gemischt: Der Stand trägt `fehlend`, und die Quittung an die KI nennt „Dokument „…“: Volltext
    noch nicht erzeugt, später erneut.“ Der Name ist entschärft.
  - Nur WLO ohne Text: `stand.OhneVolltext`, im Dienst Fehlercode `volltext_fehlt` mit Satz.
  - **Feinentscheid:** `bereitgestellt` bleibt, wie es war. Ob ein Volltext da ist, weiß erst der
    Leser; ohne MCP-Aufruf je Knoten ist es nicht bekannt.
- **MINOR 4:** In `strukturdokument_teil.aus_ablage` steht der aktuelle Stapel vor `frueher` (die
  jüngsten zuerst). `frueher` nur, solange Platz ist.
- **MINOR 5:** `ablage.speichern` löscht zuerst die abgelaufenen der Sitzung und ein Dokument
  desselben Aufrufers mit gleichem Namen und gleicher Größe (erneutes Hochladen nach einem
  Netzfehler). Gezählt werden nur die lesbaren desselben Aufrufers.
- **MINOR 6:** `log_turn_quality(…, ui_antwort=…)` schreibt `protokoll_text`. Weitergereicht von
  `persist`, `preflight` und `pruefung_fehlt`.
- **MINOR 7, Entscheid: abgespeckt, nicht gesperrt.** `teil_verweise._abgespeckt` gibt
  kuratierenden Werkzeugen `draft` ohne `inhalte` (`strukturentwurf.ohne_inhalte`). Module mit
  `liest: draft` bekommen ihn ganz.
  - Begründung: Schreibwege wie „Sammlungen aus dem Entwurf anlegen“ nehmen `{"$teil": "draft"}`
    und brauchen Titel und Beschreibungen, nicht die Dateinamen. Eine Sperre bräche sie.
- **MINOR 8:** Beim Speichern eines Entwurfs (`arbeitsstand._speichern`, Teil `draft`) setzt
  `strukturentwurf.mit_knoten_ids` die node_ids neu aus `ablage` über `i`, nur wenn
  `gebunden(struktur, ablage)`. Eine vom Client geschickte fällt weg.
- **NIT:**
  - Kopf des Lesers: „Cache nicht gelesen“ statt „ohne Cache“.
  - `volltext` liest nur mit `has_personal_auth()`.
  - Leerzeilen in `typen.py`.
  - `alle_fuer_aufrufer` einmal je Speichern (`_lesbare_zeilen` mit Merker).

### Nachprüfung TG-3d–f (16.11.) — behoben

1 MAJOR, 3 MINOR, 4 NIT. Entscheide des Koordinators, umgesetzt; noch ohne zweite Nachprüfung.
Notiz: `docs/aenderungen/2026-11-16-strukturdokumente-und-ordnerinhalte.md`, Abschnitt
„Nachprüfung“.
- **MAJOR 1, die Blase zitiert die Namen:** `antwort.bekannte_namen_neutral` ersetzt in `frei`
  jedes Zitat („…“ bzw. “…”), dessen Inhalt in `teile.namen` vorkommt, durch „…“, bevor Regex-Gate
  und Rechtsprüfung laufen (in `sicherheits_teile`, gilt in `assess` und `preflight`).
  `namen_pruefung` deckt sie ab: Hinweis ohne Sperre, Teile gespeichert. Ein selbst getipptes
  Zitat, das kein bekannter Name ist, bleibt geprüft. Die Moderation sieht weiter alles (Namen über
  `nur_moderation`).
- **MINOR 2, der Entwurf kennt seine Quelle:**
  - `strukturentwurf_aus_ordnern` schreibt `quelle_block` (die `block_id` der Auswahl) in den
    Entwurf. Manifest Eingabe und Antwort, das Modul gibt es zurück, Vorlage und Merker behalten
    es.
  - `arbeitsstand._entwurf_mit_knoten` setzt node_ids aus `ablage` nur, wenn `struktur` und
    `ablage` gebunden sind und zu `quelle_block` gehören.
  - Sonst nimmt es die node_ids des zuletzt gespeicherten Entwurfs derselben Auswahl
    (`strukturentwurf.knoten_ids_im_entwurf`); vom Client kommen keine.
- **MINOR 3, Dubletten:** Als erneutes Hochladen gilt nur gleicher Aufrufer, gleiche `block_id`,
  gleicher Name, gleiche Größe und gleicher Text (`md5`).
- **MINOR 4:** Zu `volltext_fehlt` passt der Satz zum Grund (`dienst._volltext_satz`):
  - später (der Text entsteht noch);
  - Anmeldung (`ohne_anmeldung`);
  - kein Zugriff bzw. nicht gefunden.

  Der Code bleibt `volltext_fehlt`.
- **NIT 5:** `strukturdokument.text()` ist gestrichen, samt dem Test, der nur sie prüfte.
- **NIT 6:**
  - Ein abgelaufenes oder verdrängtes Sitzungsdokument steht in `fehlend` mit Grund `abgelaufen`
    und Satz an die KI („bitte neu lesen lassen“).
  - Sind nur solche da, ist es „kein Dokument“ (`None`), nicht `volltext_fehlt`.
- **NIT 7:** `preflight` protokolliert den Grund aus den Namen auch, wenn die Moderation fehlt und
  der Zug dort endet (ohne Namen).
- **NIT 8:** Kommentar in `graph/state.py` berichtigt.

### Entscheide zu TG-6 (Hauptsitzung, 16.11.)
- **Direktstart (`agent`, `modus: direkt`) für „Themenbaum erstellen“ angenommen.** Der neue Maßstab
  `werkzeuge.ablauf_schreibt_ungefragt` zählt einen Auftrag mit Rückfrage direkt davor nicht als
  „ungefragt“. Die Person bestätigt vor jedem Schreiben ausdrücklich. TB-E3 bleibt im Sinn
  gewahrt: Kein Ablauf schreibt ohne Freigabe. Der frische Vorgang (N14) hängt weiter an
  `ablauf_schreibt_selbst`.
- **`sammlung_pruefen`:** Das Fehler-Ende `ohne_ordner` bekommt einen Ausweg (Prüfung „stumme
  Enden“). Das ist eine bewusste kleine Abweichung von „unverändert“ (G-E2); der Ablauf ist ab Werk
  aus.

### Review TG-4–6 (16.11.) — behoben

4 MAJOR, 8 MINOR, 6 NIT und 1 Fehler der vollen Suite. Entscheide des Koordinators umgesetzt, die
übrigen selbst getroffen; noch ohne Nachprüfung. Notiz
`docs/aenderungen/2026-11-16-ablauf-themenbaum-erstellen.md`, Abschnitt „Review-Behebung“.
- **0 / Befund 10, Leiste:** `n` aus den Halten des Laufs (`lauf.halte`, `treiber._rechne`, im
  Verweis mitgeführt), `m` = `n` − 1 + die meisten Halte ab hier (`fortschritt._rest`).
  - **Feinentscheid:** Ein Halt ist jede Stelle, an der der Lauf auf die Person wartet (Frage,
    Modul, KI-Schritt, Auftrag, Freigabe, Seite). Die Freigabe zählt, obwohl sie ein
    Werkzeug-Schritt ist — sonst stünde zwischen zwei Anzeigen dieselbe Zahl.
  - **Feinentscheid:** Kein neuer Halt beim erneuten Halt am selben Schritt (`erneut_vorlegen`, Wahl
    auf sich selbst) und an einer Frage, die nur eine andere wiederholt (Führung).
  - **Feinentscheid:** Läufe ohne `halte` (begonnen vor dieser Fassung) und direkte Aufrufe ohne
    Lauf rechnen weiter über den längsten Weg — die bestehenden Leisten-Tests der Führung und des
    Dokument-Ablaufs bleiben; die TG-2-Tests prüfen jetzt den Lauf (`tests/leiste_halte.py`).
  - **Ursache:** nicht das Besuchsbudget (das half nur gegen doppelte Kanten), sondern das Maß
    „längster Weg“ in einem verzweigten Graphen mit Rückwegen.
- **MAJOR 1:** `werkzeuge._ehrlich_gefragt` — eine Wahl mit einer Option, die nicht zum Auftrag
  führt, ohne Freitext dorthin, oder eine Freigabe. Die Prüfung `auftrag_rueckfrage` bleibt, wie sie
  ist.
- **MAJOR 2:** `zug._frisch_noetig` — frisch nur mit `ablage`, `metadatenlauf` oder offenem Lauf im
  Vorgang. **Folge für den Ablauf:** Ein Entwurf aus freier Arbeit kann im Vorgang liegen; darum
  prüft keine Regel `draft`, sondern Teile, die nur der Ablauf schreibt (`ordnerweg`, `metadaten`).
- **MAJOR 3:** Ganze Wörter für Synonyme an Fragen **mit Freitext**, im Treiber
  (`wahl_aus_text`) statt nur im Seed — die Führung (ohne Freitext) bleibt beim Teilwort. „Andere
  Grundlage“ in `ohne_daten` verwirft `grundlage`, `structure`, `document`, `weg`, `metadaten`,
  `ordnerweg`. Der Rückweg zu `grundlage` ist für die Leiste kein Problem mehr (Befund 10).
- **MAJOR 4, Feinentscheid:** **Daten zuerst für alle Grundlagen**, Fragen danach — so stehen die
  Fragen einmal, kurz vor dem Entwurf, und wirken für jede Grundlage. Thema: getippt in der
  Grundlage (NIT 15, keine eigene Frage mehr). „Für wen“ und „Stufe“ sind eine Frage (40 Schritte).
  Ordner: Fragen nur nach „Mit deinen Angaben verfeinern“, dann `entwurf_ordner` mit `vorlage`.
  Soll oder Ist nur bei Dateien (erkannt an `metadaten`).
- **MINOR 8:** `bereit.wlo_erschliessen` = Ablage UND `auftrag_zug.starter()` UND
  `client.erlaubt(node-metadata-write)`; Simulation: die Anmeldung des Testfalls.
- **MINOR 9:** „Anderes wählen“ verwirft nur die Daten. Regeln auf `bereit.art` stehen hinter denen
  auf die Grundlage — nach „Anderes wählen“ steht die Grundlage fest.
- **MINOR 5/6/11, NIT 16/18:** in `vorbelegung` bzw. `inhalte_aus_dateien`; die Verneinung prüft das
  Wort davor (bei „zu“/„so“ das davor).
- **NIT 13, Feinentscheid:** Erschließen der Ordner über das Übertragen im ersten Upload-Feld (dann
  Metadaten vor dem Entwurf), keine eigene Frage nach dem Prüfpunkt — sie bräuchte ein zweites
  Auswählen der Dateien und zwei Schritte mehr.
- **Offen:** Erschließen schon bereitgestellter Ordner („Ja, verwenden“) geht nur über einen neuen
  Ablauf mit Übertragen; das Befüllen der Sammlungen kommt mit den späteren Abläufen.

### Zweites Review TG-4–6 (16.11.) — behoben

2 MAJOR, 5 MINOR, 3 NIT (A–I), Entscheide des Koordinators umgesetzt. Notiz
`docs/aenderungen/2026-11-16-ablauf-themenbaum-erstellen.md`, Abschnitt „Zweites Review“.
- **A:** `treiber._mit_freitext` — mit Freitext nur der ganze Text (ohne Satzzeichen am Rand);
  `Schritt.synonyme_im_satz` (Vorgabe `None`, `False` → `None`, damit die Fassung gleich bleibt).
  - **Feinentscheid:** Verneinung = eines der zwei Wörter davor ist „kein…/nicht/ohne/no/not/
    without“; mehrere Optionen getroffen → `None` (Freitext, hier: das Thema).
- **B:** `fortschritt._ohne_rueckkanten` — Kanten j→k mit k ≤ j, von denen aus j wieder erreichbar
  ist, nur für Wahlschritte und nicht für den Schritt, an dem der Lauf hält.
  - **Feinentscheid:** Der Test „m steigt nie“ gilt für reguläre Wege (kein Schritt doppelt, kein
    `ohne_…`/`bei_fehler`-Ziel); nach einem Fehlerschritt darf `m` neu rechnen.
- **C:** `werkzeuge._ohne_auftrag_zum_ende` (Suche über alle Kanten, auch `bei_fehler`).
- **D/E/G/H/I:** im Seed bzw. in `vorbelegung` (`_getippte_grundlage` vergleicht mit den deutschen
  Labels der Frage, die `grundlage` schreibt). H über `vergleich.wert_quelle`; `typen.gelesene_teile`
  zählt den Teil im Wert mit.
- **F:** `werkzeuge.frisch_noetig` als eine Stelle für `zug` und `vorschlag.direkt_knopf`
  (Verweis aus der Sitzung, `turn_assembly`).

### Nachprüfung TG-4–6 (16.11.) — behoben

1 MAJOR, 5 MINOR, 2 NIT, Entscheide des Koordinators umgesetzt. Notiz
`docs/aenderungen/2026-11-16-ablauf-themenbaum-erstellen.md`, Abschnitt „Nachprüfung“.
- **MAJOR 1:** Freitext nur bei `grundlage`, `wofuer`, `stufe`, `umfang`, `hinweise`; alle übrigen
  Fragen des Seeds mit `kein_treffer` (de/en) und ohne Synonyme.
  - **Feinentscheid:** auch `umfang` behält Freitext („nur grob“ wertet die Vorbelegung aus);
    `soll_ist` verliert ihn (Entweder-oder).
  - **Feinentscheid:** Die Simulation kennt den Hinweis jetzt (`simulation._nur_hinweis`): der Lauf
    wartet, die nächste Eingabe gilt demselben Schritt — ohne Freitext einmal je Besuch wie im
    Betrieb, ein mehrdeutiger Satz jedes Mal.
- **MINOR 2:** `treiber._im_satz` — Satzteil bis `,;.!?`, zwei Wörter davor, eins dahinter.
  - **Feinentscheid:** „nicht nur X“ bejaht X (`_NUR`); nennt der Satz noch eine Option, ist er
    mehrdeutig.
- **MINOR 3:** `treiber.mehrdeutig`; `wahl_gilt` lehnt den Satz als Freitext ab, `wahl_zug.getippt`
  zeigt den Hinweis jedes Mal (ohne Marke). Die Prüfung erlaubt `kein_treffer` neben Freitext nur
  mit `synonyme_im_satz`.
- **MINOR 4:** `werkzeuge._ehrlich_gefragt` — eine Option zum Auftrag mit Synonymen ist keine
  Zustimmung; Befund `auftrag_synonym` für Optionen mit Synonymen, die direkt zu einem Auftrag mit
  `repo_schreibt` führen.
- **MINOR 5:** `pruefung._stelle` für Quelle und Wert; Befund `wert_stelle` bei `{teil.` mit
  falscher Form; `wert_zahl` nicht für eine Stelle. Studio `stelleImWert`, Fehler `wertForm`.
- **MINOR 6 / NIT 7 / NIT 8:** Leisten-Test (erster Halt ist kein Fehlerweg), Name „m steigt nie“;
  Ganztext-Vergleich ohne Satzzeichen (`treiber._ganz`) und Synonyme „nein danke“, „no thanks“.

### Durchtest TG-7 (16.11.) — behoben

Protokoll `docs/aenderungen/2026-11-16-durchtest-themenbaum.md`, Abschnitt „Behebung“. 2 MAJOR,
5 MINOR, 3 NIT; Entscheide des Koordinators umgesetzt.
- **M1:** (a) Steuerchip „Weiter im Ablauf“ unabhängig vom Schnellantwort-Modus; (b)
  `ki_schritt.uebernimmt` + `zug.nach_uebernahme` (Preflight-Auslöser `uebernahme`); (c) Hinweise.
  - **Feinentscheid:** Die Regel ist allgemein: Ein Modul des Schritts, das genau dessen `ausgabe`
    schreibt und `uebernommen: true` trägt — heute nur `ui_strukturentwurf` mit `draft`.
- **M2:** `dokument_lesen` wie `wissen_suchen` (virtuell, Rückruf in `run_agent_loop`, in
  `ki_schritt._VIRTUELL`).
  - **Feinentscheid:** nur in der Agent-Schleife; im Muster-Weg sagt der Rahmen ehrlich, dass die KI
    den Text dort nicht lesen kann (offene-befunde §1).
  - **Feinentscheid:** Überschriften ohne erneute Moderation (die sah die Moderation beim Hochladen),
    Abschnittstext immer; Stufe `dokument_lesen`.
- **m1/m2:** `vorbelegung._thema_aus_daten`; der Vorlagen-Zweig nimmt Stufe, Fach und ein fehlendes
  Thema aus dem Auftrag.
- **m3:** `volltext_fehlt_datei` für `not_extracted` (Sammelsatz; das MCP unterscheidet nicht).
- **m4, Feinentscheid:** Soll/Ist in `zum_entwurf` statt nach der Stufe — so passt die neue Frage
  `soll_wenig` in 40 Schritte (`nach_stufe` entfiel). Zahl aus `metadaten.inhalte.4` (vorhanden ⇔
  mindestens 5). „Andere Grundlage“ verwirft auch `soll_ist`. Die Antworten führen direkt zu
  `entwurf_inhalte` — ein Kreis über `zum_entwurf` hob in der Leiste `m` um eins.
- **m5:** `client.BEKANNTE_CODES`; `auftrag_zug._Starter.hinweis`, vom Treiber vor den Text des
  Ersatzwegs gestellt.
- **NIT:** Fundstelle (n1), `quelle: ki` aus Dateien (n3); n2 ohne Änderung (nur Markdown-Senken).
- **Review-Befunde behoben (16.11.):** kein Steuerchip im Krisen- bzw. Drohungszug (`ki_schritt.vorgegeben`, `safety` an `turn_assembly`); Steuerchip hinten, Chips des Gastgebers ungekürzt; `nach_uebernahme` prüft den Schritt; `dokument_lesen` rahmt auch die Gliederung, entschärft die Namen (`rahmen.name_fuer_ki`, auch für `dienst._namen`), merkt sich Antworten je Abschnitt und liest höchstens 6-mal je Zug; ein leerer Entwurf ist keine Übernahme; Seed-Kommentar zur Zählung.
