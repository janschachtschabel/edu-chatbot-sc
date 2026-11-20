# ui_upload — Ordner und Dateien bereitstellen: erfassen (U3-1), „Wo verarbeiten?“ und ein Knopf je Ort (Paket U, P2)

Nachgeladenes Modul (`laden: "bei_bedarf"`): rahmenloses Custom Element `<boerdi-ui-upload>` in einem
eigenen Bündel (siehe `docs/ui-module.md` §2.5).

- **Erfassen nur im Browser** (`upload-erfassen.ts`): Ordner per Knopf (`webkitdirectory`) oder
  Ablegen (FileSystem-Einträge, rekursiv), Filter (Systemdateien, leer, zu groß), Grenzen (Anzahl,
  Tiefe), ungültige Pfade verworfen; Datei-Eingaben und Ablage-Einträge liest `upload-eingabe.ts`.
- **Rollen** (`upload-rollen.ts`): Inhalt, Strukturdokument (bis zu fünf seit Plan 2026-11-16,
  TG-3e — ein sechstes ist nicht wählbar; so viele erlaubt das Antwort-Schema und die Ablage in WLO —
  Paket U prüfte die Grenze und ließ sie; PDF/DOCX/TXT/MD; ein einzelner Lehrplan in der Wurzel wird
  vorgeschlagen), ignorieren — je Datei oder je Ordner. Plan 2026-11-20, P1 (UO-4): angezeigt als
  „Gliederung“ (`struktur`), „Material“ (`inhalt`), „Gliederung und Material“ (`beides`, gilt als
  Strukturdokument und Inhalt; zählt zu den fünf, nur lesbare Formate) und „Nicht verwenden“
  (`ignorieren`), mit einer Legende unter der Liste. `zahlen.inhalte` zählt nur `inhalt`,
  `zahlen.strukturdokumente` `struktur` und `beides`.
- **Antwort** (`upload-antwort.ts`): Ordnerbaum mit Zahlen, Zahlen je Rolle, Warnungen, ggf. Name des
  Strukturdokuments. Seit Plan 2026-11-16, TG-3a trägt jeder Ordner seine Dateien (`dateiliste`: feste
  Nummer `i`, Name, Endung, Größe, Rolle; ohne Systemdateien; Namen über 120 Zeichen gekürzt mit
  Warnung `namen_gekuerzt`) — nie Inhalte. Das Backend macht daraus den Teil `struktur`; die KI sieht
  nur eine Zusammenfassung. Dieselbe Nummer `i` trägt die Freigabe beim Übertragen nach WLO (TG-3b).
  Vormerkung (`aktion: "erfasst"`) mit der getippten Nachricht; per Knopf geht seit Paket U immer
  `aktion: "bereitgestellt"` mit `ort` (unten).
- **Zielneutral** (Plan 2026-11-16, TG-1): das Feld stellt Daten nur bereit (`zweck: bereitstellen`;
  `sammlungsstruktur` bleibt gültig) und kennt kein Ziel — kein „Als Themenbaum-Entwurf übernehmen“,
  kein `ziel` am Dokument. Was mit den Daten geschieht, entscheiden die nächsten Schritte eines Ablaufs
  oder die KI mit der Person. Alte Antworten (`ordner_als_entwurf`, `dokument.ziel`) nimmt das Backend
  noch an (wie `erfasst` bzw. `dokument`).
- **Darstellung** (`upload-ansicht.ts` baut die Knoten aus einer Sicht auf den Zustand, `upload-baum.ts`,
  `upload-stil.ts`; das Element behält Zustand, Ereignisse und Fokus): Disclosure-Muster (Ordner = Knopf mit
  `aria-expanded`, Rolle = beschriftetes Auswahlfeld), Fremdtext nur als `textContent`, Fokus bleibt
  beim Neuzeichnen, Ansagen über eine bleibende `aria-live`-Zeile, nur M3-Tokens.
- **Strukturdokument lesen** (U3-2c/TG-3e, „Lesen lassen“, `aktion: "dokument"`) ist in „Hier im
  Chat“ aufgegangen (Paket U, unten). Ältere Antworten `dokument` zeigt das Modul „nur lesend“ weiter.
- **In den persönlichen Bereich übertragen** (U3-3b, `upload-uebertragen.ts` Regeln,
  `upload-uebertragen-ablauf.ts` Zustand, `upload-uebertragen-ansicht.ts` Darstellung): seit Paket U der Ort
  „In WLO ablegen und erschließen“ mit „Weiter zur Vorschau“ (seit Plan 2026-11-20, P2; davor „Hochladen“, vorher ein eigener Knopf „Übertragen vorbereiten …“);
  nur wenn das System es erlaubt (`orte.wlo.geht`; ohne `orte` `schalter.ablage_in_wlo` — Studio **und**
  bestätigte Anmeldung). Übertragen werden nicht
  ignorierte Dateien bekannter Art bis `grenzen.max_mb_ablage`, höchstens 200 je Freigabe. Ablauf: prüfen
  (sha256 im Browser, k von n) → `host.ablegen({schritt: 'vorbereiten'})` (je Eintrag die **Rolle**,
  `inhalt` | `struktur` — seit W4 Teil der Freigabe) → **Vorschau** (Ziel, Ordner oder flach, Namen des
  Servers, das Strukturdokument als solches benannt; daneben eingeklappt die eigenen **letzten Ablagen**, Paket M6 — `letzte` aus
  derselben Antwort, `letzteAus`) mit „In WLO ablegen und erschließen“ bzw. „In WLO ablegen“ (P2: je nachdem,
  ob der Server das Häkchen `erschliessen` festhielt; vorher „Jetzt übertragen“)/„Abbrechen“ → je Datei **nacheinander**
  (`schritt: 'datei'`, Fortschritt) → Ergebnisliste (Stand als Text und Symbol, Link je Knoten über
  `host.link`) → `vorgang.json` (`schritt: 'abschluss'`) → „Im Chat weitermachen“ (Antwort seit Paket U
  `aktion: "bereitgestellt"`, `ort: "wlo"`, `dateien: [{i, rolle}]` je abgelegter Datei und `ablage{…}` —
  **nur Zahlen**, keine Kennungen, auch vorgemerkt; vorher `aktion: "uebertragen"`). „Anhalten“ wirkt nach der
  laufenden Datei; „Nicht übertragene noch einmal senden“ schickt nur, was ein neuer Versuch heilen kann.
  Fähigkeit `hochladen` (für `ablegen`) und `oeffnen` (für die Links). Ohne https (kein `crypto.subtle`)
  der Code `unsicher`.
- **Texterkennung** (Plan 2026-11-19, Paket C): meldet der Server `orte.chat.texterkennung`, hängt das Feld an
  den Datenschutz-Satz „Gescannte Seiten gehen als Bild an das KI-Modell.“; liest der Server eine PDF länger
  als 5 s (`LANGE_MS`), erscheint und ertönt „Bei gescannten Seiten läuft eine Texterkennung – das kann bis
  zu anderthalb Minuten dauern.“; die Blase nennt danach „davon k per Texterkennung gelesen“ (Warnung `ocr`).
- **Texte** (`upload-texte.ts`, `upload-uebertragen-texte.ts`): Deutsch und Englisch, Zahlen und Größen
  über `Intl`.
- Backend: Dienst `upload_angebot` (`backend/src/boerdi/ui_module/dienst_upload.py`), Antwortform
  (`ui_module/upload_antwort.py`, neutrale Rahmen `[ORDNER …]` bzw. `[DOKUMENT DER PERSON …]` — sie
  sagen, was bereitliegt), Dokument lesen (`api/ui_dokumente.py`, `services/dokumente/`), Ablage im persönlichen
  Bereich (`api/ui_ablage.py`, `services/ablage/`, Rahmen `[ABLAGE DER PERSON …]`).
- **Ein Upload-Weg — „Wo verarbeiten?“** (Plan 2026-11-17, Paket U; Vertrag `docs/ui-module.md` §6
  „Ein Upload-Weg“). Bedienung:
  1. Ordner oder Dateien wählen, Rollen setzen (wie oben).
  2. Frage **„Wo sollen die Dateien verarbeitet werden?“** (`upload-orte.ts` Regeln, `upload-orte-ansicht.ts`
     Darstellung; Wortlaut nach Plan 2026-11-20 §4): zwei Chips als echte Radioknöpfe in einem `fieldset` mit
     `legend` (Pfeiltasten wählen, gesperrte überspringt der Browser), je Chip eine Erklärzeile (`aria-describedby`):
     **Nur hier im Chat lesen** („Nichts wird in WLO gespeichert … vergisst ihn spätestens {h} Stunden nach der
     letzten Nutzung. Bis {n} Dateien.“) und **In WLO ablegen und erschließen** („Deine Dateien werden Inhalte
     in deinem persönlichen Bereich in WLO … WLO liest den Text und erzeugt Titel, Beschreibung, Fach, Stufe und
     Schlagworte. Dauert ein paar Minuten.“). Unter dem gewählten Ort WLO das **Häkchen „Metadaten von WLO
     erzeugen lassen“** (Kontrollkästchen mit Label, Hinweiszeile per `aria-describedby`; Vorgabe aus
     `erschliessen`) — nur, wenn der Ablauf-Schritt `erschliessen` ausdrücklich setzt (true oder false: der
     Ablauf nutzt die Erschließung danach, Auftragsschritt mit `zustimmung: upload`) und der Metadaten-Flow
     da ist. **Ohne `erschliessen`** (freier Chat, Schritt ohne die Angabe; Review P2, Befund 1) gibt es
     kein Häkchen: der Ort heißt **In WLO ablegen**, die Erklärzeile und der Datenschutz-Satz sagen „nur
     ablegen“, `vorbereiten` schickt `erschliessen: false`. Mit `hinweis: ohne_erschliessung` (und
     `erschliessen` gesetzt) heißt der Ort ebenso **In WLO ablegen** und nennt den Grund aus
     `grund_erschliessung` („Metadaten kann WLO gerade nicht erzeugen (in diesem Chat nicht freigegeben).“
     bzw. „(der Dienst dafür ist gerade nicht erreichbar)“). Die Antwort trägt in `ablage.erschliessen`,
     was der Server festhielt — der Rahmen sagt es der KI. Der alte
     Schlüssel `einzeldatei_als_struktur` schaltet seit P2 nichts mehr um (er heißt `rolle_vorgabe: gliederung`).
     Gesperrte bleiben sichtbar, der Grund steht als Text („nicht wählbar – melde dich über den Konto-Knopf unten an“, „zu viele Dateien für hier (höchstens {n}) – mit Anmeldung
     über WLO“, „zu viel für hier (höchstens {mb} MB zusammen)“, „gerade ausgeschaltet“, „in diesem
     Ablauf nicht vorgesehen“; nur hier gerechnet: mehr als 200 für WLO, keine übertragbare Art).
     Vorauswahl aus `orte.vorauswahl` (P2: rechnet das Backend nach dem Anwendungsfall — Studio
     `upload-config.vorauswahl` im freien Chat, Schritt-Daten `vorauswahl` in einem Ablauf); die Grenzen `lokal_max_dateien` und `lokal_max_mb_gesamt` prüft
     das Modul gegen die Auswahl (nur lesbare Dateien, Inhalte und Strukturdokumente zusammen) — darüber
     ist „Nur hier im Chat lesen“ gesperrt, und die Vorauswahl wechselt zu WLO bzw. zu den Namen. `{h}` kommt aus
     `grenzen.lokal_aufbewahrung_h`. Ohne `orte` (älteres Backend, Studio-Vorschau) aus `schalter`
     abgeleitet. Darunter Hinweise zum gewählten Ort (nicht lesbare Dateien, was WLO nicht annimmt) und
     der **Datenschutz-Satz** zum Ort (was geht wohin, wie lange).
  3. **Ein Hauptknopf je Ort** (P2): **„Hier lesen“** (Chat) bzw. **„Weiter zur Vorschau“** (WLO — legt noch
     nichts ab; ablegen tut erst der Knopf der Vorschau), daneben **„Nur die Dateinamen senden (der Inhalt
     bleibt auf deinem Gerät)“** (`ort: "namen"`) und „Andere Auswahl“. Geht kein Ort, fehlt der Hauptknopf,
     und „Nur die Dateinamen senden“ ist der Hauptknopf. Die Rollen beginnen nach `rolle_vorgabe`
     (`upload-rollen.ts` `vorschlagen`: `gliederung`/`beides` jede lesbare Datei bis 5, `material` keine,
     `auto` die Lehrplan-Regel).
  4. **Hier im Chat** (`upload-chat.ts` Regeln, `upload-chat-ablauf.ts` Zustand, `upload-chat-ansicht.ts`
     Darstellung): je lesbare Datei (PDF, Word, Text, Markdown) `host.hochladen(datei, fortschritt, rolle)`
     → `POST /api/ui/dokumente` mit `rolle`, **nacheinander**, „Datei k von n“; ein Fehler je Datei als
     eigener Satz mit Dateinamen, „Noch einmal versuchen“ nur, wo es hilft, und „Ohne diese weiter“
     (auch bei `grenze_gesamt`). `grenze_anzahl` beendet den Lauf: „Mit den gelesenen weiter“ und „Nur
     Namen senden“. „Nach dieser Datei anhalten“ (und ein entferntes Element) hält nach der laufenden
     Datei an: „Mit den gelesenen weiter“ oder „Andere Auswahl“; nach Fehler oder Ende mit gelesenen
     Dateien ein Satz zur Frist `{h}`. Nicht lesbare Formate und Dateien über `lokal_max_mb_datei` gehen
     nicht hoch („nur der Name geht mit“); ohne lesbare Datei ist der Ort gesperrt. Dieselbe Datei
     (Name, Größe, Rolle, Änderungsdatum) geht einmal hoch, teilt die `upload_id` und zählt einmal. Mit `lokal_frei_dateien`/
     `lokal_frei_mb` (Rest der Sitzung) und dem Grund `grenze_sitzung` sperrt das Modul vorher.
     Antwort `aktion: "bereitgestellt"`, `ort: "chat"`, `dateien: [{i, rolle, upload_id}]` (auch
     vorgemerkt); läuft gerade ein Zug, wartet sie auf „Weiter“.
  5. **In WLO** (oben): prüfen → Vorschau (`vorbereiten` mit `erschliessen`) mit „In WLO ablegen und
     erschließen“ bzw. „In WLO ablegen“/„Abbrechen“ → je Datei → Abschluss. Ein Fehler vor dem Senden bringt
     die Frage zurück; „Weiter zur Vorschau“ versucht es neu.

  Zustände: leer, Auswahl (mit Frage), gesperrt (Chip mit Grund), lädt (Fortschritt), Teilfehler,
  fertig. Der Fokus geht nach jedem Schritt auf den neuen Stand (nie auf `body`).
