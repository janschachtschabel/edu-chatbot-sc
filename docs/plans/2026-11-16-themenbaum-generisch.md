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
- **TG-2 Upload zielneutral (Backend)** — G-E4, G-E5:
  - `upload_antwort` mit neutralen Rahmen;
  - `nicht_gelesen_satz` neutral;
  - `ordner_aktion` nimmt alte Antworten wie `erfasst`;
  - der Vorgang trägt den Zweck `bereitstellen`;
  - der Modul-Auslöser in `themenbaum_aus_dokument` entfällt;
  - Master-Skill-Absatz;
  - Tests.
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
