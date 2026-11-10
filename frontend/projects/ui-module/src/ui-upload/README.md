# ui_upload — Ordner und Dateien erfassen (Paket U3-1), Strukturdokument lesen (U3-2), in WLO übertragen (U3-3)

Nachgeladenes Modul (`laden: "bei_bedarf"`): rahmenloses Custom Element `<boerdi-ui-upload>` in einem
eigenen Bündel (siehe `docs/ui-module.md` §2.5).

- **Erfassen nur im Browser** (`upload-erfassen.ts`): Ordner per Knopf (`webkitdirectory`) oder
  Ablegen (FileSystem-Einträge, rekursiv), Filter (Systemdateien, leer, zu groß), Grenzen (Anzahl,
  Tiefe), ungültige Pfade verworfen.
- **Rollen** (`upload-rollen.ts`): Inhalt, Strukturdokument (höchstens eins, PDF/DOCX/TXT/MD; ein
  einzelner Lehrplan in der Wurzel wird vorgeschlagen), ignorieren — je Datei oder je Ordner.
- **Antwort** (`upload-antwort.ts`): Ordnerbaum mit Zahlen, Zahlen je Rolle, Warnungen, ggf. Name des
  Strukturdokuments — **keine Dateinamen**. Vormerkung mit der getippten Nachricht oder Knopf
  „Befund senden“ / „Als Themenbaum-Entwurf übernehmen“.
- **Darstellung** (`upload-ansicht.ts` baut die Knoten aus einer Sicht auf den Zustand, `upload-baum.ts`,
  `upload-stil.ts`; das Element behält Zustand, Ereignisse und Fokus): Disclosure-Muster (Ordner = Knopf mit
  `aria-expanded`, Rolle = beschriftetes Auswahlfeld), Fremdtext nur als `textContent`, Fokus bleibt
  beim Neuzeichnen, Ansagen über eine bleibende `aria-live`-Zeile, nur M3-Tokens.
- **Strukturdokument lesen** (U3-2c, `upload-dokument.ts`, `upload-dokument-ansicht.ts`): ist ein
  Strukturdokument markiert und erlaubt es das System (`schalter.dokument_im_chat` — Studio-Bereich
  `01-base/upload-config`; die WLO-Anmeldung nur, wenn dort `dokument_ohne_anmeldung` aus ist), zeigt das Modul die **Ziele** als Knöpfe (eine Liste,
  Plan O-26; heute „Themenbaum aus dem Strukturdokument erstellen“). Klick → `host.hochladen(datei)`
  (Fähigkeit `hochladen`, XHR mit Fortschritt, `POST /api/ui/dokumente`) → Befund → Antwort
  `aktion: "dokument"` mit `dokument{upload_id, name, format, ziel, befund, vorschau}` — nie der Text.
  Nur diese eine Datei wird hochgeladen. Fehler je Code als eigener Satz, ein neuer Versuch nur, wo
  er helfen kann (Netz, Last, Frist); läuft gerade ein Zug, wartet der Befund auf „… jetzt erstellen“.
- **In den persönlichen Bereich übertragen** (U3-3b, `upload-uebertragen.ts` Regeln,
  `upload-uebertragen-ablauf.ts` Zustand, `upload-uebertragen-ansicht.ts` Darstellung): nur wenn das System
  es erlaubt (`schalter.ablage_in_wlo` — Studio **und** bestätigte Anmeldung). Übertragen werden nicht
  ignorierte Dateien bekannter Art bis `grenzen.max_mb_ablage`, höchstens 200 je Freigabe. Ablauf: prüfen
  (sha256 im Browser, k von n) → `host.ablegen({schritt: 'vorbereiten'})` (je Eintrag die **Rolle**,
  `inhalt` | `struktur` — seit W4 Teil der Freigabe) → **Vorschau** (Ziel, Ordner oder flach, Namen des
  Servers, das Strukturdokument als solches benannt; daneben eingeklappt die eigenen **letzten Ablagen**, Paket M6 — `letzte` aus
  derselben Antwort, `letzteAus`) mit „Jetzt übertragen“/„Abbrechen“ → je Datei **nacheinander**
  (`schritt: 'datei'`, Fortschritt) → Ergebnisliste (Stand als Text und Symbol, Link je Knoten über
  `host.link`) → `vorgang.json` (`schritt: 'abschluss'`) → „Im Chat weitermachen“ (Antwort
  `aktion: "uebertragen"` mit `ablage{…}` — **nur Zahlen**, auch vorgemerkt). „Anhalten“ wirkt nach der
  laufenden Datei; „Nicht übertragene noch einmal senden“ schickt nur, was ein neuer Versuch heilen kann.
  Fähigkeit `hochladen` (für `ablegen`) und `oeffnen` (für die Links). Ohne https (kein `crypto.subtle`)
  der Code `unsicher`.
- **Texte** (`upload-texte.ts`, `upload-uebertragen-texte.ts`): Deutsch und Englisch, Zahlen und Größen
  über `Intl`.
- Backend: Dienst `upload_angebot` (`backend/src/boerdi/ui_module/dienst_upload.py`), Antwortform
  (`ui_module/upload_antwort.py`, Rahmen `[ORDNER …]` bzw. `[DOKUMENT DER PERSON …]`), Entwurf aus
  Ordnern (`ui_module/strukturentwurf_ordner.py`, `services/ordner_aktion.py`), Dokument lesen
  (`api/ui_dokumente.py`, `services/dokumente/`), Entwurf aus dem Dokument
  (`ui_strukturentwurf` mit `aus_dokument`, `services/strukturentwurf_dienst.py`), Ablage im persönlichen
  Bereich (`api/ui_ablage.py`, `services/ablage/`, Rahmen `[ABLAGE DER PERSON …]`).
