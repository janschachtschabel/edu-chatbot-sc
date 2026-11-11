"""What the bot says without asking a model (C1-f2b).

A second catalogue beside ``messages.py``, deliberately not merged with it: that
one carries the ``detail`` of an HTTP error, read by an editor in the studio,
and picks its language from ``Accept-Language``. These sentences are the bot's
own voice in the chat, read by the end user, and follow ``environment.locale``
— the same source as the LLM answer (C1-f1). Different audience, different
trigger; only the rendering is shared (``i18n/catalogue``).

Deliberately NOT in here:

* text that goes INTO a prompt rather than to the user — e.g. the
  ``"(Die Sammlung enthält aktuell keine Inhalte.)"`` placeholder that
  ``direct_actions`` hands to the curation LLM as the IST list. That is prompt
  material and stays German by the C1 decision.
* the regexes and keyword lists that READ German text. They are tools, not
  sentences — a regex has no translation, it has a per-language counterpart.
  Those that read OUR OWN output live beside their code
  (``i18n/output_patterns`` when two modules share them, otherwise next to
  their only consumer — ``services/canvas_fast_path``,
  ``domain/inline_rendering``); those that read the USER's message are still
  German-only, a known gap (C1-f2c).

**The quick replies are chips the user clicks, and the click sends their text
back as a message.** They still work in English because the pattern is chosen by
the classifier, not by matching the phrase: ``trigger_phrases`` is handed to the
model as data (``pattern_engine.py:243``), never matched as a pattern. Keep the
translations semantically equivalent anyway — the classifier maps meaning.

**A magic word stays in the original in every language.** ``material.askType``
tells the user to write "Automatisch" — that string is a key in
``05-canvas/type-aliases.yaml``, which ``resolve_material_type`` looks up, and
the table is German-only. Translated, the sentence would give an instruction the
system cannot carry out. Same rule as for proper nouns and quoted titles.

simplify: one flat module, by now for five surfaces — ``content.``/``action.``
(direct actions), ``material.``/``completion.`` (canvas), ``links.`` (the
type-focus search pointer), ``guide.`` (the bring-me-there labels) and
``inline.`` (the title above the inline box). The key
prefix is the seam to split along into a ``bot_text/`` package; the parity
guards in ``tests/test_i18n_bot_text.py`` survive that unchanged as long as the
package merges the parts back into one ``BOT_TEXT``. Worth doing once this file
passes ~500 lines — below that the split costs more attention than it saves.
"""

from typing import Final

from boerdi.i18n.catalogue import Catalogue, render
from boerdi.i18n.locale import Locale

BOT_TEXT: Final[Catalogue] = {
    "de": {
        # ── M17: Volltext eines Materials ──────────────────────────────
        "content.missingNode": "Mir fehlt die Angabe, welches Material ich öffnen soll.",
        "content.mcpUnreachable": (
            "Den Volltext konnte ich gerade nicht laden — die Materialsuche "
            "war nicht erreichbar. Versuch es bitte gleich noch einmal."
        ),
        # Zwei Schlüssel statt einer Komposition: die Anführungszeichen sind
        # sprachabhängig („…" vs “…”), und ein zusammengesetzter Satz würde sie
        # im Code festschreiben.
        "content.aboutMaterial": "Zum Material: ",
        "content.aboutMaterialNamed": "Zum Material „{title}“: ",
        "content.reason.accessDenied": (
            "Dieses Material ist **nicht frei zugänglich** — den Volltext gibt die "
            "Quelle nur angemeldeten Nutzer:innen heraus."
        ),
        "content.reason.noTextNoUrl": (
            "Zu diesem Material liegt kein Text vor, den ich anzeigen könnte — es "
            "gibt weder eine Textfassung noch eine abrufbare Quelle."
        ),
        "content.reason.extractionFailed": (
            "Der Text dieses Materials ließ sich gerade nicht auslesen. Das ist ein "
            "technisches Problem, kein Rechteproblem — ein zweiter Versuch kann "
            "klappen."
        ),
        "content.reason.nodeNotFound": (
            "Dieses Material finde ich nicht mehr — womöglich wurde es "
            "zurückgezogen oder verschoben."
        ),
        "content.reason.noEnvelope": (
            "Die Antwort der Materialsuche kam in einer Form, die ich nicht lesen "
            "konnte. Ich zeige den Inhalt lieber gar nicht als halb geraten."
        ),
        "content.reason.unknown": "Den Volltext dieses Materials konnte ich nicht laden.",
        "content.source": "Quelle: {url}",
        "content.lead": "Hier ist der Inhalt von „{title}“.",
        "content.truncated": (
            " Der Text ist sehr lang und deshalb **gekürzt** — der Anfang "
            "steht vollständig da, das Ende fehlt."
        ),
        "content.fallbackTitle": "Inhalt",
        "content.qr.createOwn": "Erstell mir stattdessen ein eigenes Material dazu",
        "content.qr.freeAlternatives": "Suche frei zugängliche Alternativen",
        "content.qr.shorter": "Mach den Text kürzer",
        "content.qr.simpler": "Formuliere es einfacher",
        "content.qr.similar": "Ähnliche Materialien zeigen",
        # ── Direkt-Aktionen auf einer Sammlung ─────────────────────────
        "action.collectionFallbackTitle": "Sammlung",
        "action.missingCollectionId": "Keine Sammlungs-ID angegeben.",
        "action.browse.header": "**{title}** — Ergebnisse {range}{total}:",
        "action.browse.ofTotal": " von {total}",
        "action.browse.empty": 'In der Sammlung "{title}" habe ich leider keine Inhalte gefunden.',
        "action.browse.loadFailed": (
            'Fehler beim Laden der Inhalte von "{title}". Versuch es bitte noch einmal.'
        ),
        "action.browse.canvasTitle": "Inhalte: {title}",
        "action.browse.canvasTitleFallback": "Sammlungs-Inhalte",
        # Paket U1-e: „Unterthemen öffnen“ im Themenbaum (Direktaktion show_collection_tree).
        # Ohne Titel (Review U1-e, Befund 11): die Überschrift trägt der Block darunter.
        "action.tree.header": "Hier sind die Unterthemen:",
        "action.tree.loadFailed": (
            'Die Unterthemen von "{title}" ließen sich nicht laden. Versuch es bitte noch einmal.'
        ),
        # Paket U1-f: der Themenbaum ist im Studio abgeschaltet (Seite „UI-Module“).
        "action.tree.inactive": (
            'Die Ansicht „Themenbaum“ ist abgeschaltet — die Unterthemen von "{title}" kann ich '
            "hier nicht öffnen."
        ),
        # Paket U2: „Als Entwurf bearbeiten“ im Themenbaum (Direktaktion edit_collection_as_draft).
        "action.draft.header": (
            'Die Gliederung von "{title}" als Entwurf — unten bearbeiten, herunterladen oder '
            "übernehmen."
        ),
        "action.draft.loadFailed": (
            'Die Gliederung von "{title}" ließ sich gerade nicht als Entwurf laden.'
        ),
        "action.draft.ohneTitel": "Gliederung aus WLO",
        "action.draft.inactive": (
            'Entwürfe sind hier abgeschaltet — die Gliederung von "{title}" kann ich nicht als '
            "Entwurf öffnen."
        ),
        # Paket U3-1b: „Als Themenbaum-Entwurf übernehmen“ in ui_upload.
        "action.folderDraft.header": (
            'Die Ordnerstruktur von "{title}" als Entwurf — unten bearbeiten, herunterladen oder '
            "übernehmen."
        ),
        "action.folderDraft.empty": (
            'In "{title}" gibt es keine Unterordner, aus denen ein Themenbaum werden könnte.'
        ),
        "action.folderDraft.ohneTitel": "Gliederung aus Ordnern",
        "action.folderDraft.inactive": (
            'Entwürfe sind hier abgeschaltet — die Ordnerstruktur von "{title}" kann ich nicht als '
            "Entwurf öffnen."
        ),
        # Paket A1: Abläufe aus dem Katalog (``services/ablauf/zug``).
        "action.ablauf.unbekannt": "Diesen Ablauf gibt es hier nicht oder er ist ausgeschaltet.",
        "action.ablauf.wahlVeraltet": (
            "Diese Wahl gilt nicht mehr — der Ablauf steht inzwischen woanders."),
        "action.ablauf.anmeldung": "Für diesen Ablauf melde dich bitte bei WLO an.",
        "action.ablauf.startdaten": (
            "Dieser Ablauf braucht passende Startdaten von der Seite, in die der Chat eingebettet "
            "ist — so kann er nicht starten."),
        "action.ablauf.laeuftSchon": (
            "Dieser Ablauf läuft hier schon — es geht weiter, wo er steht."),
        # AS-Ua: neutral — auch ein Vorschlag der KI löst die Rückfrage aus (AS-5).
        "action.ablauf.ersetzen": (
            "Ein Ablauf soll starten, aber in diesem Gespräch läuft noch einer. Ein Neustart "
            "beendet den laufenden (auch einen Auftrag, auf den er wartet). Willst du neu "
            "starten?"),
        "action.ablauf.keinLauf": "In diesem Gespräch läuft gerade kein Ablauf.",
        "action.ablauf.abbrechenFrage": (
            "Den Ablauf wirklich abbrechen? Das lässt sich nicht zurücknehmen; ein Auftrag, auf "
            "den er wartet, endet mit. Was schon gesammelt ist, bleibt im Arbeitsstand."),
        # Browser-Abnahme AS-U, L-2: neben den Chips des Schritts muss der Satz sagen, wofür sie
        # stehen, und der Knopf darf nicht wie eine zweite Zusage („Ja, …“) klingen.
        "action.ablauf.abbrechenFrageZurueck": (
            "Den Ablauf wirklich abbrechen? Das lässt sich nicht zurücknehmen; ein Auftrag, auf "
            "den er wartet, endet mit. Was schon gesammelt ist, bleibt im Arbeitsstand. Willst du "
            "lieber weitermachen, wähle eine andere Antwort."),
        "action.ablauf.abbrechenJa": "Ablauf abbrechen",
        "action.ablauf.abgebrochenPerson": "Der Ablauf ist abgebrochen.",
        "action.ablauf.neuStarten": "Neu starten",
        "action.ablauf.ersetzenOhneKnopf": (
            "Die Seite möchte einen Ablauf starten, aber in diesem Gespräch läuft noch einer. "
            "Beende ihn zuerst („Neues Vorhaben“), dann kann die Seite neu starten."),
        "action.ablauf.konflikt": (
            "Dein Arbeitsstand wurde gerade an anderer Stelle geändert. Bitte versuche es "
            "noch einmal."),
        "action.ablauf.fehler": "An dieser Stelle kommt der Ablauf nicht weiter.",
        "action.ablauf.weiter": "Weiter geht's.",
        "action.ablauf.fertig": "Der Ablauf ist abgeschlossen.",
        "action.ablauf.weiterKnopf": "Weiter im Ablauf",
        "action.ablauf.dochMitAblauf": "Doch mit Ablauf",
        "action.ablauf.auftragKnopf": "Stand prüfen",
        "action.ablauf.freigabeErneutKnopf": "Vorschau erneut zeigen",
        "action.ablauf.freigabeAbbrechenKnopf": "Ablauf abbrechen",
        "action.ablauf.freigabeAbgebrochen": (
            "Der Ablauf ist abgebrochen — in WLO wurde nichts geändert."),
        "action.ablauf.freigabeAbgebrochenPlan": (
            "Der Ablauf ist abgebrochen. Was der Plan schon erledigt hat, bleibt in WLO; "
            "fortgesetzt wird er nicht."),
        "action.ablauf.freigabeOhneAnmeldung": (
            "Zum Ändern in WLO brauche ich deine Anmeldung — geändert wurde nichts."),
        "action.ablauf.freigabeSpaeter": (
            "Die Vorschau ließ sich gerade nicht holen (WLO ausgelastet, keine Antwort oder die "
            "Anmeldung abgewiesen) — geändert wurde nichts. Versuche es gleich mit „Vorschau "
            "erneut zeigen“."),
        "action.ablauf.freigabeAbgelaufen": (
            "Die Vorschau ist abgelaufen — geändert wurde nichts. Hol sie dir mit „Vorschau "
            "erneut zeigen“ neu."),
        "action.ablauf.freigabeKonflikt": (
            "Die Änderung ist in WLO gespeichert, aber der Ablauf ließ sich gerade nicht "
            "fortschreiben — er endet hier. Starte ihn neu, falls noch Schritte fehlen."),
        "action.ablauf.freigabeNichtMehrOffen": (
            "Diese Vorschau gehört zu einem Ablauf, der nicht mehr darauf wartet (abgebrochen oder "
            "neu vorgelegt) — geändert wurde nichts."),
        "action.ablauf.freigabeVorbereitet": (
            "Die Änderung ist vorbereitet, die Seite führt sie aus. Der Ablauf endet hier — starte "
            "ihn danach neu, falls noch Schritte fehlen."),
        "action.ablauf.auftragAbbrechenKnopf": "Auftrag abbrechen",
        "action.ablauf.auftragAbbrechenJa": "Ja, abbrechen",
        "action.ablauf.auftragAbbrechenFrage": (
            "Soll ich den laufenden Auftrag wirklich abbrechen? Sein Ergebnis kommt dann nicht "
            "mehr, und der Ablauf endet hier."),
        "action.ablauf.auftragAbgebrochen": "Der Auftrag ist abgebrochen, der Ablauf endet hier.",
        "action.ablauf.auftragSchonBeendet": "Dieser Auftrag läuft nicht mehr.",
        "action.ablauf.auftragNurHierAbgebrochen": (
            "Der Ablauf endet hier. Den Auftrag selbst konnte ich ohne deine Anmeldung nicht "
            "beenden — er läuft bis zu seinem Ende weiter, sein Ergebnis holt hier aber niemand "
            "mehr ab."),
        "action.vorgang.neuFrage": (
            "Gerade läuft noch ein Auftrag. Fängst du neu an, breche ich ihn ab, und sein Ergebnis "
            "kommt nicht mehr. Trotzdem neu beginnen?"),
        "action.vorgang.neuJa": "Ja, neu beginnen",
        "action.ablauf.auftragGesperrt": (
            "Während dieser Auftrag läuft, geht es hier erst weiter, wenn er fertig ist. Tippe auf "
            "„Stand prüfen“ — oder brich ihn ab."),
        "action.ablauf.auftragGestartet": "Ein Auftrag läuft im Hintergrund.",
        "action.vorgang.neu": (
            "Gut, wir fangen neu an. Dein bisheriger Arbeitsstand ist abgeschlossen."),
        "action.vorgang.geloescht": "Dein Arbeitsstand ist gelöscht.",
        "action.vorgang.keiner": "Gerade gibt es keinen Arbeitsstand.",
        "action.vorgang.neuKnopf": "Neues Vorhaben",
        "action.vorgang.loeschenKnopf": "Arbeitsstand löschen",
        "action.vorgang.loeschenFrage": (
            "Soll ich deinen Arbeitsstand wirklich löschen? Dazu gehören alle gespeicherten "
            "Vorhaben, auch abgeschlossene, und das hochgeladene Dokument dieser Sitzung. Das "
            "lässt sich nicht rückgängig machen."),
        "action.vorgang.loeschenJa": "Ja, löschen",
        "action.ablauf.auftragAbgewiesen": (
            "Den Stand dieses Auftrags darf ich mit deiner Anmeldung nicht abrufen. Melde dich "
            "bitte neu an und starte den Ablauf noch einmal."),
        "action.ablauf.auftragLaeuft": (
            "Der Auftrag läuft noch. Schau gern später wieder nach — tippe dann auf "
            "„Stand prüfen“."),
        "action.ablauf.auftragNichtAbrufbar": (
            "Den Stand des Auftrags kann ich gerade nicht abrufen. Versuch es bitte gleich noch "
            "einmal."),
        "action.ablauf.dateienSpaeter": (
            "Der Auftrag ist fertig, aber seine Dateien konnte ich gerade nicht holen. Tippe bitte "
            "gleich noch einmal auf „Stand prüfen“."),
        "action.ablauf.fehltNoch": (
            "Für den nächsten Schritt fehlt noch etwas. Arbeite gern noch an diesem Schritt weiter "
            "und tippe dann wieder auf „Weiter im Ablauf“."),
        "action.curate.searchPill": "Fehlende Inhalte zu {title} suchen",
        "action.curate.searchPillPlain": "Fehlende Inhalte suchen",
        "action.curate.noCompendium": (
            'Die Sammlung „{title}" hat keinen kompendialen Text hinterlegt, '
            "daher kann ich nicht zuverlässig abgleichen, was inhaltlich noch "
            "fehlt. Ich kann dir aber die vorhandenen Inhalte zusammenfassen "
            "oder gezielt passende Materialien suchen."
        ),
        "action.lp.resetNotice": (
            "_Hinweis: Es waren keine neuen Inhalte verfügbar, "
            "deshalb wird die Auswahl jetzt wiederholt._"
        ),
        "action.lp.noContents": (
            'Leider keine Inhalte in der Sammlung "{title}" gefunden, '
            "aus denen ein Lernpfad erstellt werden koennte."
        ),
        "action.lp.failed": (
            'Fehler beim Erstellen des Lernpfads für "{title}". Versuch es bitte noch einmal.'
        ),
        # ── Material erstellen: Rückfragen, Fehler, Lösungen-Stub ───────
        # Das genannte Stichwort MUSS ein Alias aus
        # ``05-canvas/type-aliases.yaml`` sein, sonst gibt der Satz eine
        # Anweisung, die das System nicht ausführen kann. Bis C1-f2b6 hiess
        # es deshalb auch auf Englisch „Automatisch"; seit C1-g2e kennt die
        # Aliasliste ``automatic``, also darf der Satz sagen, was der Chip
        # daneben zeigt.
        "material.askType": (
            "Welches Material soll ich dir zum Thema **{topic}** erstellen? "
            "Waehle einen Typ aus den Vorschlaegen oder schreib \"Automatisch\", "
            "damit ich den passenden Typ selbst waehle."
        ),
        "material.askTopic": (
            "Gerne erstelle ich dir ein Material. Zu welchem **Thema**? "
            "Beispiel: \"Erstelle ein Arbeitsblatt zur Photosynthese für Klasse 6\"."
        ),
        "material.genFailed": (
            "Ich konnte das **{label}** zum Thema *{topic}* gerade "
            "nicht erstellen. Versuch es nochmal — "
            "meistens klappt es beim zweiten Anlauf. (Fehlernummer: {nummer})"
        ),
        "material.createFailed": "Fehler beim Erstellen (Fehlernummer: {nummer})",
        "material.solutionsStub": (
            "## Lösungen\n\n"
            "_Lösungen werden ergänzt — du kannst mir "
            "antworten mit \"Lösungen ergänzen\", "
            "dann fülle ich den Block aus._"
        ),
        # ── Fertig-Blasen für Material und Lernpfad ─────────────────────
        # Die ``.du``/``.sie``-Paare bilden die deutsche Höflichkeitsform ab
        # (``formality`` aus dem Pattern-Output). Englisch kennt sie nicht —
        # dort stehen absichtlich zweimal dieselben Sätze, damit der Aufrufer
        # nicht sprachabhängig verzweigen muss.
        "completion.canvas.lead.du": (
            "Ich habe dir ein **{label}** zum Thema *{topic}* erstellt."
        ),
        "completion.canvas.lead.sie": (
            "Ich habe Ihnen ein **{label}** zum Thema *{topic}* erstellt."
        ),
        "completion.sections": "Abschnitte:",
        "completion.tasks": "Enthält **{count} Aufgaben**.",
        "completion.tasksWithSolutions": "Enthält **{count} Aufgaben** mit Lösungen.",
        "completion.canvas.outro.du": (
            "Du siehst es rechts im Canvas — ich kann es direkt anpassen, "
            "wenn du z.B. \"mach die Aufgaben einfacher\" oder \"füge Lösungen "
            "hinzu\" schreibst."
        ),
        "completion.canvas.outro.sie": (
            "Sie sehen es rechts im Canvas — ich kann es direkt anpassen, "
            "wenn Sie z.B. \"machen Sie die Aufgaben einfacher\" oder "
            "\"fügen Sie Lösungen hinzu\" schreiben."
        ),
        "completion.inline.outro.du": (
            "Das Material steht direkt unter dieser Nachricht — du kannst "
            "es mit dem Druck-Button als PDF speichern. Sag mir gerne, was "
            "angepasst werden soll (z.B. *\"mach die Aufgaben einfacher\"* "
            "oder *\"füge Lösungen hinzu\"*)."
        ),
        "completion.inline.outro.sie": (
            "Das Material steht direkt unter dieser Nachricht — Sie können "
            "es mit dem Druck-Button als PDF speichern. Geben Sie bitte "
            "Bescheid, falls Sie Anpassungen wünschen (z.B. *\"machen Sie "
            "die Aufgaben einfacher\"* oder *\"fügen Sie Lösungen hinzu\"*)."
        ),
        "completion.lp.lead.canvas": (
            "Ich habe dir den **Lernpfad zu *{topic}*** im Canvas rechts aufgebaut."
        ),
        "completion.lp.lead.inline": (
            "Ich habe dir den **Lernpfad zu *{topic}*** direkt unter dieser "
            "Nachricht aufgebaut."
        ),
        "completion.lp.phases": "Er ist in diese Phasen gegliedert:",
        "completion.lp.outro.canvas": (
            "Du kannst ihn im Canvas drucken, als Markdown speichern oder mir "
            "sagen, was angepasst werden soll (z.B. *\"mach ihn für Klasse 5 "
            "einfacher\"* oder *\"füge einen Schritt zur Sicherung hinzu\"*)."
        ),
        "completion.lp.outro.inline": (
            "Du kannst ihn mit dem Druck-Button unten als PDF speichern oder "
            "mir sagen, was angepasst werden soll (z.B. *\"mach ihn für "
            "Klasse 5 einfacher\"* oder *\"füge einen Schritt zur Sicherung "
            "hinzu\"*)."
        ),
        # ── Suchverweis bei Typ-Fokus + Ersatz-Beschriftungen ───────────
        # Das fehlende schließende Anführungszeichen hinter ``{topic}`` ist
        # ALT-verbatim (``f" zu „{_topic_for_text}"" "`` — das ASCII-Zeichen
        # beendet dort die f-Zeichenkette, statt sie zu schließen). Nach der
        # Regel „ALT-Wortlaut schlägt Rechtschreibung" bleibt es stehen;
        # Englisch erbt den Fehler nicht.
        #
        # ``.sie`` (GV-EMB-2, 2026-09-27): die Sie-Fassung, die ``turn_links``
        # nach ``formality`` wählt (``_SIE_FASSUNG``). Ohne Endung steht
        # weiter der ALT-Wortlaut im Du — deshalb kein ``.du``/``.sie``-Paar
        # wie bei ``completion.``. Die Sie-Fassung hat kein ALT-Vorbild und
        # schließt das Anführungszeichen.
        "links.typeFocus.ctaTopic": (
            "Für {label} zu „{topic} schau in die Suche unten — dort findest "
            "du die gefilterten Treffer."
        ),
        "links.typeFocus.ctaTopic.sie": (
            "Für {label} zu „{topic}“ schauen Sie in die Suche unten — dort "
            "finden Sie die gefilterten Treffer."
        ),
        "links.typeFocus.ctaPlain": (
            "Für {label} zum Thema schau in die Suche unten — dort findest "
            "du die gefilterten Treffer."
        ),
        "links.typeFocus.ctaPlain.sie": (
            "Für {label} zum Thema schauen Sie in die Suche unten — dort "
            "finden Sie die gefilterten Treffer."
        ),
        "guide.label.sourcePage": "Quell-Seite",
        "guide.label.learnMore": "Mehr erfahren",
        # ── Ersatztexte des Anti-Halluzinations-Wächters ────────────────
        # Alle drei werden MITTEN in einen bestehenden Satz gesetzt bzw.
        # ersetzen einen ganzen Satz; die abschließenden Leerzeichen sind
        # ALT-verbatim und Teil der Fügung — nicht wegräumen. Die
        # ``.sie``-Fassungen (s. oben) tragen sie aus demselben Grund.
        "links.claim.typeFocusCta": (
            "Für {label} zum Thema klick auf die Suche unten — dort findest "
            "du die gefilterten Treffer. "
        ),
        "links.claim.typeFocusCta.sie": (
            "Für {label} zum Thema klicken Sie auf die Suche unten — dort "
            "finden Sie die gefilterten Treffer. "
        ),
        "links.claim.fallbackLabel": "Materialien",
        "links.claim.searchHits": "passende Treffer in der Suche",
        "links.claim.searchPointer": (
            "Schau in die verlinkte Suche unten — dort findest du passende "
            "Treffer zum Thema. "
        ),
        "links.claim.searchPointer.sie": (
            "Schauen Sie in die verlinkte Suche unten — dort finden Sie "
            "passende Treffer zum Thema. "
        ),
        # ── Titel der Inline-Box (M09/M10/M11) ─────────────────────────
        # Der Box-Titel entsteht aus diesem Wort plus dem Thema
        # (``f"{label}: {topic}"``, ALT-verbatim). Er steht über der Box und
        # wird gelesen — anders als der Material-Typ, den das Modell selbst
        # geschrieben hat und den wir unverändert übernehmen.
        "inline.title.learningPath": "Lernpfad",
        "inline.title.material": "Material",
        "inline.title.editedVersion": "Bearbeitete Version",
        "inline.title.content": "Inhalt",
        # Die Box sagt nicht, dass etwas geändert WURDE — das steht als erste
        # Zeile im Text des Servers und wäre hier doppelt. Sie sagt, was der
        # Kasten IST: die Sache, über die entschieden wird.
        "inline.title.writePreview": "Änderung zur Abnahme",
        # Die Frage hat ZWEI Ausgänge, und der zweite steht ausdrücklich da:
        # ohne ihn ist die Vorschau eine Ja/Nein-Sperre statt eines Angebots.
        "inline.writePreview.frist": "Die Freigabe gilt {minuten} Minuten ab dieser Vorschau.",
        "inline.writePreview.ask": (
            "Soll ich das so ausführen? Wenn etwas nicht stimmt, sag mir, "
            "was anders sein soll."
        ),
        # Nur die Zustimmung bekommt einen Knopf. Ein „Ändern"-Knopf könnte nur
        # einen Satz senden, den der Nutzer selbst besser formuliert.
        "action.write.confirmChip": "Ja, so ausführen",
        # Paket 19 (Review 19-5): die freie Antwort auf die Vorschau ließ sich unter Last nicht
        # prüfen — die Vorschau steht erneut darunter, der Chip meint genau sie.
        "write.consentUnclear": (
            "Deine letzte Nachricht konnte ich deshalb nicht prüfen. Unten steht die Vorschau "
            "noch einmal — soll ich sie unverändert ausführen? Wolltest du etwas ändern, "
            "schreib es mir gleich noch einmal."
        ),
        # S5: die Abnahme lag vor, es kam keine bestätigte Rückmeldung.
        #
        # Der Satz sagte bis zum Review „es wurde nichts geändert" — eine
        # Behauptung, die an dieser Stelle **niemand belegen kann**: Ablehnung
        # und Zeitüberschreitung sehen für uns gleich aus (``transport`` macht
        # aus beidem dieselbe Fehler-Antwort). Bei einer Zeitüberschreitung NACH
        # dem Schreiben wäre der Satz falsch, die Person legte dieselbe Sache
        # ein zweites Mal an, und der kuratierte Bestand trüge eine Dublette.
        #
        # Deshalb sagt er jetzt genau so viel, wie feststeht — und nennt den
        # einen Schritt, der die Unsicherheit auflöst. Konservativ in die
        # richtige Richtung: nachsehen kostet eine Minute, eine Dublette bleibt.
        # Der Server hat geantwortet und abgelehnt. Hier DARF „nichts geändert"
        # stehen: der Beleg dafür ist seine Antwort. Seit Paket M2 folgt ein fachlicher
        # Grund (``write.rejectedReason``, nur für ``refused``/``invalid_input``/
        # ``not_found``/…); Repository-Interna bleiben im Protokoll.
        # Paket 10 (Kurzaudit S-1/S-3/S-4): Zustimmung zu einer Vorschau, die unter
        # einer anderen Anmeldung entstand (``services/abnahme_hinweis``).
        "write.callerChanged": (
            "Das kann ich hier nicht ausführen: Die Vorschau entstand unter einer "
            "WLO-Anmeldung, die in diesem Fenster gerade nicht gilt — etwa in einem neuen "
            "Tab oder nach einer abgelaufenen Anmeldung. Es wurde nichts geändert. Melde "
            "dich an und bitte mich dann noch einmal darum."
        ),
        "write.executeRejected": (
            "Das ist so nicht durchgegangen — WLO hat die Änderung abgelehnt, "
            "es wurde nichts geändert. Sag mir, was ich anders machen soll; "
            "dann lege ich sie dir erneut zur Abnahme vor."
        ),
        "write.confirmRenewed": (
            "Die Freigabe war nicht mehr gültig — es wurde nichts geändert. Unten steht die "
            "Vorschau noch einmal; bestätige sie bitte erneut."),
        "write.loginNeeded": (
            "Dafür braucht WLO deine eigene Anmeldung — es wurde nichts geändert. Melde dich "
            "an und bitte mich dann noch einmal darum."),
        "write.rejectedReason": "Grund: {grund}",
        "write.existsHint": (
            "Dazu gibt es schon einen Datensatz: „{titel}“ ({kennung}). Soll ich stattdessen "
            "mit diesem weiterarbeiten?"),
        "write.confirmExpired": (
            "Die Freigabe war nicht mehr gültig — es wurde nichts geändert. Bitte mich gleich "
            "noch einmal darum, dann lege ich dir die Änderung neu vor."),
        "write.nothingToChange": "Da gibt es nichts zu ändern — in WLO steht es schon so.",
        "write.planOpen": (
            "Noch nicht alles fertig — mit „Plan fortsetzen“ geht es ohne neue Bestätigung weiter "
            "(bis zu 30 Minuten nach der Freigabe)."),
        "write.planExpired": (
            "Der Plan ist abgelaufen oder nicht mehr bekannt — weiter geändert wurde nichts; was "
            "schon erledigt ist, bleibt. Stoße ihn neu an — die neue Vorschau zeigt, was schon "
            "da ist."),
        "write.planNone": "Gerade gibt es keinen offenen Plan, den ich fortsetzen könnte.",
        "write.timeoutNothingDone": (
            "WLO hat nicht rechtzeitig geantwortet — geändert wurde nichts. Bitte mich einfach "
            "noch einmal darum, dann lege ich dir die Vorschau neu vor."),
        # Paket AS-8a: Probe der Studio-Vorschau — das Werkzeug lief nicht.
        "probe.trocken": (
            "Trockenlauf: Hier wäre jetzt {werkzeug} gelaufen — geschrieben wurde nichts."),
        "write.planStillOpen": (
            "Ein früherer Plan ist noch nicht fertig — es wurde nichts geändert. Führe ihn zuerst "
            "mit „Plan fortsetzen“ zu Ende; danach lege ich dir die neue Vorschau gern vor."),
        "write.planTooLarge": (
            "Dieser Plan ist zu groß, um ihn hier zu bestätigen — es wurde nichts geändert. Lass "
            "ihn uns in kleineren Teilen angehen."),
        "write.planUnclearStart": (
            "Von WLO kam keine Antwort — ob der Plan angelaufen ist, ist offen. „Plan fortsetzen“ "
            "setzt ihn fort, falls ja; sonst sage ich es dir."),
        "write.planUnclear": (
            "Vom Server kam keine Antwort. Der Plan bleibt bestehen; „Plan fortsetzen“ setzt ihn "
            "gefahrlos fort."),
        # Plan 2026-11-07 (CB-2/CB-4): nichts lief — die Abnahme bleibt liegen.
        "write.busy": (
            "WLO ist gerade ausgelastet — ausgeführt wurde noch nichts. Deine Freigabe gilt "
            "weiter: tippe gleich noch einmal auf „Ja, so ausführen“."),
        "write.busyWait": "WLO bittet, etwa {s} Sekunden zu warten.",
        "write.authUnclear": (
            "Deine Anmeldung ließ sich gerade nicht prüfen — ausgeführt wurde noch nichts. Deine "
            "Freigabe gilt weiter: tippe gleich noch einmal auf „Ja, so ausführen“."),
        "write.planBusy": (
            "WLO ist gerade ausgelastet — weiter geändert wurde noch nichts. Der Plan bleibt "
            "bestehen; „Plan fortsetzen“ setzt ihn gleich fort."),
        "write.tooManyPlans": (
            "Unter deiner Anmeldung laufen schon fünf unfertige Pläne — es wurde nichts geändert. "
            "Führe zuerst einen davon zu Ende; danach lege ich dir die Vorschau gern neu vor."),
        "write.planBlocked": (
            "Fortsetzen geht hier gerade nicht — das Werkzeug ist in diesem Zusammenhang nicht "
            "freigegeben. Weiter geändert wurde nichts."),
        "action.plan.weiterKnopf": "Plan fortsetzen",
        "write.executeUnconfirmed": (
            "Die Änderung ist nicht bestätigt zurückgekommen — ob sie "
            "angekommen ist, kann ich von hier aus nicht sagen. Sieh bitte in "
            "WLO nach, bevor du es noch einmal versuchst; sonst steht sie am "
            "Ende zweimal da."
        ),
        # ── Hinweise und Chips am Rand einer normalen Antwort ──────────
        # ``facets.narrowChip``: das Label kommt aus dem WLO-Vokabular und
        # bleibt, wie WLO es liefert — übersetzt wird nur das Wort davor.
        # Die Anführungszeichen im Filter-Hinweis stehen als eigener
        # Schlüssel, weil sie sprachabhängig sind (wie content.aboutMaterial).
        "facets.narrowChip": "Nur {label} ({count})",
        "facets.quotedValue": "„{value}“",
        "facets.unresolvedFilter": (
            "Hinweis: Nach {values} konnte ich nicht filtern und habe "
            "allgemeiner gesucht."
        ),
        "facets.unresolvedLicense": (
            "Hinweis: Die Lizenz {value} kenne ich nicht — mit ihr finde ich keine "
            "Materialien."),
        "facets.licenseSuggestion": "Meintest du {values}?",
        "qr.passQuality": "Hat das geholfen?",
        # ── Was der Nutzer sieht, wenn etwas nicht geht ────────────────
        "error.safetyBlocked": (
            "Diese Anfrage konnte ich nicht bearbeiten — sie verletzt "
            "Sicherheits- oder Inhaltsregeln. Probier es bitte mit einer "
            "anderen Formulierung erneut."
        ),
        # Paket 18A: ``MODERATION_FAILURE_MODE=closed`` und die Inhaltsprüfung
        # fehlt — kein Vorwurf an die Person, sie hat nichts falsch gemacht.
        "error.moderationUnavailable": (
            "Ich kann deine Nachricht gerade nicht prüfen lassen und antworte "
            "deshalb lieber nicht. Versuch es bitte in ein paar Minuten noch einmal."
        ),
        # Paket 18C/D: die Fehlernummer (Anfang der Trace-ID) am Satzende statt der
        # Ausnahme-Klasse — sie führt im Studio zum Zug; die Auswertung erkennt den Satz davor.
        "error.internal": (
            "Da ist intern etwas schiefgelaufen. Versuch es nochmal — "
            "wenn es bestehen bleibt, gib mir kurz Bescheid. (Fehlernummer: {nummer})"
        ),
        "error.answerFailed": (
            "Ich konnte gerade keine Antwort erzeugen. Versuch es noch einmal "
            "— meistens klappt es beim zweiten Anlauf. (Fehlernummer: {nummer})"
        ),
        "error.retryChip": "Nochmal versuchen",
        # Paket 18F: kein LLM-Platz binnen ``LLM_SLOT_WAIT_S`` — kein Fehler mit Nummer, sondern
        # Last; die Person soll es gleich noch einmal versuchen.
        "error.llmBusy": (
            "Gerade sind sehr viele Anfragen gleichzeitig unterwegs, und ich komme nicht "
            "durch. Versuch es bitte in einer Minute noch einmal."
        ),
        # ── A4c-2b: eine Maschine endet ohne eigenen Text ──────────────
        # ``AgentRun.text`` ist nur bei ``text``/``submit`` gefüllt; bei Frist,
        # Token-Budget, Iterationsdeckel, Stillstand und LLM-Fehler bleibt er
        # leer. Eine leere Blase ist der schlechtere von beiden Ausfällen.
        #
        # ``agent.failed`` dient seit 2026-08-21 BEIDEN Maschinen: der
        # Muster-Weg (``graph/nodes/respond``) sagt denselben Satz, wenn ein
        # Aussetzer des Anbieters auch die Wiederholungen überlebt hat. Es ist
        # derselbe Ausfall — zwei Formulierungen dafür wären zwei Wahrheiten.
        # Der Schlüssel behält den ``agent.``-Präfix, weil dort seine Heimat
        # ist; umbenennen hieße drei Aufrufstellen und zwei Sprachen anfassen.
        "agent.incomplete": (
            "Ich bin damit nicht fertig geworden — die Anfrage war zu "
            "umfangreich. Stell sie gern kleiner geschnitten noch einmal."
        ),
        "agent.failed": (
            "Ich konnte gerade keine Antwort erzeugen. Versuch es noch einmal "
            "— meistens klappt es beim zweiten Anlauf."
        ),
        # D3: Der Lauf endete an einem Deckel, hatte sein Ergebnis aber schon
        # geliefert — ihm fehlt nur der Begleitsatz. Die beiden Sätze darüber
        # würden von der Box widerlegt, die direkt darunter steht.
        "agent.delivered": "Hier ist das Ergebnis.",
        # U1-d1: Die KI stellt eine Frage mit Auswahlfeld (``ui_entscheidung``) und schreibt
        # selbst keinen Satz dazu — die Frage steht im Feld darunter.
        "agent.frage": "Bitte wähle unten aus.",
        "agent.entwurf": "Hier ist ein Entwurf — unten bearbeiten, herunterladen oder übernehmen.",
        # ── Kontext-Bestätigung: was ich in dieser Sammlung sehe ───────────
        # Nutzer-Vorgabe 2026-08-14: die Begrüßung soll ZEIGEN, dass der
        # Kontext angekommen ist, statt es zu behaupten. Drei Fassungen, weil
        # jede Zahl einzeln ausfallen darf (``services/context_facts``) —
        # fehlen beide, bleibt der Satz weg und es bleibt bei der Begrüßung.
        "context.stock.both": (
            "Ich sehe {materials} Materialien und {skills} freigegebene "
            "Skills dazu."
        ),
        "context.stock.materials": "Ich sehe {materials} Materialien darin.",
        "context.stock.skills": "Ich sehe {skills} freigegebene Skills dazu.",
        "curation.failed": "Die Kuratier-Analyse konnte nicht erstellt werden.",
        "curation.error": "Fehler bei der Kuratier-Analyse. Versuch es bitte noch einmal.",
        "learningPath.failed": "Lernpfad konnte nicht erstellt werden.",
        "learningPath.error": "Fehler beim Erstellen des Lernpfads. Versuch es bitte noch einmal.",
        # ── C5-c2: die Anmelde-Rückfrage ──────────────────────────────
        # Nur der ablehnende Chip steht hier. Der anmeldende trägt seine
        # Beschriftung im Widget-Katalog, weil er nichts absendet, sondern dort
        # eine Handlung auslöst (Begründung in ``domain/auth_qr``).
        # Formuliert als Satz des NUTZERS — der Klick schickt ihn ab.
        "auth.readOnly": "Such einfach, ohne Anmeldung",
    },
    "en": {
        "content.missingNode": "You have not told me which material to open.",
        "content.mcpUnreachable": (
            "I could not load the full text just now — the material search was "
            "unreachable. Please try again in a moment."
        ),
        "content.aboutMaterial": "About the material: ",
        "content.aboutMaterialNamed": "About the material “{title}”: ",
        "content.reason.accessDenied": (
            "This material is **not freely accessible** — the source releases the "
            "full text to signed-in users only."
        ),
        "content.reason.noTextNoUrl": (
            "There is no text I could show for this material — neither a written "
            "version nor a retrievable source."
        ),
        "content.reason.extractionFailed": (
            "The text of this material could not be extracted just now. That is a "
            "technical problem, not a rights problem — a second attempt may work."
        ),
        "content.reason.nodeNotFound": (
            "I cannot find this material any more — it may have been withdrawn or "
            "moved."
        ),
        "content.reason.noEnvelope": (
            "The material search answered in a shape I could not read. I would "
            "rather show nothing than half a guess."
        ),
        "content.reason.unknown": "I could not load the full text of this material.",
        "content.source": "Source: {url}",
        "content.lead": "Here is the content of “{title}”.",
        "content.truncated": (
            " The text is very long and has therefore been **shortened** — the "
            "beginning is complete, the end is missing."
        ),
        "content.fallbackTitle": "Content",
        "content.qr.createOwn": "Create your own material on this instead",
        "content.qr.freeAlternatives": "Search for freely accessible alternatives",
        "content.qr.shorter": "Make the text shorter",
        "content.qr.simpler": "Put it in simpler words",
        "content.qr.similar": "Show similar materials",
        "action.collectionFallbackTitle": "Collection",
        "action.missingCollectionId": "No collection ID was given.",
        "action.browse.header": "**{title}** — results {range}{total}:",
        "action.browse.ofTotal": " of {total}",
        "action.browse.empty": 'I found no content in the collection "{title}".',
        "action.browse.loadFailed": 'Failed to load the content of "{title}". Please try again.',
        "action.browse.canvasTitle": "Content of {title}",
        "action.browse.canvasTitleFallback": "Collection content",
        "action.tree.header": "Here are the subtopics:",
        "action.tree.loadFailed": (
            'Could not load the subtopics of "{title}". Please try again.'
        ),
        "action.tree.inactive": (
            'The topic tree view is switched off — I cannot open the subtopics of "{title}" here.'
        ),
        "action.draft.header": (
            'The structure of "{title}" as a draft — edit, download or accept it below.'
        ),
        "action.draft.loadFailed": (
            'Could not load the structure of "{title}" as a draft right now.'
        ),
        "action.draft.ohneTitel": "Structure from WLO",
        "action.draft.inactive": (
            'Drafts are switched off here — I cannot open the structure of "{title}" as a draft.'
        ),
        "action.folderDraft.header": (
            'The folder structure of "{title}" as a draft — edit, download or accept it below.'
        ),
        "action.folderDraft.empty": (
            '"{title}" has no subfolders that could become a topic tree.'
        ),
        "action.folderDraft.ohneTitel": "Structure from folders",
        "action.folderDraft.inactive": (
            'Drafts are switched off here — I cannot open the folder structure of "{title}" as a '
            "draft."
        ),
        "action.ablauf.unbekannt": "This workflow does not exist here or is switched off.",
        "action.ablauf.wahlVeraltet": "This choice no longer applies — the workflow has moved on.",
        "action.ablauf.anmeldung": "Please sign in to WLO for this workflow.",
        "action.ablauf.startdaten": (
            "This workflow needs suitable start data from the page that embeds the chat — it "
            "cannot start like this."),
        "action.ablauf.laeuftSchon": (
            "This workflow is already running here — it continues where it stands."),
        "action.ablauf.ersetzen": (
            "A workflow is about to start, but another one is still running in this "
            "conversation. A restart ends the running one (including a job it is waiting for). "
            "Do you want to restart?"),
        "action.ablauf.keinLauf": "No workflow is running in this conversation right now.",
        "action.ablauf.abbrechenFrage": (
            "Really cancel the workflow? This cannot be undone; a job it is waiting for ends "
            "too. What has been collected so far stays in your work state."),
        "action.ablauf.abbrechenFrageZurueck": (
            "Really cancel the workflow? This cannot be undone; a job it is waiting for ends "
            "too. What has been collected so far stays in your work state. To carry on instead, "
            "pick another answer."),
        "action.ablauf.abbrechenJa": "Cancel workflow",
        "action.ablauf.abgebrochenPerson": "The workflow has been cancelled.",
        "action.ablauf.neuStarten": "Restart",
        "action.ablauf.ersetzenOhneKnopf": (
            "The page wants to start a workflow, but another one is still running in this "
            "conversation. End it first (“new project”), then the page can start again."),
        "action.ablauf.konflikt": (
            "Your work was just changed elsewhere. Please try again."),
        "action.ablauf.fehler": "The workflow cannot continue at this point.",
        "action.ablauf.weiter": "Let's continue.",
        "action.ablauf.fertig": "The workflow is complete.",
        "action.ablauf.weiterKnopf": "Continue workflow",
        "action.ablauf.dochMitAblauf": "Use the workflow after all",
        "action.ablauf.auftragKnopf": "Check status",
        "action.ablauf.freigabeErneutKnopf": "Show the preview again",
        "action.ablauf.freigabeAbbrechenKnopf": "Cancel workflow",
        "action.ablauf.freigabeAbgebrochen": (
            "The workflow is cancelled — nothing was changed in WLO."),
        "action.ablauf.freigabeAbgebrochenPlan": (
            "The workflow is cancelled. What the plan has already done stays in WLO; it will "
            "not be continued."),
        "action.ablauf.freigabeOhneAnmeldung": (
            "To change anything in WLO I need you to be signed in — nothing was changed."),
        "action.ablauf.freigabeSpaeter": (
            "The preview could not be fetched just now (WLO busy, no answer, or the sign-in was "
            "rejected) — nothing was changed. Try again shortly with “Show the preview again”."),
        "action.ablauf.freigabeAbgelaufen": (
            "The preview has expired — nothing was changed. Get a fresh one with “Show the "
            "preview again”."),
        "action.ablauf.freigabeKonflikt": (
            "The change is saved in WLO, but the workflow could not be updated just now — it "
            "ends here. Start it again if steps are still missing."),
        "action.ablauf.freigabeNichtMehrOffen": (
            "This preview belongs to a workflow that no longer waits for it (cancelled or shown "
            "again) — nothing was changed."),
        "action.ablauf.freigabeVorbereitet": (
            "The change is prepared and the page carries it out. The workflow ends here — start "
            "it again afterwards if steps are still missing."),
        "action.ablauf.auftragAbbrechenKnopf": "Cancel job",
        "action.ablauf.auftragAbbrechenJa": "Yes, cancel",
        "action.ablauf.auftragAbbrechenFrage": (
            "Do you really want me to cancel the running job? Its result will not arrive, and the "
            "workflow ends here."),
        "action.ablauf.auftragAbgebrochen": "The job is cancelled, the workflow ends here.",
        "action.ablauf.auftragSchonBeendet": "This job is no longer running.",
        "action.ablauf.auftragNurHierAbgebrochen": (
            "The workflow ends here. Without your sign-in I could not stop the job itself — it "
            "keeps running until it finishes, but nobody collects its result here."),
        "action.vorgang.neuFrage": (
            "A job is still running. If you start afresh, I will cancel it and its result will not "
            "arrive. Start afresh anyway?"),
        "action.vorgang.neuJa": "Yes, start afresh",
        "action.ablauf.auftragGesperrt": (
            "While this job is running, we can only continue once it is done. Tap “Check "
            "status” — or cancel it."),
        "action.ablauf.auftragGestartet": "A job is running in the background.",
        "action.vorgang.neu": "Fine, let's start afresh. Your previous work is closed.",
        "action.vorgang.geloescht": "Your work in progress has been deleted.",
        "action.vorgang.keiner": "There is no work in progress right now.",
        "action.vorgang.neuKnopf": "New project",
        "action.vorgang.loeschenKnopf": "Delete work in progress",
        "action.vorgang.loeschenFrage": (
            "Do you really want me to delete your work in progress? This includes all saved "
            "projects, closed ones too, and the document uploaded in this session. This cannot "
            "be undone."),
        "action.vorgang.loeschenJa": "Yes, delete",
        "action.ablauf.auftragAbgewiesen": (
            "I am not allowed to fetch the status of this job with your sign-in. Please sign in "
            "again and start the workflow once more."),
        "action.ablauf.auftragLaeuft": (
            "The job is still running. Feel free to check back later — then tap “Check status”."),
        "action.ablauf.auftragNichtAbrufbar": (
            "I can't fetch the status of the job right now. Please try again in a moment."),
        "action.ablauf.dateienSpaeter": (
            "The job is done, but I couldn't fetch its files just now. Please tap “Check status” "
            "again in a moment."),
        "action.ablauf.fehltNoch": (
            "Something is still missing for the next step. Keep working on this step, then tap "
            "“Continue workflow” again."),
        "action.curate.searchPill": "Search for content missing from {title}",
        "action.curate.searchPillPlain": "Search for missing content",
        "action.curate.noCompendium": (
            'The collection “{title}” has no editorial summary on file, so I '
            "cannot reliably tell what is still missing. I can summarise the "
            "existing content for you, or search for fitting materials."
        ),
        "action.lp.resetNotice": (
            "_Note: no new content was available, so the selection starts over._"
        ),
        "action.lp.noContents": (
            'I found no content in the collection "{title}" that a learning path '
            "could be built from."
        ),
        "action.lp.failed": 'Failed to build the learning path for "{title}". Please try again.',
        "material.askType": (
            "Which kind of material should I create on **{topic}**? Pick a type "
            "from the suggestions, or write \"Automatic\" and I will choose a "
            "fitting one myself."
        ),
        "material.askTopic": (
            "I will gladly create a material for you. On which **topic**? "
            "For example: \"Create a worksheet on photosynthesis for year 6\"."
        ),
        "material.genFailed": (
            "I could not create the **{label}** on *{topic}* just now. "
            "Please try again — it usually works on the second attempt. (Error number: {nummer})"
        ),
        "material.createFailed": "Could not create this material (Error number: {nummer})",
        "material.solutionsStub": (
            "## Solutions\n\n"
            "_Solutions will be added — reply with \"add solutions\" and I "
            "will fill in this section._"
        ),
        "completion.canvas.lead.du": (
            "I have created a **{label}** on *{topic}* for you."
        ),
        "completion.canvas.lead.sie": (
            "I have created a **{label}** on *{topic}* for you."
        ),
        "completion.sections": "Sections:",
        "completion.tasks": "Contains **{count} exercises**.",
        "completion.tasksWithSolutions": "Contains **{count} exercises** with solutions.",
        "completion.canvas.outro.du": (
            "You can see it in the canvas on the right — I can adjust it "
            "directly if you write something like \"make the exercises easier\" "
            "or \"add solutions\"."
        ),
        "completion.canvas.outro.sie": (
            "You can see it in the canvas on the right — I can adjust it "
            "directly if you write something like \"make the exercises easier\" "
            "or \"add solutions\"."
        ),
        "completion.inline.outro.du": (
            "The material is right below this message — you can save it as a "
            "PDF with the print button. Just tell me what should change "
            "(e.g. *\"make the exercises easier\"* or *\"add solutions\"*)."
        ),
        "completion.inline.outro.sie": (
            "The material is right below this message — you can save it as a "
            "PDF with the print button. Just tell me what should change "
            "(e.g. *\"make the exercises easier\"* or *\"add solutions\"*)."
        ),
        "completion.lp.lead.canvas": (
            "I have built the **learning path on *{topic}*** in the canvas "
            "on the right."
        ),
        "completion.lp.lead.inline": (
            "I have built the **learning path on *{topic}*** right below "
            "this message."
        ),
        "completion.lp.phases": "It is structured into these phases:",
        "completion.lp.outro.canvas": (
            "You can print it from the canvas, save it as Markdown, or tell me "
            "what should change (e.g. *\"make it easier, for year 5\"* or "
            "*\"add a step for consolidation\"*)."
        ),
        "completion.lp.outro.inline": (
            "You can save it as a PDF with the print button below, or tell me "
            "what should change (e.g. *\"make it easier, for year 5\"* or "
            "*\"add a step for consolidation\"*)."
        ),
        "links.typeFocus.ctaTopic": (
            "For {label} on “{topic}” check the search below — that is where "
            "you will find the filtered results."
        ),
        "links.typeFocus.ctaTopic.sie": (
            "For {label} on “{topic}” check the search below — that is where "
            "you will find the filtered results."
        ),
        "links.typeFocus.ctaPlain": (
            "For {label} on this topic check the search below — that is where "
            "you will find the filtered results."
        ),
        "links.typeFocus.ctaPlain.sie": (
            "For {label} on this topic check the search below — that is where "
            "you will find the filtered results."
        ),
        "guide.label.sourcePage": "Source page",
        "guide.label.learnMore": "Learn more",
        "links.claim.typeFocusCta": (
            "For {label} on this topic, click the search below — that is "
            "where you will find the filtered results. "
        ),
        "links.claim.typeFocusCta.sie": (
            "For {label} on this topic, click the search below — that is "
            "where you will find the filtered results. "
        ),
        "links.claim.fallbackLabel": "materials",
        "links.claim.searchHits": "matching results in the search",
        "links.claim.searchPointer": (
            "Look at the linked search below — that is where you will find "
            "matching results on this topic. "
        ),
        "links.claim.searchPointer.sie": (
            "Look at the linked search below — that is where you will find "
            "matching results on this topic. "
        ),
        "inline.title.learningPath": "Learning path",
        "inline.title.material": "Material",
        "inline.title.editedVersion": "Edited version",
        "inline.title.content": "Content",
        "inline.title.writePreview": "Change awaiting your approval",
        "inline.writePreview.frist": (
            "This approval is valid for {minuten} minutes from this preview."),
        "inline.writePreview.ask": (
            "Shall I go ahead? If something is off, tell me what to change."
        ),
        "action.write.confirmChip": "Yes, go ahead",
        "write.consentUnclear": (
            "So I could not check your last message. The preview is below once more — shall "
            "I carry it out unchanged? If you wanted something changed, just tell me again."
        ),
        "write.callerChanged": (
            "I cannot carry that out here: the preview was made under a WLO sign-in that "
            "does not apply in this window right now — for example in a new tab or after "
            "the sign-in expired. Nothing was changed. Sign in, then ask me again."
        ),
        "write.executeRejected": (
            "That did not go through — WLO rejected the change, and nothing "
            "was modified. Tell me what to do differently and I will put it "
            "up for approval again."
        ),
        "write.confirmRenewed": (
            "The approval was no longer valid — nothing was changed. The preview is below "
            "once more; please confirm it again."),
        "write.loginNeeded": (
            "WLO needs your own sign-in for this — nothing was changed. Please sign in and "
            "then ask me again."),
        "write.rejectedReason": "Reason: {grund}",
        "write.existsHint": (
            "There is already a record for this: “{titel}” ({kennung}). Shall I work with "
            "that one instead?"),
        "write.confirmExpired": (
            "The approval was no longer valid — nothing was changed. Just ask me again and I "
            "will present the change anew."),
        "write.nothingToChange": "There is nothing to change — WLO already has it this way.",
        "write.planOpen": (
            "Not everything is done yet — “Continue” carries on without a new approval (up to 30 "
            "minutes after the approval)."),
        "write.planExpired": (
            "The plan has expired or is no longer known — nothing further was changed; what was "
            "already done stays. Start it again — the new preview shows what is already there."),
        "write.planNone": "There is no open plan I could continue right now.",
        "write.timeoutNothingDone": (
            "WLO did not answer in time — nothing was changed. Just ask me again and I will show "
            "you the preview anew."),
        "probe.trocken": "Dry run: {werkzeug} would have run here — nothing was written.",
        "write.planStillOpen": (
            "An earlier plan is not finished yet — nothing was changed. Finish it with “Continue” "
            "first; then I will gladly show you the new preview."),
        "write.planTooLarge": (
            "This plan is too large to confirm here — nothing was changed. Let us do it in "
            "smaller parts."),
        "write.planUnclearStart": (
            "WLO did not answer — whether the plan started is unclear. “Continue” resumes it if "
            "it did; otherwise I will tell you."),
        "write.planUnclear": (
            "The server did not answer. The plan remains; “Continue” resumes it safely."),
        "write.busy": (
            "WLO is busy right now — nothing has been carried out yet. Your approval still "
            "stands: tap “Yes, go ahead” again in a moment."),
        "write.busyWait": "WLO suggests waiting about {s} seconds.",
        "write.authUnclear": (
            "Your sign-in could not be checked just now — nothing has been carried out yet. Your "
            "approval still stands: tap “Yes, go ahead” again in a moment."),
        "write.planBusy": (
            "WLO is busy right now — nothing further has been changed yet. The plan remains; "
            "“Continue” resumes it in a moment."),
        "write.tooManyPlans": (
            "Five unfinished plans are already running under your sign-in — nothing was changed. "
            "Finish one of them first; then I will gladly show you the preview again."),
        "write.planBlocked": (
            "Continuing is not possible here right now — the tool is not enabled in this context. "
            "Nothing further was changed."),
        "action.plan.weiterKnopf": "Continue",
        "write.executeUnconfirmed": (
            "The change did not come back confirmed — from here I cannot tell "
            "whether it went through. Please check in WLO before trying again, "
            "otherwise it may end up there twice."
        ),
        "facets.narrowChip": "Only {label} ({count})",
        "facets.quotedValue": "“{value}”",
        "facets.unresolvedFilter": (
            "Note: I could not filter by {values} and searched more broadly "
            "instead."
        ),
        "facets.unresolvedLicense": (
            "Note: I do not know the licence {value}, so I find no materials with it."),
        "facets.licenseSuggestion": "Did you mean {values}?",
        "qr.passQuality": "Did that help?",
        "error.safetyBlocked": (
            "I could not process this request — it breaks our safety or "
            "content rules. Please try rephrasing it."
        ),
        "error.moderationUnavailable": (
            "I cannot have your message checked right now, so I would rather not "
            "answer. Please try again in a few minutes."
        ),
        "error.internal": (
            "Something went wrong on our side. Try again — if it "
            "keeps happening, let me know. (Error number: {nummer})"
        ),
        "error.answerFailed": (
            "I could not produce an answer just now. Try again — it usually "
            "works on the second attempt. (Error number: {nummer})"
        ),
        "error.retryChip": "Try again",
        "error.llmBusy": (
            "There are a lot of requests at once right now, and I can't get through. "
            "Please try again in a minute."
        ),
        "agent.incomplete": (
            "I did not get through this one — the request was too broad. Try "
            "again with a narrower question."
        ),
        "agent.failed": (
            "I could not produce an answer just now. Try again — it usually "
            "works on the second attempt."
        ),
        "agent.delivered": "Here is the result.",
        "agent.frage": "Please choose below.",
        "agent.entwurf": "Here is a draft — edit, download or accept it below.",
        "context.stock.both": (
            "I can see {materials} materials and {skills} approved guides for it."
        ),
        "context.stock.materials": "I can see {materials} materials in it.",
        "context.stock.skills": "I can see {skills} approved guides for it.",
        "curation.failed": "The curation analysis could not be created.",
        "curation.error": "Error during the curation analysis. Please try again.",
        "learningPath.failed": "The learning path could not be created.",
        "learningPath.error": "Error while creating the learning path. Please try again.",
        "auth.readOnly": "Just search, no sign-in",
    },
}


def bot_text(locale: Locale, key: str, **params: object) -> str:
    """The bot's sentence for ``key`` in ``locale``, with ``params`` substituted."""
    return render(BOT_TEXT, locale, key, **params)
