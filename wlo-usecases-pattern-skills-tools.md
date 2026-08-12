# WLO KI-Integration — Use-Cases, Pattern, Skills und MCP-Tools

**Zweck:** Entwickler:innen sollen einschätzen können, welche Use-Cases es gibt, was jeder davon an Chatbot-Pattern, Skills, Wissensquellen und MCP-Tools braucht, was davon existiert und was neu angelegt werden muss.

**Geltungsbereich:** WLO-Chatbot, GPT-Store bzw. User-LLM über MCP, Browser-Plugin. Alle drei Kanäle nutzen denselben MCP-Server. Das RAG steht nur dem Chatbot zur Verfügung.

**Stand:** August 2026 · Grundlage: MCP-Werkzeugkatalog (38 Tools), Pattern-Seed `backend/seeds/03-patterns/` (17 Pattern), Flow-Boards Sommercamp, Skill-Host-Konzept.

**Drei Kernaussagen**

1. Pattern beschreiben **Vorhaben**, nicht Gesprächszustände. Slot-Rückfragen, Bestätigungen, Revisionen und Bezugnahmen sind Engine-Mechaniken; das unterbrochene Pattern bleibt Eigentümer.
2. Jedes Pattern deklariert seine **Wissensquellen** mit Vorrang. Es wird nie über alle Quellen gefächert.
3. Der Soll-Ist-Abgleich steht gebündelt in Abschnitt 11.

---

## Legende

| Zeichen | Bedeutung |
|---|---|
| `C` | Kanal WLO-Chatbot |
| `G` | Kanal GPT-Store / User-LLM über MCP |
| `P` | Kanal Browser-Plugin |
| ✓ | vorhanden und nutzbar |
| ~ | vorhanden, aber eingeschränkt, leer oder unverifiziert |
| ✗ | fehlt |

IDs: `S-*` Schutz · `B-*` Bot, Plattform und Organisation · `P-*` fachliches Vorhaben · `E*` Engine-Mechanik · `Q*` Wissensquelle. `M01`–`M17` sind die IDs im heutigen Seed.

---

## 1. Bausteine

| Baustein | Was er leistet | Stand |
|---|---|---|
| MCP-Server | Zugriff auf die Repository-API, 25 lesende und 13 kuratierende Werkzeuge | ✓ |
| Chatbot-Pattern | Muster für Gesprächsführung, Auswahl über `priority` und `when_to_use` | ✓ 17 im Seed |
| Engine-Mechaniken | Slot-Register, Frame, Bezugsauflösung, Revision, Bestätigung, Quellen-Routing | ✗ |
| Chatbot-RAG | Wissensantworten ohne Suche | ~ vorhanden, ungefüllt, unsegmentiert |
| Skills | fachliche Regeln als SKILL.md, je Scope in einer Registry gebündelt | kein belastbarer Ist-Stand |
| Web-Widgets | Karte, Karussell, Vollansicht für Trefferdarstellung | ✓ 3 Komponenten |
| Wissensbasis | Kompendialtexte, Lehrpläne, Themenseiten, Volltexte, Q&A, Musterdaten | ~ überwiegend leer |

**Harte Grenze:** Skills können keine eigenen APIs aufrufen. Alles, was ein Skill an Daten braucht, muss vorher als MCP-Tool existieren.

---

## 2. Wissensquellen

Zwei Familien mit unterschiedlichem Zugriffsweg. Die Unterscheidung entscheidet, welche Abfragen ein Zug überhaupt auslöst.

| ID | Quelle | Weg | Inhalt | Stand |
|---|---|---|---|---|
| Q1 | Webseite und Prozesse | RAG | Bedienung, Abläufe, Einreichungsweg, Selbstdarstellung | ✗ Korpus fehlt |
| Q2 | Projekte | RAG | WLO-Projekte, Vorhaben, Zeiträume | ✗ Korpus fehlt |
| Q3 | Partner | RAG | Beteiligte, Rollen, Zuständigkeiten | ✗ Korpus fehlt |
| Q4 | OER-Wissen | RAG | OER-Konzepte, Lizenzen, allgemeine Didaktik | ✗ Korpus fehlt |
| Q5 | Inhalte und Metadaten | MCP | Materialien, Metadaten, Volltexte | ✓ |
| Q6 | Sammlungen und Themenbaum | MCP | Sammlungen, Struktur, Statistik | ✓ |
| Q7 | Themenseiten | MCP | Layout, Schwimmlinien, Zielgruppen-Varianten | ~ Tools ✓, Bestand ✗ |
| Q8 | Kompendiale Texte | MCP | Kap. 1 Fachinhalt, Kap. 2 Lehrplan, Kap. 3 Sammlungszustand | ~ Tool ✓, Bestand ✗ |
| Q9 | Skills und Registries | MCP | SKILL.md, Musterdaten, Registry | ~ Tool ✓, Sammlung ✗ |
| Q10 | Wikipedia | MCP | Begriffsklärung | ✓ |
| Q11 | Web und Crawler | MCP | offene Quellen | ✗ |

### 2.1 Vorrangregeln

| Frage | Reihenfolge | Begründung |
|---|---|---|
| Fachlich zum Thema | Q8 Kap. 1 → Q4 → Q10 | der kuratierte Kompendialtext hat Vorrang vor allgemeinem Wissen |
| Lehrplanbezug | Q8 Kap. 2 → Q4 | Lehrplandaten gibt es nur kuratiert |
| Zustand einer Sammlung | Q8 Kap. 3 → Q6 | Soll aus dem Text, Ist aus dem Bestand |
| Materialbedarf | Q5 → Q6 → Q7 | nie RAG — das RAG kennt den Bestand nicht |
| Plattform und Organisation | Q1 → Q2 → Q3 | nie MCP, außer beim Skill-Katalog (Q9) |
| Bewertungsregeln | Q9 → Q4 | Skill schlägt allgemeines Wissen |

### 2.2 Wirkung

- **Keine Fächerung.** `P-SUCHEN` fragt das RAG nie ab, `B-PLATTFORM` fragt das Repositorium nur für den Skill-Katalog ab.
- **Weniger Aufrufe.** `P-WISSEN` erreicht mit Vorrangkette maximal zwei Quellen statt fünf.
- **Herkunft wird belegbar.** Jede Antwort trägt ihre Quelle — Voraussetzung für `B-FEEDBACK` und für die Fehlerrückverfolgung in kompendialen Texten.
- **Risiko:** eine falsche Quellenzuordnung erzeugt selbstbewusst falsche Antworten („was ist OER" aus einem Physik-Kompendium). Deshalb braucht E8 ein Ausreichend-Kriterium, nicht nur einen Treffer.

### 2.3 Neu erkannte Anforderung an das RAG

Das RAG ist heute ein undifferenzierter Speicher. Für Quellen-Routing muss es **nach Korpus segmentiert** und gefiltert abfragbar sein (Q1–Q4 als getrennte Räume mit Korpus-Label). Ohne diese Segmentierung ist Abschnitt 2.1 nicht implementierbar.

---

## 3. Engine-Mechaniken

Acht Mechaniken, **keine Pattern**. Sie stehen nicht in der `priority`-Liste und konkurrieren nicht um Vorfahrt.

| ID | Mechanik | Was sie tut | Ersetzt |
|---|---|---|---|
| E1 | Slot-Register | hält je Pattern-Eigentümer die aufgelösten Slots über das Gespräch hinweg | — |
| E2 | Frame | markiert einen unterbrochenen Vorgang: Eigentümer, Slots, fehlender Slot, Versuchszähler, Frist. Maximal einer offen | — |
| E3 | Slot-Nachfrage | rendert die Rückfrage in fester Form: genau eine Frage, drei konkrete Quick-Replies. Inhalt liefert der Eigentümer | **M03** |
| E4 | Bezugsauflösung | löst Ordinalzahlen und Deixis gegen die letzte Trefferliste auf | — |
| E5 | Revision | ein Folgezug ändert einen **gefüllten** Slot des letzten Eigentümers → Eigentümer erneut aufrufen, Ausgabe vollständig neu rendern | **M11** |
| E6 | Bestätigung | ein `confirmToken` steht aus → einlösen, Frist prüfen, Feldbericht, zurück zum Eigentümer | — |
| E7 | Leerergebnis und Degradation | Abfrage kam leer zurück → `rescue` bzw. `degrade` **des Eigentümers** ausführen | **M12** |
| E8 | Quellen-Routing und Herkunftsnachweis | führt die `sources`-Kette des Eigentümers in Vorrangfolge aus, prüft Ausreichend-Kriterium, bricht beim ersten tragfähigen Treffer ab, vermerkt die Herkunft | — |

### 3.1 Warum es kein Slot-Klärungs-Pattern gibt

Ein Sprung zu einem Slot-Pattern verliert den Kontext des Vorhabens. Ein Verbleiben ohne Zustand macht den Gesprächsstand unsichtbar. Der Frame löst beides.

```
frame = {
  owner:     "P-SUCHEN",
  slots:     { fach: "Mathematik", thema: null, stufe: null },
  missing:   "thema",
  utterance: "ich will einen inhalt für mathe",
  attempts:  1,
  expiresIn: 3
}
```

Im UI als Chip darstellbar: „Suche · Mathematik · Thema fehlt". Im Log als eine Zeile.

**Slot füllen und Slot ändern sind dieselbe Operation.** Deshalb fällt M11 weg: „mach es kürzer" ändert den Slot `umfang` beim letzten Eigentümer. Damit verschwindet zugleich die Unterscheidung zwischen Umformulieren einer Antwort und Neurendern eines Artefakts — der Eigentümer weiß selbst, welche Ausgabeform er hat.

### 3.2 Zugtypen

| Typ | Mechanik | Verhalten am Frame |
|---|---|---|
| Anreichern und durchlassen | E4 | fügt nodeIds zum Kontext, unterbricht nicht |
| Binden und fortsetzen | E3, E6 | Slot bzw. Token einlösen, Eigentümer setzt fort, kein Routing |
| Ändern und fortsetzen | E5 | gefüllten Slot ersetzen, Eigentümer erneut aufrufen |
| Eigener Zug, Frame überdauert | `B-*` | antwortet, Frame bleibt offen |
| Harter Abbruch | `S-*` | Frame wird verworfen |

### 3.3 Schutzregeln gegen die Frame-Falle

| Regel | Wert | Begründung |
|---|---|---|
| Kein Nesting | max. 1 offener Frame | ein neuer Frame verwirft den alten |
| Frist | 3 Züge | danach nicht mehr bindend |
| Versuchsgrenze | max. 2 | danach mit dem Vorhandenen breit suchen oder an `B-ORIENTIERUNG` abgeben |
| Ausstieg immer möglich | jederzeit | Themenwechsel führt ohne Nachfrage aus dem Frame heraus |
| Frame ist sichtbar | UI und Log | der Nutzer muss den wartenden Vorgang erkennen und verwerfen können |

### 3.4 Pattern-Vertrag

| Feld | Inhalt |
|---|---|
| `slots` | Pflicht- und Optionalfelder, je mit Vokabularquelle |
| `sources` | erlaubte Wissensquellen in Vorrangfolge, mit Ausreichend-Kriterium |
| `quick_replies` | wie Vorschläge je fehlendem Slot erzeugt werden |
| `revisable` | welche Slots nachträglich geändert werden dürfen |
| `rescue` | Leiter bei Leerergebnis |
| `degrade` | Satz bei fehlendem Skill oder fehlendem Bestand |
| `owns` | welcher Kontext für Folgezüge gehalten wird |
| `hands_off` | welche Folgeabsichten das Pattern verlassen |
| `when_to_use` / `when_not_to_use` | Auswahlkriterien |

---

## 4. Laufzeitkette

| Schritt | Was passiert |
|---|---|
| 1 Eingabe | Äußerung plus Zustand: Slot-Register, letzte Trefferliste, letzte Ausgabe, offener Frame |
| 2 Schutz | `S-KRISE`, `S-BEDROHUNG` greifen unbedingt und brechen ab |
| 3 Bezugsauflösung (E4) | Ordinalzahlen und Deixis → nodeIds im Kontext |
| 4 Frame-Auflösung (E2, E3, E5, E6) | Slot-Antwort, Slot-Änderung oder Bestätigung? → Eigentümer fortsetzen, weiter bei 6 |
| 5 Pattern-Auswahl | Gegenstandsleiter, dann `priority`. Neuer Eigentümer, alter Frame verworfen |
| 6 Slot-Prüfung | das Pattern prüft seine Pflichtslots. Fehlt einer: Frame anlegen, E3-Nachfrage, Zug endet |
| 7 Quellen-Routing (E8) | `sources` in Vorrangfolge, Abbruch beim ersten tragfähigen Treffer, Herkunft vermerken. Leer → `rescue` (E7) |
| 8 Skill-Laden | falls Scope vorhanden: Registry lesen, Bündel laden. Leer → `degrade` (E7) |
| 9 Ausgabe | Rendering je Pattern, Slot-Register und Trefferliste fortschreiben |

**Zwei entscheidende Reihenfolgen:** Auswahl **vor** Slot-Prüfung — das löst das Slot-Pattern auf. Und Quellen-Routing **nach** der Auswahl — dadurch ist die Quellenmenge schon eingegrenzt, bevor die erste Abfrage läuft.

### 4.1 Gegenstandsleiter für Schritt 5

1. **Gegenstand?** Bot, Plattform oder Organisation → `B-*`. Ein Langtext an einem Knoten → `P-TEXTKOERPER`. Der Nutzer selbst → `P-UEBEN`. Ein Repo-Objekt → Frage 2. Kein Gegenstand → `P-WISSEN`, `P-SUCHEN` oder `B-ORIENTIERUNG`.
2. **Soll sich der Bestand ändern?** Metadaten oder Struktur → `P-KURATIEREN`. Langtext → `P-TEXTKOERPER`.
3. **nodeId im Kontext?** Anzeigewunsch → `P-VERTIEFEN`. Bewertungsauftrag → `P-BEWERTEN`. Abwandlungswunsch → `P-ADAPTIEREN`. Keine nodeId und Materialbedarf → `P-SUCHEN`. Keine nodeId und Artefaktwunsch → `P-ERZEUGEN`.

### 4.2 Beispielverlauf

| Zug | Eingabe | Greift | Quellen | Ausgabe |
|---|---|---|---|---|
| 1 | „ich will einen Inhalt für Mathe" | `P-SUCHEN`, dann E2/E3 | — | eine Frage plus 3 Quick-Replies, Frame offen |
| 2 | „Bruchrechnen, Klasse 6" | E3 bindet → `P-SUCHEN` setzt fort | Q5 | Trefferkarten |
| 3 | „was heißt eigentlich CC BY?" | `P-WISSEN`, E8 | Q4 (nicht Q8, kein Fachthema) | Definition mit Herkunftsangabe, Frame bleibt |
| 4 | „nimm Nummer 2 und 3" | E4 | Q5 | Auswahl bestätigt, kein Pattern-Wechsel |
| 5 | „zeig mir den Volltext vom ersten" | E4, dann `P-VERTIEFEN` | Q5 | Dokument-Box, Quelle benannt |
| 6 | „mach daraus ein Arbeitsblatt, Niveau B" | `P-ADAPTIEREN` | Q5, Q9 (`didaktik`, `lizenz`) | Artefakt mit Quell- und Lizenzvermerk |
| 7 | „mach es kürzer" | E5 auf Slot `umfang` | — | Artefakt neu gerendert, kein Pattern-Wechsel |
| 8 | „speichere das in WLO" | `P-KURATIEREN`, dann E2/E3 | Q6 für Ablageortvorschläge | Nachfrage mit Sammlungsvorschlägen |
| 9 | „in die Sammlung Bruchrechnen" | E3 bindet → fortsetzen | Q9 (`kuration`) | Vorschau plus `confirmToken` |
| 10 | „ja" | E6 | — | Feldbericht, was wirklich ankam |
| 11 | „such mir noch mehr dazu" | E5 auf `P-SUCHEN` aus dem Register | Q5 | weitere Treffer, Filter aus Zug 2 erhalten |

Zug 3 zeigt die Quellenwirkung: eine Lizenzfrage mitten in einer Materialsuche geht an Q4 und löst **keine** Repository-Abfrage aus. Zug 11 zeigt das Slot-Register: die Suchparameter aus Zug 2 überleben acht fremde Züge.

---

## 5. Pattern

16 Pattern auf drei Ebenen. Fett = neu anzulegen.

### 5.1 Schutz

| ID | Prio | Auslöser | Quellen | Seed |
|---|---|---|---|---|
| S-KRISE | 999 | akute psychische Not, Selbstgefährdung | — | M01 ✓ |
| S-BEDROHUNG | 998 | Drohung, Hassrede, Aufforderung zu Illegalem | — | M02 ✓ |

### 5.2 Bot, Plattform und Organisation

| ID | Prio | Nutzerabsicht | Quellen | Scope | Seed |
|---|---|---|---|---|---|
| **B-OFFTOPIC** | 620 | harmlos außerhalb Bildung: „schreib ein Gedicht", „wie wird das Wetter" | — | — | ✗ |
| **B-TRANSPARENZ** | 610 | „welche KI bist du", „was passiert mit meinen Daten", „was kostet das" | Konfiguration | — | ✗ |
| B-FEEDBACK | 600 | „deine Antwort war falsch", „woher hast du das", Fehlermeldung | E8-Protokoll, Q8, Q&A | — | M13 teils, M14 ✓ |
| **B-PLATTFORM** | 590 | „wie lade ich Material hoch", „welche Projekte gibt es", „wer sind eure Partner", „welche Skills gibt es" | Q1 → Q2 → Q3, Skill-Katalog Q9 | `plattform` | ✗ |
| B-ORIENTIERUNG | 460 | „was kann ich hier machen" — Erstkontakt ohne Thema | Q1 | — | M15 ✓ |

`B-PLATTFORM` deckt Bedienung, Projekte, Partner, Selbstdarstellung und Skill-Katalog ab. Gemeinsamer Gegenstand: die Organisation und ihre Plattform. Gemeinsamer Ausgabevertrag: Auskunft mit Absprunglink, keine Materialsuche, keine Ausführung.

### 5.3 Fachliche Vorhaben

| ID | Prio | Gegenstand und Absicht | Quellen | Scope | Seed |
|---|---|---|---|---|---|
| **P-TEXTKOERPER** | 588 | ein Langtext an einem Knoten soll entstehen oder sich ändern: Kompendialtext Kap. 1–3, Volltext, Q&A, SKILL.md | Q8, Q5, Q9 | `redaktion`, bei SKILL.md `skill` | ✗ |
| **P-KURATIEREN** | 584 | Metadaten oder Struktur ändern: anlegen, Felder ändern, Sammlung anlegen, Verweise setzen, einreichen, löschen, Vorschlag entscheiden | Q5, Q6 | `kuration`, `lizenz` | ✗ |
| **P-BEWERTEN** | 570 | ein benanntes Repo-Objekt bewerten: prüfen, Füllstand, Abdeckung, Kennzahlen | Q8 → Q6 → Q5, Q9, optional Q10/Q11 | `qs` | ✗ |
| **P-UEBEN** | 555 | der Nutzer selbst soll geprüft werden: „frag mich ab" | Q8 Kap. 2, Q5 | `pruefung` | ✗ |
| **P-ADAPTIEREN** | 545 | ein **benanntes** Material abwandeln: differenzieren, kürzen, umschreiben, auf Landesdesign bringen, remixen | Q5 Volltext, Q9 | `didaktik`, `lizenz` | ✗ |
| P-ERZEUGEN | 530 | neues Artefakt aus Bedarf, ohne einzelne Ausgangsquelle: Arbeitsblatt, Quiz, Stunde, Reihe, Lernpfad, Bewertungsraster | Q5, Q8, Q9 | `didaktik` | M09 ✓, M10 ✓ |
| P-WISSEN | 520 | Frage ohne Objektbezug und ohne Materialwunsch — fachlich, lehrplanbezogen oder OER-Domäne | Q8 Kap. 1/2 → Q4 → Q10 | `lehrplan` | M04 ✓ |
| P-VERTIEFEN | 510 | nodeId liegt vor, Anzeigewunsch: Volltext, Schwimmlinien, Sammlungsinhalte, Verortung, Ähnliches | Q5, Q6, Q7 | — | M08 ✓, M16 ✓, M17 ✓ |
| P-SUCHEN | 500 | Bedarf nach Treffern | Q5 → Q6 → Q7 | — | M05 ✓, M06 ✓, M07 ✓ |

### 5.4 Pattern × Quelle

| Pattern | Q1–Q3 Webseite, Projekte, Partner | Q4 OER-Wissen | Q5–Q7 Bestand | Q8 Kompendium | Q9 Skills | Q10/Q11 extern |
|---|---|---|---|---|---|---|
| B-PLATTFORM | ● | ○ | — | — | ○ Katalog | — |
| B-FEEDBACK | — | — | — | ○ | — | — |
| P-SUCHEN | — | — | ● | — | — | — |
| P-VERTIEFEN | — | — | ● | ○ | — | — |
| P-WISSEN | — | ● | — | ● | — | ○ |
| P-ERZEUGEN | — | ○ | ● | ○ | ● | — |
| P-ADAPTIEREN | — | — | ● | ○ | ● | — |
| P-BEWERTEN | — | ○ | ● | ● | ● | ○ |
| P-UEBEN | — | — | ● | ● | ● | — |
| P-KURATIEREN | — | — | ● | — | ● | — |
| P-TEXTKOERPER | — | ○ | ● | ● | ● | ○ |

● Hauptquelle · ○ nachgeordnet oder optional · — nie abfragen

Sieben der neun fachlichen Pattern fragen das RAG **nie** ab. Nur `P-WISSEN` und indirekt `P-ERZEUGEN`, `P-BEWERTEN`, `P-TEXTKOERPER` greifen auf Q4 zurück, und dort immer nachgeordnet.

### 5.5 Kontext-Eigentum

| Pattern | Hält | Folgezug bleibt | Folgezug verlässt |
|---|---|---|---|
| P-SUCHEN | Suchslots, Trefferliste | Filter ändern, mehr Treffer, andere Ansicht | nodeId-Anzeige → P-VERTIEFEN |
| P-VERTIEFEN | aktuelles Objekt, Darstellungsart | anderes Detail zum Objekt, Verortung, Ähnliches | Urteil → P-BEWERTEN · Abwandlung → P-ADAPTIEREN |
| P-WISSEN | Themenkontext, genutzte Quelle | Nachfrage zum Thema, andere Ausführlichkeit | Materialbedarf → P-SUCHEN |
| P-ERZEUGEN | Artefakt, Erzeugungsslots | Umfang, Sprache, Artefakttyp, Niveau ändern | Ablage → P-KURATIEREN |
| P-ADAPTIEREN | Quell-nodeId, Zielform, Lizenzkette, Artefakt | Zielform, Niveau, Design ändern | Ablage → P-KURATIEREN |
| P-BEWERTEN | Gegenstand, gelaufene Skills, Befunde | Detail zu einem Befund, weitere Prüfaspekte | Lücke schließen → P-SUCHEN oder P-KURATIEREN |
| P-UEBEN | Fragefolge, Antworten, Stand, Abbruchpunkt | nächste Frage, Wiederholung, Abbruch | Material zum Thema → P-SUCHEN |
| P-KURATIEREN | Vorgang, Gegenstand, Feldwerte, `confirmToken` | Felder korrigieren, Ablageort wechseln, bestätigen | — |
| P-TEXTKOERPER | nodeId, Abschnitt, Prüfstatus, Entwurf | anderen Abschnitt, Text ändern, Status setzen | Bot testen → B-FEEDBACK |
| B-PLATTFORM | genutzter Korpus, letzter Absprunglink | Nachfrage im selben Korpus | Ausführungsauftrag → P-KURATIEREN |

### 5.6 Slot-Schemata

| Pattern | Pflicht | Optional (revidierbar) | Quelle für Quick-Replies |
|---|---|---|---|
| P-SUCHEN | `thema` | `fach`, `stufe`, `typ`, `niveau`, `lizenz`, `suchraum` | `lookup_wlo_vocabulary`, `get_subject_portals` |
| P-VERTIEFEN | `nodeId` | `darstellung` | Objekttyp aus `get_node_details` |
| P-WISSEN | `frage` | `wissensart`, `stufe`, `land`, `ausführlichkeit` | `lookup_wlo_vocabulary` |
| P-ERZEUGEN | `artefakttyp`, `thema` | `stufe`, `niveau`, `umfang`, `sprache` | Registry `didaktik` |
| P-ADAPTIEREN | `quell-nodeId`, `zielform` | `niveau`, `design`, `umfang`, `sprache` | Registry `didaktik` |
| P-BEWERTEN | `gegenstand` | `prüfaspekte` | Registry `qs` |
| P-UEBEN | `thema`, `stufe` | `fragetyp`, `umfang` | Registry `pruefung` |
| P-KURATIEREN | `vorgang`, `gegenstand`, bei Neuanlage `ablageort` | `felder` | `browse_collection_tree`, `lookup_wlo_vocabulary` |
| P-TEXTKOERPER | `nodeId`, `abschnitt` | `operation` | Registry `redaktion` |
| B-PLATTFORM | `anliegen` | `korpus` | Registry `plattform` |

`wissensart` bei `P-WISSEN` steuert die Vorrangkette: fachlich → Q8 Kap. 1, lehrplanbezogen → Q8 Kap. 2, OER-Domäne → Q4. Ist der Slot leer, entscheidet E8 über Themenabgleich und fällt auf Q4 zurück.

### 5.7 Trennschärfe

| Grenze | Regel |
|---|---|
| P-ADAPTIEREN gegen P-ERZEUGEN | Ableitung eines **benannten** Materials (Lizenz und Quelle wirken fort) gegen neues Artefakt, für das Material nur eine Quelle unter mehreren ist |
| P-KURATIEREN gegen P-TEXTKOERPER | Feld im Metadatenschema gegen Langtext-Property (Kompendialtext, Volltext, Q&A, SKILL.md) |
| B-PLATTFORM gegen P-KURATIEREN | **Wie-Frage** über einen Vorgang gegen **Ausführungsauftrag** mit Ziel. „Wie melde ich Material an" gegen „melde das an" |
| B-PLATTFORM gegen P-WISSEN | Gegenstand ist die Organisation oder ihre Plattform (Q1–Q3) gegen Gegenstand ist ein Fach- oder Domänenthema (Q8, Q4) |
| P-BEWERTEN gegen P-WISSEN | P-BEWERTEN braucht ein benanntes Repo-Objekt. Ohne Objekt ist es eine Wissensfrage |
| P-BEWERTEN gegen P-VERTIEFEN | Urteil gegen Anzeige. „prüf die Sammlung Optik" gegen „zeig mir die Sammlung Optik" |
| P-SUCHEN gegen P-WISSEN | Treffer aus dem Bestand gegen Auskunft. Nie beides in einem Zug |
| B-FEEDBACK gegen E5 | Anderes Ergebnis gewünscht → E5 beim Eigentümer. Qualität des Bots oder Herkunftsfrage → B-FEEDBACK |

### 5.8 Was aus den 17 Seed-Pattern wird

| Bleibt | Wird zusammengeführt | Wird Engine-Mechanik | Wird Skill |
|---|---|---|---|
| M01→S-KRISE, M02→S-BEDROHUNG, M15→B-ORIENTIERUNG, M04→P-WISSEN | M05+M06+M07→P-SUCHEN · M08+M16+M17→P-VERTIEFEN · M09+M10→P-ERZEUGEN · M13+M14→B-FEEDBACK | M03→E3 · M11→E5 · M12→E7 | M09 Lernpfad als Skill in `didaktik` |

**Zwei Faltungen als Ermessensentscheidung:** Der Skill-Katalog liegt bei `B-PLATTFORM`, weil er Plattform-Selbstbeschreibung ist. Skill-Bearbeitung liegt bei `P-TEXTKOERPER`, weil eine SKILL.md ein Langtext an einem Knoten ist — mit verpflichtendem Review-Gate im Scope `skill`. Falls dieses Gate einen eigenen Ablauf braucht, ist `P-TEXTKOERPER` später zu splitten.

---

## 6. Skill-Scopes

Je Scope eine Skill-Sammlung mit Master-Skill als Registry. Ohne Registry weiß ein Pattern nicht, was es laden darf. **Für Skills liegt kein belastbarer Ist-Stand vor — alle Scopes sind als neu anzulegen zu planen.**

| Scope | Pattern | Skills |
|---|---|---|
| `plattform` | B-PLATTFORM | WLO-Prozesse, Registrierung und Rechte, Einreichungs- und Prüfweg, Sammlungen und Workspace, Suche und Filter, Skill-Katalog, FAQ zu schulischen Prozessen |
| `redaktion` | P-TEXTKOERPER | Aufbau des Kompendialtextes und seiner Facetten, Kapitelkonventionen, Q&A-Konventionen, Volltextregeln, Prüfstatus-Kriterien |
| `skill` | P-TEXTKOERPER (SKILL.md) | Skill-Konventionen und Aufbau, Review-Kriterien, Sicherheitsprüfung, Versionierung |
| `kuration` | P-KURATIEREN | Erschließungsregeln, Pflichtfelder je Inhaltstyp, Vokabular-Zuordnung, Sammlungs-Konventionen, Dublettenkriterien, Lösch-Policy |
| `lizenz` | P-KURATIEREN, P-ADAPTIEREN | TULLU-Regeln, Weiterverwendung und Bearbeitung, Attribution bei Ableitungen, Quellenangabe |
| `qs` | P-BEWERTEN | Sachrichtigkeit, Neutralität, didaktische Qualität, Barrierefreiheit, Metadaten-Qualität, Design-Konformität Land und Schule, Füllstand einer Sammlung, Lehrplan-Abdeckung, Kennzahlen-Deutung, edu-check-Kategorien |
| `pruefung` | P-UEBEN | Fragetypen, Bewertungsmaßstäbe, Feedbackregeln, Prüfungsformate je Bildungsgang |
| `didaktik` | P-ERZEUGEN, P-ADAPTIEREN | Stunde planen, Unterrichtsreihe, Arbeitsblatt, Aufgaben und Übungen, Binnendifferenzierung mit Adaptionsregeln, Lernziele und Kompetenzen, Bewertungsraster, Lernpfad, Landes- und Schuldesign |
| `lehrplan` | P-WISSEN | Lehrplan-Auskunft je Land, Kompetenzmodelle, Bildungsstufen-Zuordnung, Fachberatung Physik-Optik |

Eine neue Fachdimension bedeutet: einen Skill schreiben und in die Registry eintragen. Kein neues Pattern, kein Deployment.

---

## 7. MCP-Tool-Inventar

### 7.1 Lesend, ohne Anmeldung — 25 Tools

| Gruppe | Tools |
|---|---|
| Suchen | `search_wlo_content`, `search_wlo_collections`, `search_wlo_all`, `search_wlo_within_collection`, `search_wlo_topic_pages`, `search` |
| Navigieren und Abrufen | `get_collection_contents`, `browse_collection_tree`, `get_subject_portals`, `get_topic_page_content`, `get_node_details`, `get_nodes_details`, `get_related_content`, `get_node_breadcrumb`, `get_node_collections`, `get_collection_stats`, `fetch` |
| Texte und Vokabulare | `get_wlo_content_text`, `get_compendium_text`, `get_wikipedia_summary`, `lookup_wlo_vocabulary`, `lookup_wlo_publishers`, `find_wlo_skills` |
| Betrieb | `wlo_health_check`, `wlo_auth_status` |

### 7.2 Kuratierend, nur mit Anmeldung — 13 Tools

Erscheinen ohne Identität nicht in `tools/list`. Alle mutierenden Werkzeuge sind zweistufig: ohne `confirmToken` nur Vorschau, der Schlüssel gilt einmalig, zehn Minuten, gebunden an genau diese Änderung.

| Gruppe | Tools |
|---|---|
| Datensätze | `wlo_create_content`, `wlo_update_content`, `wlo_submit_content`, `wlo_delete_content` |
| Sammlungen | `wlo_create_collection`, `wlo_rename_collection`, `wlo_delete_collection`, `wlo_add_to_collection`, `wlo_remove_from_collection` |
| Texte | `wlo_update_compendium` |
| Vorschläge | `wlo_suggest_metadata`, `wlo_list_suggestions`, `wlo_decide_suggestion` |

Die `confirmToken`-Mechanik entspricht genau E6. Frame (E2) und Bestätigung (E6) sollten über **denselben** Handler laufen.

---

## 8. Use-Cases

### Rubrik 1 — Finden und Durchsuchen

| Use-Case | Kanal | Quellen | MCP-Tools | Pattern / Mechanik | Skills | |
|---|---|---|---|---|---|---|
| Sammlung oder Thema suchen und erstöbern | C G | Q6 | `search_wlo_collections`, `search_wlo_all` | P-SUCHEN, E3 | — | ✓ |
| In eine Sammlung eintauchen, Inhalte auflisten | C G P | Q6 | `get_collection_contents`, `search_wlo_within_collection` | P-VERTIEFEN | — | ✓ |
| Themenbaum navigieren und blättern | C G | Q6 | `browse_collection_tree`, `get_node_breadcrumb` | P-VERTIEFEN | — | ✓ |
| Fachportale als Einstieg nutzen | C G | Q6 | `get_subject_portals` | P-SUCHEN | — | ✓ |
| Inhalte gefiltert suchen | C G P | Q5 | `search_wlo_content`, `lookup_wlo_vocabulary` | P-SUCHEN, E3 | — | ✓ |
| Nach Niveau und Bildungsstufe filtern | C G P | Q5 | `search_wlo_content`, `lookup_wlo_vocabulary` | P-SUCHEN, E3 | — | ~ unverifiziert |
| Nach Lizenz filtern | C G P | Q5 | `search_wlo_content`, `lookup_wlo_vocabulary` | P-SUCHEN, E3 | `lizenz` | ~ unverifiziert |
| Filter nachträglich ändern | C G | Q5 | `search_wlo_content` | E5 ✗ | — | ✗ |
| Inhaltsdetails und Metadaten abrufen | C G P | Q5 | `get_node_details`, `get_nodes_details` | P-VERTIEFEN | — | ✓ |
| Themenseiten finden und anzeigen | C G | Q7 | `search_wlo_topic_pages`, `get_topic_page_content` | P-VERTIEFEN | — | ~ kein Bestand |
| Ähnliche Inhalte finden | C G P | Q5 | `get_related_content` | P-VERTIEFEN | — | ~ Rendering fehlt |
| Verortung eines Materials | C P | Q6 | `get_node_collections`, `get_node_breadcrumb` | P-VERTIEFEN | — | ~ Rendering fehlt |
| Lehrplansammlung und Lehrplandetails abrufen | C G | Q8 Kap. 2 | `search_wlo_collections`, `get_compendium_section` ✗ | P-WISSEN | `lehrplan` | ✗ |
| Prüfungsdaten und Musterprüfungen finden | C G | Q5 | `search_wlo_content` | P-SUCHEN, P-UEBEN ✗ | `pruefung` | ✗ Archiv fehlt |
| Volltexte abrufen | C G P | Q5 | `get_wlo_content_text`, `get_node_details` | P-VERTIEFEN | — | ✓ |
| Anbieter und Herausgeber übersehen | C G | Q5 | `lookup_wlo_publishers` | P-BEWERTEN ✗ | `qs` | ✗ |
| OER-Statistik-Sammelknoten auswerten | C G | Q6 | `get_collection_stats`, `search_wlo_collections` | P-BEWERTEN ✗ | `qs` | ✗ |
| Eigene Inhaltsauswahl als Suchraum nutzen | C G | Q5 | `wlo_auth_status`, `search_wlo_within_collection` | P-SUCHEN (Slot) | — | ~ Auth-Methode offen |
| Nulltreffer retten | C | Q5, Q6 | `lookup_wlo_vocabulary`, `search_wlo_all` | E7 + `rescue` | — | ~ als M12, umzubauen |
| Auf Treffer Bezug nehmen | C G | Q5 | `get_nodes_details`, `fetch` | E4 ✗ | — | ✗ |
| Ergebnisse in passender Ansicht darstellen | C G | Q5–Q7 | Widget-Layer | P-SUCHEN, P-VERTIEFEN | — | ~ Ansichtswahl unvollständig |

### Rubrik 2 — Nachnutzen

| Use-Case | Kanal | Quellen | MCP-Tools | Pattern / Mechanik | Skills | |
|---|---|---|---|---|---|---|
| Ausgewählte Inhalte in den Arbeitskontext holen | C G P | Q5 | `get_node_details`, `get_nodes_details`, `fetch` | E4 ✗, E1 ✗ | — | ✗ |
| Volltexte für die Weiterverarbeitung bereitstellen | C G P | Q5 | `get_wlo_content_text`, `get_nodes_details` | P-VERTIEFEN | — | ~ max. 20 pro Aufruf |
| Inhalte remixen | C G P | Q5, Q8 | `get_wlo_content_text`, `get_compendium_section` ✗ | P-ADAPTIEREN ✗ | `didaktik`, `lizenz` | ✗ |
| Unterrichtsstunde planen | C G | Q5, Q8 Kap. 2 | `search_wlo_content`, `get_compendium_section` ✗ | P-ERZEUGEN | `didaktik` | ~ ohne Lehrplanbezug |
| Unterrichtsreihe konzipieren | C G | Q5, Q6 | `search_wlo_content`, `get_collection_contents` | P-ERZEUGEN | `didaktik` | ~ |
| Lernpfad aus dem Bestand bauen | C G | Q5 | `search_wlo_content`, `get_related_content` | P-ERZEUGEN | `didaktik` | ✓ |
| Lehrplaninhalte in Aktivitäten übersetzen | C G | Q8 Kap. 2 | `get_compendium_section` ✗ | P-ERZEUGEN | `lehrplan` | ✗ |
| Arbeitsblatt, Aufgaben, Quiz erstellen | C G P | Q5 | `get_wlo_content_text` | P-ERZEUGEN | `didaktik` | ✓ |
| Nach Lernniveau differenzieren | C G | Q5 | `search_wlo_content`, `get_wlo_content_text` | P-ADAPTIEREN ✗ | `didaktik` | ✗ |
| Inhalt an Didaktik oder Design anpassen | C P | Q5, Q9 | `get_skill_bundle` ✗, `get_wlo_content_text` | P-ADAPTIEREN ✗ | `didaktik` Musterdaten ✗ | ✗ |
| Artefakt nachbearbeiten | C | — | — | E5 ✗ | erbt | ✗ |
| Antwort umformulieren | C | — | — | E5 ✗ | erbt | ✗ |
| Prüfungsvorbereitung: Fragen, Bewertung, Feedback | C G | Q8 Kap. 2, Q5 | `get_compendium_section` ✗, `search_wlo_content` | P-UEBEN ✗ | `pruefung` | ✗ |
| Fachlich sachrichtig zum Thema antworten | C | Q8 Kap. 1 → Q4 → Q10 | `get_compendium_section` ✗, `get_wikipedia_summary` | P-WISSEN, E8 ✗ | `lehrplan` | ~ Kap. 1 und RAG leer |
| OER- und Lizenzwissen erklären | C | Q4 | — | P-WISSEN, E8 ✗ | `lizenz` | ✗ Korpus fehlt |
| Wissensfrage ohne Suche beantworten | C | Q4 | — | P-WISSEN | — | ~ RAG ungefüllt |
| Inhaltskompendium aus dem Kompendialtext ableiten | C G | Q8 | `get_compendium_section` ✗ | P-ERZEUGEN | `redaktion` | ✗ |
| Ergebnis im Chat oder als Druck ausgeben | C G | — | — | P-ERZEUGEN | — | ~ Ausgabeform unvollständig |

### Rubrik 3 — Auswerten und Empfehlen

Read-only, unabhängig von Auth und Schreiben. Tool-seitig fast fertig, pattern-seitig leer.

| Use-Case | Kanal | Quellen | MCP-Tools | Pattern / Mechanik | Skills | |
|---|---|---|---|---|---|---|
| Differenz Kompendium Kap. 3 gegen Sammlungsinhalte | C G | Q8 Kap. 3, Q6 | `get_compendium_section` ✗, `get_collection_contents` | P-BEWERTEN ✗ | `qs` | ✗ |
| Lücken analysieren und Vorschläge unterbreiten | C G | Q8, Q6 | `get_compendium_section` ✗, `get_collection_contents`, `get_collection_stats` | P-BEWERTEN ✗ | `qs` | ✗ |
| Vollständigkeit einer Sammlung bewerten | C G | Q8, Q6 | `browse_collection_tree`, `get_collection_contents`, `get_collection_stats` | P-BEWERTEN ✗ | `qs` Metrik ✗ | ✗ |
| Bestand über Statistik und Facetten einschätzen | C G P | Q6 | `get_collection_stats` | P-BEWERTEN ✗ | `qs` | ~ nur Basis-Stats |
| Zusatzwissen zur Klärung heranziehen | C G | Q10, Q11 ✗ | `get_wikipedia_summary`, `search_web` ✗ | P-BEWERTEN ✗, E8 ✗ | — | ~ Web fehlt |
| Inhalt prüfen und Bewertung ausgeben | C G P | Q5, Q8, Q9 | `search_wlo_content`, `get_node_details`, `find_wlo_skills` ~, `get_skill_bundle` ✗ | P-BEWERTEN ✗ | `qs` | ✗ |
| Sachrichtigkeit prüfen | C P | Q5 Volltext, Q9 | `get_wlo_content_text`, `get_skill_bundle` ✗ | P-BEWERTEN ✗ | `qs` | ✗ |
| Konformität zu Landes- oder Schulvorgaben prüfen | C P | Q9 | `get_skill_bundle` ✗ | P-BEWERTEN ✗ | `qs` Musterdaten ✗ | ✗ |
| Thematische Abdeckung für eine Bildungsstufe bewerten | C G | Q8 Kap. 2, Q6 | `get_compendium_section` ✗, `get_collection_contents` | P-BEWERTEN ✗ | `qs`, `lehrplan` | ✗ |
| Kennzahlen verständlich erklären | C G | Q6 | `get_collection_stats`, `lookup_wlo_publishers` | P-BEWERTEN ✗ | `qs` | ✗ |
| Rückmelden, was nicht geprüft werden konnte | C P | Q9 | `find_wlo_skills` ~ | E7 ✗ + `degrade` | `qs` | ✗ |
| Herkunft einer Antwort ausweisen | C | E8-Protokoll | — | E8 ✗, B-FEEDBACK | — | ✗ |
| Metadaten und Sammlungszuordnung empfehlen | C G P | Q5, Q6 | `get_node_details`, `get_node_collections`, `wlo_suggest_metadata` | P-KURATIEREN ✗ | `kuration` | ✗ |
| Hinterlegte Vorschläge einsehen und entscheiden | C P | Q5 | `wlo_list_suggestions`, `wlo_decide_suggestion` | P-KURATIEREN ✗, E6 ✗ | `kuration` | ✗ |

### Rubrik 4 — Kuratierungshilfen

| Use-Case | Kanal | Quellen | MCP-Tools | Pattern / Mechanik | Skills | |
|---|---|---|---|---|---|---|
| Webseite erschließen, Formular vorausfüllen | P | Q5 | `search_wlo_content`, `get_node_details`, `lookup_wlo_vocabulary` | P-KURATIEREN ✗ | `kuration` | ~ läuft ohne Bot |
| Neuen Datensatz für eine URL anlegen | C G P | Q5 | `wlo_create_content` | P-KURATIEREN ✗, E6 ✗ | `kuration` | ✗ |
| Datensatz mit eigenem Textkörper anlegen | C G | Q5 | `wlo_create_text_content` ✗ | P-KURATIEREN ✗, E6 ✗ | `kuration` | ✗ |
| Metadaten eines Datensatzes ändern | C G P | Q5 | `wlo_update_content` | P-KURATIEREN ✗, E6 ✗ | `kuration` | ✗ |
| Volltext eines Datensatzes schreiben oder ergänzen | C G | Q5 | `wlo_update_content_text` ✗ | P-TEXTKOERPER ✗, E6 ✗ | `redaktion` | ✗ |
| Datensatz zur redaktionellen Prüfung einreichen | C G P | Q5 | `wlo_submit_content` | P-KURATIEREN ✗ | `kuration` | ~ M13 zeigt nur Link |
| Metadaten-Vorschläge hinterlegen | C G P | Q5 | `wlo_suggest_metadata` | P-KURATIEREN ✗ | `kuration` | ✗ |
| Sammlung anlegen oder umbenennen | C G P | Q6 | `wlo_create_collection`, `wlo_rename_collection` | P-KURATIEREN ✗, E6 ✗ | `kuration` | ✗ |
| Material in Sammlung aufnehmen oder entfernen | C G P | Q6 | `wlo_add_to_collection`, `wlo_remove_from_collection` | P-KURATIEREN ✗, E6 ✗ | `kuration` | ✗ |
| Erzeugtes Artefakt ablegen und Sammlung vorschlagen | C G | Q6 | `wlo_create_text_content` ✗, `wlo_add_to_collection`, `browse_collection_tree` | P-KURATIEREN ✗, E3 ✗, E6 ✗ | `kuration`, `lizenz` | ✗ |
| Canvas-Inhalt oder Chatverlauf verstetigen | C G | Q5 | `wlo_create_text_content` ✗ | P-KURATIEREN ✗ | `kuration` | ✗ |
| Datensatz oder Sammlung löschen | C G P | Q5, Q6 | `wlo_delete_content`, `wlo_delete_collection` | P-KURATIEREN ✗, E6 ✗ | `kuration` | ✗ |
| Kompendialtext schreiben, ersetzen, entfernen | C G | Q8 | `wlo_update_compendium`, `get_compendium_section` ✗ | P-TEXTKOERPER ✗ | `redaktion` | ✗ |
| Kapitel 3 bei neuen Inhalten aktualisieren | C | Q8, Q6 | `wlo_update_compendium`, Repo-Trigger ✗ | P-TEXTKOERPER ✗ | `redaktion` | ✗ |
| Frage-Antwort-Paare generieren und editieren | C | Q8 | `get_qa_pairs` ✗, `wlo_update_qa_pairs` ✗ | P-TEXTKOERPER ✗ | `redaktion` | ✗ |
| Bot gegen den Text testen, Fehlerquelle nennen | C | Q8, Q&A, E8-Protokoll | `get_compendium_section` ✗, `get_qa_pairs` ✗ | B-FEEDBACK, E8 ✗ | `redaktion` | ~ teils M17 |
| Skill anlegen, ändern, versionieren, freigeben | C G | Q9 | `wlo_create_text_content` ✗, `wlo_update_content_text` ✗, Registry-Schreibzugriff ✗ | P-TEXTKOERPER ✗ | `skill` | ✗ |
| Skill-Katalog zeigen, Skill erklären | C G | Q9 | `find_wlo_skills` ~, `get_skill_bundle` ✗ | B-PLATTFORM ✗ | `plattform` | ✗ |
| Skill gezielt anwenden | C G | Q9 | `get_skill_bundle` ✗ | Slot am jeweiligen Pattern | betroffener Scope | ✗ |
| Sammlung zur Themenseite machen | P G | Q7 | `wlo_set_topic_page` ✗ | P-KURATIEREN ✗ | `kuration` | ✗ |
| Nutzung oder Danksagung vermerken | C G P | Q5 | `wlo_register_usage` ✗ | P-KURATIEREN ✗ | — | ✗ |
| Quellen systematisch erschließen (Crawler) | C P | Q11 ✗ | `search_web` ✗, `crawl_source` ✗ | P-KURATIEREN ✗ | `kuration` | ✗ |
| Plattformvorgänge erklären | C | Q1 | — | B-PLATTFORM ✗ | `plattform` | ✗ |
| Auskunft zu Projekten geben | C | Q2 | — | B-PLATTFORM ✗ | `plattform` | ✗ |
| Auskunft zu Partnern geben | C | Q3 | — | B-PLATTFORM ✗ | `plattform` | ✗ |
| Schreibrecht und Identität klären | C G P | — | `wlo_auth_status` | P-KURATIEREN ✗ | — | ~ Pattern fehlt |
| Fehler melden | C P | — | `wlo_submit_content` | B-FEEDBACK | — | ~ ruft kein Tool |
| Skills an das User-LLM ausliefern | G | Q9 | MCP als Skill-Hub, Deeplink | kein Pattern — Auslieferungsweg | — | ~ Wege geklärt |

---

## 9. Offene Entscheidungen

| Entscheidung | Wirkt auf |
|---|---|
| RAG-Segmentierung: vier getrennte Korpora oder ein Index mit Korpus-Label | E8, B-PLATTFORM, P-WISSEN |
| Ausreichend-Kriterium für E8: Score-Schwelle, Themenabgleich oder LLM-Urteil | Antwortqualität, Latenz |
| YAML gegen Markdown gegen RAG für den Kompendialtext | `get_compendium_section`, Editor-Entwicklung, P-TEXTKOERPER |
| Ablageform des Kompendialtextes: Property, eigenes Objekt, Serienobjekte nach Bildungsstufe | P-TEXTKOERPER, Performance |
| Auth-Methode für das Sommercamp: ein Demo-User gegen OAuth2 | alle Kurationswerkzeuge |
| QS-Metriken: wann ist eine Sammlung vollständig | `qs`-Skills, P-BEWERTEN |
| Grenzwerte für Performance beim Skill-Laden | P-BEWERTEN, P-ERZEUGEN, P-ADAPTIEREN |
| Editor-Wahl und Transferszenario | P-TEXTKOERPER, Browser-Plugin |

---

## 10. Minimal-Set für das Sommercamp

| Kategorie | Umfang |
|---|---|
| Engine | E1 Slot-Register · E2 Frame · E3 Slot-Nachfrage · E6 Bestätigung (gemeinsamer Handler mit E2) · E7 Degradation · E8 Quellen-Routing |
| Pattern neu | P-KURATIEREN · P-BEWERTEN · P-TEXTKOERPER · B-TRANSPARENZ · B-PLATTFORM |
| Zusammenführungen | P-SUCHEN · P-VERTIEFEN · P-ERZEUGEN |
| Tools | `get_skill_bundle` · `get_compendium_section` · `wlo_create_text_content` |
| Skills | Registry und je 2–3 Skills für `kuration`, `qs`, `plattform` |
| Quellen | RAG segmentieren und Q1 füllen · Q8 Kap. 2 und Kap. 3 für Optik · Q7 Themenseite Optik · Q9 Skill-Sammlung anlegen |
| Verifikation | Niveau- und Lizenzfilter in `search_wlo_content` |

**Verschiebbar:** E4, E5, P-UEBEN, P-ADAPTIEREN, B-OFFTOPIC, Korpora Q2–Q4, Scopes `lehrplan`, `pruefung`, `lizenz`, `redaktion`, `skill`.

**Nicht verschiebbar, auch wenn es verlockt:** solange M11 mit Prio 600 als Pattern in der Liste steht, fängt es Bestätigungen und Slot-Antworten ab. Entweder E5 bauen oder M11 vorübergehend deaktivieren.

**E8 ist neu im Minimal-Set,** weil B-PLATTFORM und P-WISSEN sonst über alle Quellen fächern und die Herkunft nicht ausweisbar ist. Eine reduzierte Variante genügt fürs SC: feste Vorrangketten aus dem Pattern-Vertrag, ohne dynamische Bewertung.

---

## 11. Soll-Ist-Abgleich

### 11.1 Pattern

| ID | Soll | Ist | Zu tun |
|---|---|---|---|
| S-KRISE | 999, Schutz | M01 | — |
| S-BEDROHUNG | 998, Schutz | M02 | — |
| B-OFFTOPIC | 620 | — | **neu anlegen** |
| B-TRANSPARENZ | 610, Konfigurationsquelle | — | **neu anlegen** |
| B-FEEDBACK | 600, Q8 + E8-Protokoll | M13 teils, M14 | zusammenführen, `wlo_submit_content` anbinden, Herkunftsangabe |
| B-PLATTFORM | 590, Q1→Q2→Q3 + Skill-Katalog, Scope `plattform` | — | **neu anlegen** |
| P-TEXTKOERPER | 588, Q8/Q5/Q9, Scope `redaktion` + `skill` | — | **neu anlegen** |
| P-KURATIEREN | 584, Q5/Q6, Scope `kuration` + `lizenz` | — | **neu anlegen** |
| P-BEWERTEN | 570, Q8→Q6→Q5 + Q9, Scope `qs` | — | **neu anlegen** |
| P-UEBEN | 555, Q8 Kap. 2 + Q5, Scope `pruefung` | — | **neu anlegen** |
| P-ADAPTIEREN | 545, Q5 Volltext + Q9, Scope `didaktik` + `lizenz` | — | **neu anlegen** |
| P-ERZEUGEN | 530, Q5/Q8/Q9, Scope `didaktik` | M09, M10 | zusammenführen, skillgetrieben, Ablage-Absprung |
| P-WISSEN | 520, Q8 Kap. 1/2 → Q4 → Q10, Scope `lehrplan` | M04 | Quellenkette und `wissensart` ergänzen, RAG bestücken |
| P-VERTIEFEN | 510, Q5/Q6/Q7 | M08, M16, M17 | zusammenführen, Rendering je Objekttyp, Verortung und Ähnliches |
| P-SUCHEN | 500, Q5→Q6→Q7 | M05, M06, M07 | zusammenführen, Prio-Gleichstand auflösen, Filter-Slots, `rescue` |
| B-ORIENTIERUNG | 460, Q1 | M15 | als Fallback verdrahten |
| — | entfällt als Pattern | M03 | in E3 überführen |
| — | entfällt als Pattern | M11 | in E5 überführen |
| — | entfällt als Pattern | M12 | in E7 überführen |

**Bilanz:** 16 Pattern im Soll · 8 neu anzulegen · 4 zusammenzuführen · 2 anzupassen · 3 in Mechaniken überzuführen.

### 11.2 Engine-Mechaniken

| ID | Soll | Ist | Zu tun |
|---|---|---|---|
| E1 | Slot-Register je Eigentümer | — | **neu** |
| E2 | Frame mit Frist und Versuchszähler | — | **neu** |
| E3 | Slot-Nachfrage-Renderer | M03 als Pattern | **neu**, M03 auflösen |
| E4 | Bezugsauflösung Ordinal und Deixis | — | **neu** |
| E5 | Revision gefüllter Slots | M11 als Pattern | **neu**, M11 auflösen |
| E6 | `confirmToken` einlösen, Feldbericht | — | **neu**, Handler mit E2 teilen |
| E7 | `rescue` und `degrade` des Eigentümers | M12 als Pattern | **neu**, M12 auflösen |
| E8 | Quellen-Routing mit Vorrang und Herkunftsnachweis | — | **neu** |
| — | Auswahl läuft nach den Mechaniken, Pattern-Vertrag im Seed-Schema | flache `priority`-Liste | Auswahlmechanismus umbauen |

**Bilanz:** 8 Mechaniken, alle neu, plus ein Umbau des Auswahlmechanismus.

### 11.3 Skills

Für Skills liegt **kein belastbarer Ist-Stand** vor. Alle Scopes sind als neu zu planen.

| Scope | Registry | Skills | Aufwand | Blockiert |
|---|---|---|---|---|
| `kuration` | **neu** | 7 | hoch | P-KURATIEREN, Rubrik 4 |
| `qs` | **neu** | 10 | hoch | P-BEWERTEN, Rubrik 3 |
| `didaktik` | **neu** | 9 | hoch | P-ERZEUGEN, P-ADAPTIEREN |
| `plattform` | **neu** | 7 | mittel, nur Dokumentation | B-PLATTFORM |
| `redaktion` | **neu** | 5 | mittel | P-TEXTKOERPER |
| `lizenz` | **neu** | 4 | mittel | P-KURATIEREN, P-ADAPTIEREN |
| `lehrplan` | **neu** | 4 | hoch, braucht Curricula | P-WISSEN |
| `pruefung` | **neu** | 4 | mittel, braucht Prüfungsarchiv | P-UEBEN |
| `skill` | **neu** | 4 | niedrig, Review-Gate ist Pflicht | P-TEXTKOERPER (SKILL.md) |

**Voraussetzung für alle:** Skill-Sammlung anlegen und `WLO_SKILLS_COLLECTION_ID` verdrahten.

### 11.4 MCP-Tools

**Vorhanden: 38** — 25 lesend (Abschnitt 7.1), 13 kuratierend (Abschnitt 7.2).

| Tool | Soll | Ist | Zu tun | Prio |
|---|---|---|---|---|
| `get_skill_bundle` | Skill inkl. Anhänge und Musterdaten laden | — | **neu** | hoch |
| `get_compendium_section` | Kapitel oder Facette einzeln, mit Inhaltsverzeichnis-Modus für E8 | `get_compendium_text` liefert alles | **neu** | hoch |
| `wlo_create_text_content` | Datensatz mit Textkörper oder Datei | `wlo_create_content` nur für URL | **neu** | hoch |
| `wlo_update_content_text` | Volltext schreiben oder ergänzen | `wlo_update_content` nur Metadaten | **neu** | mittel |
| `get_qa_pairs` / `wlo_update_qa_pairs` | Q&A adressierbar mit IDs | nur im Kompendialtext, ohne IDs | **neu** | mittel |
| Volltext-Batch | über 20 IDs | `get_nodes_details` max. 20 | **neu** | mittel |
| `search_web` | Websuche mit Quellenangabe | nur `get_wikipedia_summary` | **neu** | mittel |
| `crawl_source` | Quelle oder Domain erschließen | — | **neu** | mittel |
| `wlo_set_topic_page` | Layout, Schwimmlinien, Zielgruppen setzen | Themenseiten nur lesbar | **neu** | mittel |
| Repo-Trigger / Webhook | Kap. 3 neu berechnen | kein Ereignis | **neu** | niedrig |
| `wlo_register_usage` | Nutzung bzw. „+1" schreiben | OER-Statistik nicht schreibbar | **neu** | niedrig |
| Registry-Schreibzugriff | Skill eintragen | — | **neu**, fürs SC manuell | niedrig |
| `get_collection_coverage` | Abdeckung serverseitig | — | **neu**, nur bei Performanceproblemen | niedrig |
| `search_wlo_content` | Niveau- und Lizenzfilter belastbar | vorhanden, unverifiziert | **prüfen und dokumentieren** | hoch |
| `find_wlo_skills` | Scope-Filter, verdrahtete Sammlung | `WLO_SKILLS_COLLECTION_ID` fehlt | **nachschärfen** | hoch |
| `get_compendium_text` | Bestand vorhanden | Tool ✓, Bestand ✗ | Bestand aufbauen | hoch |
| `wlo_auth_status` | Methode entschieden, Rechte-User | Auth ✓, Methode offen | entscheiden | hoch |
| `get_collection_stats` | Verteilungs- und Abdeckungswerte | nur Basis-Stats | **nachschärfen** | mittel |
| `get_nodes_details` | Grenze kommunizieren oder Batch | max. 20 Volltexte | **nachschärfen** | mittel |

**Bilanz:** 13 Tools neu · 6 nachzuschärfen · 38 unverändert nutzbar.

### 11.5 Wissensquellen und Bestände

| Quelle | Soll | Ist | Zu tun |
|---|---|---|---|
| Q1 Webseite und Prozesse | RAG-Korpus, gefiltert abfragbar | RAG vorhanden, ungefüllt, unsegmentiert | **RAG segmentieren, Korpus füllen** |
| Q2 Projekte | RAG-Korpus | — | **Korpus füllen** |
| Q3 Partner | RAG-Korpus | — | **Korpus füllen** |
| Q4 OER-Wissen | RAG-Korpus | — | **Korpus füllen** |
| Q5 Inhalte und Metadaten | MCP | ✓ | — |
| Q6 Sammlungen und Themenbaum | MCP | ✓ | — |
| Q7 Themenseiten | MCP plus Bestand | Tools ✓, Bestand ✗ | **Themenseite Optik anlegen** |
| Q8 Kompendiale Texte | Kap. 1–3 für Optik, kapitelweise lesbar | Tool ✓, Bestand ✗ | **Texte erstellen**, Ablageform entscheiden |
| Q9 Skills und Registries | 9 Registries, Skill-Sammlung verdrahtet | Tool ✓, Sammlung ✗ | **Sammlung anlegen, Registries aufbauen** |
| Q10 Wikipedia | MCP | ✓ | — |
| Q11 Web und Crawler | MCP | ✗ | **Tools anlegen** |
| Prüfungsarchiv | Daten in der Lehrplansammlung | ✗ | **Material akquirieren** |
| Musterdaten Design und Didaktik | Vorlagen im Skill-Ordner | ✗ | **erstellen** |
| Modell- und Datenschutzangaben | Konfiguration für B-TRANSPARENZ | ✗ | **erstellen** |

### 11.6 Gesamtbilanz

| Kategorie | Vorhanden | Neu anzulegen | Umzubauen |
|---|---|---|---|
| Pattern | 5 unverändert übernehmbar | 8 | 4 Zusammenführungen, 2 Anpassungen, 3 Auflösungen |
| Engine-Mechaniken | 0 | 8 | Auswahlmechanismus |
| Skills | kein belastbarer Ist-Stand | 9 Registries, 54 Skills | — |
| MCP-Tools | 38 | 13 | 6 nachzuschärfen |
| Wissensquellen | 4 von 11 | 6 Korpora bzw. Bestände | RAG-Segmentierung |
