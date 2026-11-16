# Der WLO-Weg für eigene Inhalte ist ab Werk an (2026-11-16)

Anlass: Rückmeldung vom 16.11.:

> „Das Hochladen und Anlegen der Knoten soll der MCP machen […] der Kestra-Flow braucht als Input
> die node id. Die Volltexte werden innerhalb von Kestra / dem Repo erzeugt und auch die Metadaten.
> Der Chatbot sollte sie danach holen und nutzen. Wenn das dreifach ausgeschaltet ist, sollte man
> es aktivieren und die Voraussetzungen kommunizieren.“

Paket TG-0 im Plan `docs/plans/2026-11-16-themenbaum-generisch.md`.

## Der Weg (gebaut seit U3-3, K1 und R1)

1. **Upload-Feld:** Es legt die Dateien über die Stapel-Werkzeuge des MCP im persönlichen Bereich
   der Person in WLO an. Daraus entsteht der Teil `ablage` mit den node_ids.
2. **Ablauf „Themenbaum · aus eigenen Inhalten“:** Er startet auf Wunsch der Person den
   Kestra-Flow `edusharing.chatbot/node-metadata-write` mit diesen node_ids, in Blöcken zu 50.
   Volltexte und Metadaten entstehen im Repositorium bzw. in Kestra.
3. **Zurückholen:** `metadaten_lesen` holt die Ergebnisse, und `ui_strukturentwurf` baut daraus
   den Themenbaum-Entwurf.

## Was sich ändert

### Ab Werk an

- **Die Ablage in WLO:** `ablage_in_wlo: true` (Vorgabe des Modells, Seed `01-base/upload-config`).
  - Angeboten wird sie nur, wenn der MCP-Server die Stapel-Ablage (`wlo_prepare_file_batch`) führt,
    über die Fähigkeitsabfrage `services/mcp/faehigkeiten.kennt_werkzeug`.
  - Vorher wäre sie angezeigt worden und erst nach der Vorschau gescheitert.
- **Der Metadaten-Flow:** Er gilt als **Werksvorgabe im Code** (`auftraege/client.WERKSVORGABE`),
  wenn weder das Studio etwas freigibt noch `B_API_JOBS_FLOWS` gesetzt ist.
  - Der Seed `01-base/kestra-flows` bleibt leer. Review M1/M2: Ein Seed-Eintrag wirkte als
    Studio-Liste.
  - Folgen eines Seed-Eintrags wären gewesen: Einer Anlage mit gesetzter Variable hätte der
    `migrate`-Dienst beim Start still alle anderen Flows genommen. Fehlte der Flow in der
    Variable, wären alle Aufträge aus gewesen. Werksabgleich und Werkszustand wären mit 400
    gescheitert.
- **Der Ablauf „Themenbaum · aus eigenen Inhalten“:** `aktiv: true`.
- **Folge der Werksvorgabe:** Aufträge gelten ab Werk als eingerichtet (`client.freigeschaltet()`),
  vorher erst nach einer Freigabe.
  - Zur Laufzeit braucht ein Auftrag weiter die Anmeldung und den durchgereichten Schlüssel der
    Person, sonst nimmt der Schritt `bei_fehler`.
  - Die Probe im Studio lässt einen nicht freigegebenen Flow jetzt scheitern wie im Betrieb.
  - Wer Aufträge ganz abschalten will, stellt im Studio die Kestra-Freigabe auf „aus“. Eine
    ausgeschaltete Freigabe schlägt die Werksvorgabe.

### Die Voraussetzungen werden genannt, statt den Weg zu verstecken

- **Upload-Feld:** Ohne WLO-Anmeldung steht dort, vor und nach dem Erfassen: „Dateien in deinen
  persönlichen Bereich in WLO übertragen – dort entstehen Volltexte und Metadaten – geht, wenn du
  bei WLO angemeldet bist.“ Dafür gibt es den neuen Systemschalter `ablage_nach_anmeldung`, nach
  dem Muster von `lesen_nach_anmeldung`.
- **KI:** Die Quittung des Felds sagt nicht mehr „hochgeladen wird dabei nichts“. Sie nennt die
  Ablage oder ihre Voraussetzung. Die Beschreibung im Manifest ist entsprechend angepasst.
- **Ablauf:**
  - Der Einstieg sagt, wohin die Dateien kommen und dass Volltexte und auf Wunsch Metadaten
    einige Minuten brauchen.
  - Ohne Dateien in WLO kommt kein Ende mehr, sondern ein neuer Versuch („Nochmal auswählen“ /
    „Beenden“). Der Text nennt den eigentlichen Grund: „Senden“ schickt nur die Übersicht.
  - Scheitert der Flow, nennt der Text die möglichen Gründe: nicht eingerichtet, nicht
    freigegeben, Zugang darf ihn nicht starten, nicht erreichbar.
  - Ohne Anmeldung nennt der Ablauf die Anmeldung, wie bisher (`voraussetzungen`).
- **Studio:** Die Hinweise am Schalter und am Abschnitt „Hochladen“ beschreiben den ganzen Weg.

### Prüfung der Abläufe

Ein nicht freigegebener Kestra-Flow sperrt einen eingeschalteten Ablauf nur noch, wenn sein
Auftragsschritt keinen Ersatzweg (`bei_fehler`) hat.
- **Mit Ersatzweg** ist es ein Hinweis unter „Prüfen“: „bis dahin nimmt der Schritt den Ersatzweg
  …“.
- **Entziehen einer Freigabe:** Dieselbe Regel gilt beim Entziehen im Studio (Review m4).
- **Grund:** Wo `B_API_JOBS_FLOWS` den Flow nicht enthält oder die b-api keine Aufträge
  einrichtet, scheiterten sonst Werksabgleich und Speichern.
- **Zur Laufzeit** startet der Auftrag dann nicht, und der Schritt nimmt `bei_fehler`. Das Review
  hat das für alle Fälle bestätigt: kein Start-Pfad, Flow nicht erlaubt, keine Anmeldung, kein
  Schlüssel, Aufteilung.
- **Hingenommen (Review m3):** Ein eigener Ablauf mit Ersatzweg erscheint in der Liste ohne
  Befund, obwohl sein Auftrag nie läuft. Die Warnung steht unter „Prüfen“.

### Unverändert

- Geschrieben wird nur mit bestätigter Anmeldung. Alle drei Ablage-Endpunkte und der Auftrag
  prüfen `has_personal_auth`.
- Der Metadaten-Flow läuft erst nach der Rückfrage im Chat (`repo_schreibt`).

## Voraussetzungen im Betrieb

- **MCP:** Der MCP-Server führt die Stapel-Ablage. Sonst bietet das Feld die Ablage nicht an.
- **b-api:** Aufträge sind eingerichtet. Der Flow läuft mit dem durchgereichten Schlüssel der
  Person, also hinter dem b-api-Proxy, nie mit `B_API_KEY`.
- **`B_API_JOBS_FLOWS`:** Ist die Variable gesetzt, ist sie maßgeblich. Wer den Ablauf nutzen
  will, nimmt `edusharing.chatbot/node-metadata-write` dort auf oder gibt ihn im Studio frei.
- **Datenschutz:** Eingaben und Ausgaben eines Auftrags liegen bei Kestra 30 Tage im Klartext,
  hier die erzeugten Metadaten privater Dateien. Die Werksvorgabe setzt das voraus. Wer das nicht
  will, setzt `B_API_JOBS_FLOWS` ohne den Flow oder schaltet die Kestra-Freigabe im Studio aus.

## Geprüft

- **Unabhängiges Review:** 2 MAJOR, 6 MINOR, 4 NIT.
  - Behoben: M1, M2 (Werksvorgabe im Code), m4 (Wächter beim Entziehen), m5 (Texte an die KI),
    m6 (MCP-Fähigkeit), m7 (neuer Versuch statt Ende), m8 (Doku), n9 (Texte), n10 (Tests), n11
    (Hinweis auch nach dem Erfassen), n12 (Datenschutz in den Voraussetzungen).
  - Hingenommen: m3, siehe oben.
- **Backend:** Upload-, Ablage-, Kestra-, Ablauf- und Seed-Tests grün. Die Simulation aller
  Selbsttests von „aus eigenen Inhalten“ ist grün, die Prüfung ohne Befund.
- **`ui-module` und `studio`:** grün. Das Schema fürs Studio und der API-Vertrag sind
  unverändert.
- **Nicht live geprüft:** Ablage und Flow gegen Staging.

## Deploy

- Image neu bauen. Keine Migration.
- `import-config --werksabgleich`. Er übernimmt Upload-Schalter und Ablauf, wenn sie auf Staging im
  Studio nicht angepasst wurden. Sonst im Studio einschalten:
  - Betrieb → Hochladen: „Inhalte in WLO ablegen“;
  - Abläufe → „Themenbaum · aus eigenen Inhalten“.
- Ist auf Staging `B_API_JOBS_FLOWS` gesetzt, muss der Flow darin stehen.
