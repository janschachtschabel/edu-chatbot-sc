# Rückmeldung an MCP und Flow-Autoren: eigene Inhalte löschen, Umwandlungs-Flow (2026-11-20)

Anlass: Im Chatbot ist mit dem Plan „Upload-Ort und Erschließung“
([`plans/2026-11-20-upload-ort-und-erschliessung.md`](plans/2026-11-20-upload-ort-und-erschliessung.md),
noch nicht ausgerollt) „In WLO ablegen und erschließen“ der Normalfall geworden — auch für Lehrpläne,
die im Ablauf „Themenbaum erstellen“ nur die Gliederung liefern. Daraus entstehen zwei Wünsche. Beide
sind nicht dringend; der Chatbot läuft ohne sie. Gelesen wurde dein Stand in `wlo-mcp-server-sc`;
gemessen ist für diese Rückmeldung nichts.

## 1 An den MCP-Entwickler: eigene Inhalte löschen

**Wofür:** Am Ende von „Themenbaum erstellen“ möchten wir fragen: **„Gliederungsdatei behalten oder aus
WLO löschen?“** Ein Lehrplan, den die Person nur als Gliederung hochgeladen hat, liegt danach als
Inhalt in ihrem persönlichen Bereich. Manche wollen ihn dort nicht behalten. Heute bleibt er liegen,
weil wir dafür kein passendes Werkzeug haben.

**Warum nicht `wlo_delete_content`:** Das Werkzeug löscht jeden Datensatz, den die angemeldete Person
löschen darf — bei Konten mit Redaktionsrechten also weit mehr als die eigenen Uploads. Der Chatbot
schließt es darum in Abläufen aus (eigener Entscheid R-E1). Für den Fall oben brauchen wir etwas
Engeres, das der Server selbst begrenzt.

**Wunsch:** ein Werkzeug (Name nach deiner Wahl, etwa `wlo_delete_own_content`, oder ein Modus des
bestehenden Werkzeugs), das nur löscht, wenn **der Server** prüft:

1. Der Knoten ist ein Datensatz (`ccm:io`), keine Sammlung, kein Ordner, keine Sammlungs-Verknüpfung.
2. Ihn hat **die angemeldete Person selbst angelegt** (Ersteller = Aufrufer).
3. Er liegt **in ihrem persönlichen Bereich** (Hauptelternknoten dort, etwa der Ordner einer
   Stapel-Ablage) — nicht in einem geteilten Bereich.
4. Vorschlag: Er ist in keiner Sammlung verwendet und nicht veröffentlicht; sonst ablehnen mit eigenem
   Code statt still mitzulöschen.

Gern zweistufig wie die übrigen schreibenden Werkzeuge (Vorschau, dann `confirmToken`), mit eigenen
Ablehnungs-Codes je verletzter Bedingung (etwa `not_own`, `not_in_home`, `in_use`) und `not_found`
für schon Gelöschtes. Ideal wäre eine Liste von `nodeIds` je Aufruf mit Ergebnis je Knoten — eine
Ablage hat bis zu fünf Gliederungen.

**Was der Chatbot dazu tut:** Er ruft das Werkzeug nur nach einem ausdrücklichen Klick der Person auf
„Aus WLO löschen“ und nur für Knoten, die dieser Upload als Gliederung neu angelegt hat (dieselbe
Bindung wie bei der Zustimmung zum Metadaten-Flow). Ohne das Werkzeug bietet er die Frage nicht an.

## 2 An die Autoren der Kestra-Flows: Umwandlungs-Flow (Wunsch E15)

**Wofür:** Für einen Themenbaum aus einem Lehrplan braucht der Chatbot die **Gliederung** des
Dokuments (Überschriften und ihre Ebenen). Der Volltext des Repositoriums (`textContent`) ist in der Regel
flacher Text, in dem die Überschriften nicht mehr als solche erkennbar sind; liest der Chatbot ein Dokument selbst („Nur hier im Chat lesen“), wandelt er
es in Markdown mit Gliederung um. Für Dokumente, die in WLO liegen, fehlt dieser Weg.

**Wunsch:** ein Flow, der für einen Datensatz (`nodeId`, mit den Rechten der Person) die Datei in
**Markdown mit Gliederung** umwandelt (Überschriften `#`, `##`, … aus der Dokumentstruktur, Listen und
Tabellen möglichst erhalten) und das Ergebnis als **Datei oder Text** ausgibt — als Ausgabe des Jobs
(dann lesen wir sie über den MCP, Vorschlag W5 `wlo_flow_file` aus der Liste vom 17.11.) oder als
Anhang am Datensatz. Eingaben und Ausgaben liegen bei Kestra 30 Tage; für private Lehrpläne bitte
nichts darüber hinaus speichern.

Auf der Seite des Chatbots ist die Stelle vorbereitet: Ein Flow wird dort als Auftragsschritt im
Ablauf eingetragen und im Studio freigegeben; Code ändern wir dafür nicht.

## 3 Zum Flow `edusharing.chatbot/node-metadata-write` (bekannt, nur zur Erinnerung)

- **Titel wird überschrieben:** Der Flow ersetzt den Titel der Datei. Wir haben das angenommen und
  sagen es der Person jetzt vorher, am Häkchen „Metadaten von WLO erzeugen lassen“: „WLO setzt dabei
  Titel, Beschreibung, Fach, Stufe und Schlagworte neu – der Dateiname bleibt nicht der Titel.“ Der
  Vorschlag, einen vorhandenen Titel stehen zu lassen, bleibt bestehen.
- **jobId in `ccm:version_comment`:** unverändert offen, siehe
  [`mcp-rueckmeldung-2026-11-20-volltext-status.md`](mcp-rueckmeldung-2026-11-20-volltext-status.md) §4.

Danke fürs Lesen — Rückfragen gern an das Chatbot-Team.
