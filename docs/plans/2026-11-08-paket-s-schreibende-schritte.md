# Paket S — schreibende Ablaufschritte mit Freigabe (2026-11-08)

Auftrag des Nutzers (2026-11-08): „… und geh dann zum nächsten Paket über“. Grundlage sind der Plan
[`2026-11-05-vorgang-und-ablaeufe.md`](2026-11-05-vorgang-und-ablaeufe.md) §6 („S Schreiben: `freigabe` an
`werkzeug`/`auftrag`, `ui_freigabe`, Schreib-Invariante am Start“) und der ältere Feinentwurf
[`2026-10-24-ablaeufe-und-ui-module.md`](2026-10-24-ablaeufe-und-ui-module.md) §6.11.

## Ziel

Ein Ablauf kann in WLO schreiben, etwa einen Volltext anhängen (W1), Metadaten ändern oder Inhalte einsortieren.
Das geht nur mit der **Freigabe der Person**, mit derselben Vorschau, Zustimmungsprüfung und Einlösung wie im
Chat. Der Treiber ruft nie selbst mit Schlüssel. Ein Modell setzt ihn nie.

## Entscheide (Empfehlung übernommen, Nutzer-Go „weiter mit dem nächsten Paket“)

| # | Frage | Entscheid |
|---|---|---|
| FS-1 | Eigenes Modul `ui_freigabe`? | **Nein.** Wiederverwendet werden die Vorschau-Box (`ui_inhaltsrahmen`, `schreib_vorschau`) und der Chip „Ja, so ausführen“ des Chats. Damit gibt es kein neues Bündel und keinen zweiten Weg der Zustimmung. Ein Klick oder ein „ja“ geht durch dieselbe Zustimmungsprüfung (Liste → Veto → LLM) und dieselbe Einlösung (`write_approval`). |
| FS-2 | Muss der Schritt `freigabe` ausdrücklich tragen? | **Ja** (§6.11). `freigabe: {de, en}` ist der Satz über der Vorschau. Die Prüfung weist jeden schreibenden Schritt ohne ihn ab und jeden `freigabe` an einem nicht schreibenden Werkzeug. |
| FS-3 | Welche Werkzeuge? | Nur **bestätigbare** kuratierende WLO-Werkzeuge (`CONFIRMABLE_TOOLS`), **keine Pläne** (`PLAN_TOOLS`). Pläne setzt „Plan fortsetzen“ über mehrere Züge fort, ein späteres Paket. Fremde MCP-Server bleiben gesperrt. |
| FS-4 | `freigabe` an `auftrag`? | **Später.** Die B-API erlaubt heute nur lesende Flows (`offene-befunde` §1); es gibt keinen schreibenden Flow, den man freigeben könnte. |
| FS-5 | Schreib-Invariante am Start | Ein Ablauf mit schreibendem Schritt braucht die Voraussetzung `anmeldung` (Prüfung). Vorgelegt und eingelöst wird nur mit `schreiben_erlaubt()`, wie im Chat. |
| FS-6 | Nein, abgelaufen, nichts geschrieben | Der Lauf wartet weiter. Unter jeder Antwort stehen „Vorschau erneut zeigen“ (neue Vorschau mit denselben, neu eingesetzten Angaben) und „Ablauf abbrechen“. |
| FS-7 | Ausgang offen (keine Antwort nach dem Ja) | Der Lauf **endet** mit Fehler, nicht über `bei_fehler`: Es kann geschrieben sein, ein Folgeschritt auf falscher Annahme wäre schlimmer. Der Text sagt „bitte in WLO nachsehen“, wie im Chat. |
| FS-8 | Abgelehnt (Server hat geantwortet, nichts geschrieben) | `bei_fehler`, sonst Ende mit Fehler — wie ein `werkzeug` ohne Ergebnis. Der Grund des Servers steht in der Antwort (`_GRUND_ZEIGEN`). |
| FS-9 | Ergebnis | Teil `schreibt` (wenn gesetzt) mit dem strukturierten Teil der Server-Antwort (`structuredContent`), sonst `{"text": …}`. „Nichts zu ändern“ gilt als Erfolg (`{"unveraendert": true}`). |

## Ablauf eines Freigabe-Schritts

1. Der Treiber erreicht `werkzeug` mit `freigabe`. Er setzt die Teile ein (Ziel = Werkzeug, also `darf()` und
   64 KB) und ruft `Umgebung.vorlegen(werkzeug, args)`: das Werkzeug **ohne** Schlüssel, deterministisch über
   `call_mcp_tool_antwort`. Der Schlüssel kommt aus `structuredContent.confirm` (sonst aus dem Text).
   - Fehler oder keine Antwort → `bei_fehler` bzw. Ende mit Fehler (es wurde nichts geschrieben).
   - Kein Schlüssel (nichts zu ändern) → Erfolg, weiter.
   - Sonst: `Ausgabe.freigabe = {werkzeug, args, schluessel, vorschau}`, Status **`wartet_freigabe`**, Halt.
2. Der Zug merkt die Abnahme wie die Werkzeug-Schleife (`remember_pending` mit Aufrufer, `merke_vorschau`), dazu
   die Marke `ablauf = {id, schritt}`. Er zeigt Satz, Vorschau-Box und Chip.
3. Folgezug „ja“: Der Vorlauf löst ein, wie im Chat (`redeem_write_approval`). Danach gibt eine Nachlauf-Naht
   (`ablauf/freigabe_zug.nach_einloesen`) das Ergebnis an den Treiber (`treiber.weiter_freigabe`):
   - Erfolg → Teil `schreibt`, nächster Schritt. Satz und Folge werden an die Antwort gehängt.
   - Abgelehnt → `bei_fehler` (FS-8).
   - Ausgang offen → Ende mit Fehler (FS-7).
   - Neu vorgelegt (Schlüssel abgelaufen) → die neue Abnahme trägt die Marke weiter.
   - Liegen gelassen (ausgelastet, Anmeldung unklar, Zustimmung unklar) → nichts, der Lauf wartet.
   - Verbraucht ohne Schreiben (Frist, `timeout_ohne_wirkung`) → der Lauf wartet, Knöpfe nach FS-6.
4. „Nein“ oder etwas anderes: `discard_stale_approval` verwirft die Abnahme wie heute, der Lauf wartet (FS-6).

## Teilpakete (je mit Review)

| Teil | Inhalt |
|---|---|
| **S1** | Feld `freigabe` (`NurBei werkzeug`, Vorgabe `None`, `""` → `None`); Prüfung: schreibend nur mit `freigabe`, bestätigbar, kein Plan, Voraussetzung `anmeldung`, `freigabe` nur an schreibendem Werkzeug; `_wartet`. Studio: Feldtexte, Schrittfolge. |
| **S2** | Treiber: `Umgebung.vorlegen`, `wartet_freigabe` (Status in Treiber, `zug_basis`, `zug`, `vorgaenge`), `weiter_freigabe`; Zug: Abnahme merken und zeigen; Knöpfe „Vorschau erneut zeigen“ und „Ablauf abbrechen“ samt Direktaktionen. |
| **S3** | Nachlauf nach dem Einlösen (`freigabe_zug.nach_einloesen` im Vorlauf); Ergebnis als Teil; Ende bei offenem Ausgang; Doku (`architektur.md`, `ablaeufe`-Doku, offene Liste). |

**Stand 2026-11-08:** S1–S3 umgesetzt und reviewt (zwei Reviews, Notiz
[`aenderungen/2026-11-08-paket-s-schreibende-schritte.md`](../aenderungen/2026-11-08-paket-s-schreibende-schritte.md)).
Zusatz aus dem Review: kein Löschen aus einem Ablauf (Entscheid des Nutzers offen); ein Ausfall beim Vorlegen lässt
den Lauf warten statt `bei_fehler`.

## Fallen (aus der Karte)

- Neue Felder an `Schritt` mit Vorgabe `None`, sonst ändert sich `treiber.fassung` jedes Ablaufs.
- Ein neuer Wartezustand muss in `zug_basis.STATUS`/`_WARTEND`, `zug.lauf_wartet`, `vorgaenge.WARTEND`,
  `pruefung._wartet` und den Knöpfen stehen.
- Direktaktionen und Modul-Antworten verwerfen eine offene Abnahme (`discard_stale_approval`), das ist gewollt.
  Die Knöpfe nach FS-6 sind Direktaktionen und brauchen keine offene Abnahme.
- Der Schlüssel geht nie ins Modell und nie ins Protokoll; die Vorschau-Box zeigt den redigierten Text.
- Vor Netzaufrufen `basis.frei(session)` (M7).
