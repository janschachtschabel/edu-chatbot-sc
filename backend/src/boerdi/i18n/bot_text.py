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
        "action.browse.loadFailed": 'Fehler beim Laden der Inhalte von "{title}": {error}',
        "action.browse.canvasTitle": "Inhalte: {title}",
        "action.browse.canvasTitleFallback": "Sammlungs-Inhalte",
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
        "action.lp.failed": 'Fehler beim Erstellen des Lernpfads für "{title}": {error}',
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
            "nicht erstellen ({error}). Versuch es nochmal — "
            "meistens klappt es beim zweiten Anlauf."
        ),
        "material.createFailed": "Fehler beim Erstellen",
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
        "links.typeFocus.ctaTopic": (
            "Für {label} zu „{topic} schau in die Suche unten — dort findest "
            "du die gefilterten Treffer."
        ),
        "links.typeFocus.ctaPlain": (
            "Für {label} zum Thema schau in die Suche unten — dort findest "
            "du die gefilterten Treffer."
        ),
        "guide.label.sourcePage": "Quell-Seite",
        "guide.label.learnMore": "Mehr erfahren",
        # ── Ersatztexte des Anti-Halluzinations-Wächters ────────────────
        # Alle drei werden MITTEN in einen bestehenden Satz gesetzt bzw.
        # ersetzen einen ganzen Satz; die abschließenden Leerzeichen sind
        # ALT-verbatim und Teil der Fügung — nicht wegräumen.
        "links.claim.typeFocusCta": (
            "Für {label} zum Thema klick auf die Suche unten — dort findest "
            "du die gefilterten Treffer. "
        ),
        "links.claim.fallbackLabel": "Materialien",
        "links.claim.searchHits": "passende Treffer in der Suche",
        "links.claim.searchPointer": (
            "Schau in die verlinkte Suche unten — dort findest du passende "
            "Treffer zum Thema. "
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
        "inline.writePreview.ask": (
            "Soll ich das so ausführen? Wenn etwas nicht stimmt, sag mir, "
            "was anders sein soll."
        ),
        # Nur die Zustimmung bekommt einen Knopf. Ein „Ändern"-Knopf könnte nur
        # einen Satz senden, den der Nutzer selbst besser formuliert.
        "action.write.confirmChip": "Ja, so ausführen",
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
        # stehen: der Beleg dafür ist seine Antwort. Den Grund nennt der Satz
        # nicht — er ist ein Interna-Auszug und steht im Protokoll.
        "write.executeRejected": (
            "Das ist so nicht durchgegangen — WLO hat die Änderung abgelehnt, "
            "es wurde nichts geändert. Sag mir, was ich anders machen soll; "
            "dann lege ich sie dir erneut zur Abnahme vor."
        ),
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
        "qr.passQuality": "Hat das geholfen?",
        # ── Was der Nutzer sieht, wenn etwas nicht geht ────────────────
        "error.safetyBlocked": (
            "Diese Anfrage konnte ich nicht bearbeiten — sie verletzt "
            "Sicherheits- oder Inhaltsregeln. Probier es bitte mit einer "
            "anderen Formulierung erneut."
        ),
        # ``{kind}`` ist der Ausnahme-TYP (``RuntimeError``), nicht die
        # Meldung — interne Details gehören nicht in eine Nutzer-Blase.
        "error.internal": (
            "Da ist intern etwas schiefgelaufen ({kind}). Versuch es nochmal — "
            "wenn es bestehen bleibt, gib mir kurz Bescheid."
        ),
        "error.retryChip": "Nochmal versuchen",
        # ── A4c-2b: der Agent-Modus endet ohne eigenen Text ────────────
        # ``AgentRun.text`` ist nur bei ``text``/``submit`` gefüllt; bei Frist,
        # Token-Budget, Iterationsdeckel, Stillstand und LLM-Fehler bleibt er
        # leer. Eine leere Blase ist der schlechtere von beiden Ausfällen.
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
        "curation.error": "Fehler bei der Kuratier-Analyse: {error}",
        "learningPath.failed": "Lernpfad konnte nicht erstellt werden.",
        "learningPath.error": "Fehler beim Erstellen des Lernpfads: {error}",
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
        "action.browse.loadFailed": 'Failed to load the content of "{title}": {error}',
        "action.browse.canvasTitle": "Content of {title}",
        "action.browse.canvasTitleFallback": "Collection content",
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
        "action.lp.failed": 'Failed to build the learning path for "{title}": {error}',
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
            "I could not create the **{label}** on *{topic}* just now "
            "({error}). Please try again — it usually works on the second attempt."
        ),
        "material.createFailed": "Could not create this material",
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
        "links.typeFocus.ctaPlain": (
            "For {label} on this topic check the search below — that is where "
            "you will find the filtered results."
        ),
        "guide.label.sourcePage": "Source page",
        "guide.label.learnMore": "Learn more",
        "links.claim.typeFocusCta": (
            "For {label} on this topic, click the search below — that is "
            "where you will find the filtered results. "
        ),
        "links.claim.fallbackLabel": "materials",
        "links.claim.searchHits": "matching results in the search",
        "links.claim.searchPointer": (
            "Look at the linked search below — that is where you will find "
            "matching results on this topic. "
        ),
        "inline.title.learningPath": "Learning path",
        "inline.title.material": "Material",
        "inline.title.editedVersion": "Edited version",
        "inline.title.content": "Content",
        "inline.title.writePreview": "Change awaiting your approval",
        "inline.writePreview.ask": (
            "Shall I go ahead? If something is off, tell me what to change."
        ),
        "action.write.confirmChip": "Yes, go ahead",
        "write.executeRejected": (
            "That did not go through — WLO rejected the change, and nothing "
            "was modified. Tell me what to do differently and I will put it "
            "up for approval again."
        ),
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
        "qr.passQuality": "Did that help?",
        "error.safetyBlocked": (
            "I could not process this request — it breaks our safety or "
            "content rules. Please try rephrasing it."
        ),
        "error.internal": (
            "Something went wrong on our side ({kind}). Try again — if it "
            "keeps happening, let me know."
        ),
        "error.retryChip": "Try again",
        "agent.incomplete": (
            "I did not get through this one — the request was too broad. Try "
            "again with a narrower question."
        ),
        "agent.failed": (
            "I could not produce an answer just now. Try again — it usually "
            "works on the second attempt."
        ),
        "agent.delivered": "Here is the result.",
        "context.stock.both": (
            "I can see {materials} materials and {skills} approved guides for it."
        ),
        "context.stock.materials": "I can see {materials} materials in it.",
        "context.stock.skills": "I can see {skills} approved guides for it.",
        "curation.failed": "The curation analysis could not be created.",
        "curation.error": "Error during the curation analysis: {error}",
        "learningPath.failed": "The learning path could not be created.",
        "learningPath.error": "Error while creating the learning path: {error}",
        "auth.readOnly": "Just search, no sign-in",
    },
}


def bot_text(locale: Locale, key: str, **params: object) -> str:
    """The bot's sentence for ``key`` in ``locale``, with ``params`` substituted."""
    return render(BOT_TEXT, locale, key, **params)
