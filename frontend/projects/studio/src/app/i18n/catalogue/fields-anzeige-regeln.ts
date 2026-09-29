/**
 * Feldtexte (ST-1) der Seite „Anzeige“, Abschnitt Darstellungsregeln
 * (`01-base/display-rules`). Kopfzeilen-Navigation und Geräte derselben Seite
 * stehen in `fields-anzeige-kopf-geraete.ts`; zusammen wären es über 300 Zeilen.
 *
 * Schlüsselschema wie in allen `fields-*.ts` (Kopf von `fields-layer-doc.ts`,
 * Plan 2026-09-26 §9.3). Die Wirkung steht nicht im Modell, sondern bei den
 * Lesern: `config_loader/widget.py` (`load_display_rules_config`) gibt ein
 * kuratiertes Dict zurück, das `turn_persist.py`, `tool_loop.py`,
 * `quick_reply_policy.py` und das Widget (`ui/src/grouping`, `ui/src/inline-doc`)
 * lesen. Was dabei nicht ankommt, sagen die Hilfetexte, statt eine Wirkung zu
 * versprechen: `layout`, `inline_fallback_enabled` und die beiden
 * `inline_card_links`-Felder (auch `01-base/widget-modes` wirkt nicht, siehe
 * `fields-karten.ts`; bis ST-9 stand hier das Gegenteil). `max_chars`
 * und `exclude_patterns` wirken seit 2026-09-27; vorher reichte der Lader den
 * Deckel nicht durch, und `pattern_output` trug keine Muster-Kennung.
 * `intro_text` ist seit 2026-09-27 auch im Modell eine Zuordnung Muster-ID → Text,
 * wie der Lader sie liest; vorher bestand ein einzelner Text die Prüfung.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_ANZEIGE_REGELN: CataloguePart = {
  de: {
    'feld.DisplayRulesArea.display_rules.label': 'Darstellungsregeln',
    'feld.DisplayRulesArea.display_rules.hint':
      'Was der Chat wie anzeigt: Dokument-Boxen, Ergebnisboxen, Antwortvorschläge. Der Chat '
      + 'liest die Regeln in jedem Zug neu, Änderungen gelten ab der nächsten Antwort.',

    // ── Dokument-Boxen ──────────────────────────────────────────────
    'feld.DisplayRulesBlock.inline_documents.label': 'Dokument-Boxen',
    'feld.DisplayRulesBlock.inline_documents.hint':
      'Lange Ergebnisse wie Lernpfade, erzeugte Materialien oder Überarbeitungen erscheinen '
      + 'als gerahmte Box im Verlauf, mit kurzem Begleittext in der Sprechblase.',
    'feld.InlineDocumentsRules.enabled.label': 'Boxen anzeigen',
    'feld.InlineDocumentsRules.enabled.hint':
      'Aus: Lernpfade, erzeugte Materialien und andere Dokumente des Modells stehen im '
      + 'Antworttext statt in einer Box. Die Volltext-Anzeige und die Vorschau einer Änderung '
      + 'an WLO bleiben Boxen; Vorgabe: an.',
    'feld.InlineDocumentsRules.font_size_percent.label': 'Schriftgröße',
    'feld.InlineDocumentsRules.font_size_percent.hint':
      'Schriftgröße im Inhalt der Box in Prozent, Vorgabe 85 (Standardgröße); kleinere '
      + 'Zahlen verkleinern die Schrift. Ein Wert außerhalb der Grenzen wird beim Speichern '
      + 'abgewiesen.',
    'feld.InlineDocumentsRules.per_pattern.label': 'Box je Muster',
    'feld.InlineDocumentsRules.per_pattern.hint':
      'Je Muster an oder aus: ob ein langer Antworttext mit Überschrift in die Box wandert. '
      + 'Wirkt nur bei M09 (Lernpfad), M10 (KI-Inhalt) und M11 (Nachbearbeitung); ohne '
      + 'Eintrag an.',
    'feld.InlineDocumentsRules.intro_text.label': 'Begleittext',
    'feld.InlineDocumentsRules.intro_text.hint':
      'Je Muster ein fester Text in der Sprechblase statt des Vorspanns aus der Antwort: '
      + 'Schlüssel ist die Muster-ID (M09, M10 oder M11), Wert der Text; {topic_suffix} wird '
      + 'zu „ zum Thema …“ oder entfällt ohne Thema. Ohne Eintrag bleibt der Vorspann. Gilt '
      + 'nicht für Boxen, die das Modell selbst liefert, und erscheint auch in englischen '
      + 'Gesprächen unverändert.',

    // ── Materialien-Box ─────────────────────────────────────────────
    'feld.DisplayRulesBlock.single_content_box.label': 'Materialien-Box',
    'feld.DisplayRulesBlock.single_content_box.hint':
      'Die Box „Ausgewählte Materialien“ mit einzelnen Inhalten unter der Antwort. Wie viele '
      + 'sie zeigt, steht unter „Höchstzahl je Box“.',
    'feld.SingleContentBoxRules.enabled.label': 'Box anzeigen',
    'feld.SingleContentBoxRules.enabled.hint':
      'Aus: Einzelne Inhalte entfallen aus den Ergebnissen, Themenseiten und Sammlungen '
      + 'bleiben. Vorgabe: an.',
    'feld.SingleContentBoxRules.layout.label': 'Darstellung',
    'feld.SingleContentBoxRules.layout.hint':
      'Gedacht als Kartenansicht (card) oder Liste (list), andere Werte gelten als card. Wird '
      + 'derzeit nicht ausgewertet: Das Widget zeigt die Box immer gleich.',
    'feld.SingleContentBoxRules.max_count.label': 'Alte Höchstzahl',
    'feld.SingleContentBoxRules.max_count.hint':
      'Früherer Ort für die Höchstzahl der Materialien. Wirkt nur, wenn unter „Höchstzahl je '
      + 'Box“ kein Wert für Materialien steht; besser dort pflegen.',

    // ── Höchstzahl je Box ───────────────────────────────────────────
    'feld.DisplayRulesBlock.groups.label': 'Höchstzahl je Box',
    'feld.DisplayRulesBlock.groups.hint':
      'Wie viele Einträge jede Ergebnisbox unter der Antwort höchstens zeigt; Server und '
      + 'Widget kürzen beide darauf. In der Muster-Engine bestimmen die Werte auch, wie viele '
      + 'Treffer das Modell auswählen darf (5 bis 20).',
    'feld.GroupsRules.themenseiten_max.label': 'Themenseiten',
    'feld.GroupsRules.themenseiten_max.hint':
      'Höchstzahl in der Box „Themenseiten“, 1 bis 20; Vorgabe 3.',
    'feld.GroupsRules.sammlungen_max.label': 'Sammlungen',
    'feld.GroupsRules.sammlungen_max.hint':
      'Höchstzahl in der Box „Sammlungen“, 1 bis 20; Vorgabe 3.',
    'feld.GroupsRules.materialien_max.label': 'Materialien',
    'feld.GroupsRules.materialien_max.hint':
      'Höchstzahl in der Box „Ausgewählte Materialien“, 1 bis 8; Vorgabe 3.',
    'feld.GroupsRules.materialien_max_lernpfad.label': 'Materialien im Lernpfad',
    'feld.GroupsRules.materialien_max_lernpfad.hint':
      'Höchstzahl der Materialien, wenn die Antwort ein Lernpfad ist (Muster M09), 1 bis 8; '
      + 'Vorgabe 5. Das Widget zeigt in der Box trotzdem höchstens so viele wie bei '
      + '„Materialien“.',
    'feld.GroupsRules.webseiten_max.label': 'Webseiten-Inhalte',
    'feld.GroupsRules.webseiten_max.hint':
      'Höchstzahl in der Box „Webseiten-Inhalte“ (Links aus dem Antworttext), 1 bis 30; '
      + 'Vorgabe 3. Mehr als fünf Links entnimmt der Server einer Antwort meist nicht.',

    // ── Links im Antworttext ────────────────────────────────────────
    'feld.DisplayRulesBlock.inline_card_links.label': 'Links im Antworttext',
    'feld.DisplayRulesBlock.inline_card_links.hint':
      'Gedacht für Treffer-Links direkt im Antworttext. Wird derzeit nicht ausgewertet; auch '
      + 'die „Trefferliste im Text“ weiter unten wirkt nicht, der Server hängt keine an.',
    'feld.InlineCardLinksRules.limit.label': 'Anzahl Links',
    'feld.InlineCardLinksRules.limit.hint':
      'Höchstzahl der Treffer-Links im Text, 1 bis 6; Vorgabe 3. Wird derzeit nicht '
      + 'ausgewertet.',
    'feld.InlineCardLinksRules.title_max_chars.label': 'Titellänge',
    'feld.InlineCardLinksRules.title_max_chars.hint':
      'Höchstlänge eines Link-Titels in Zeichen, 30 bis 200; Vorgabe 70. Wird derzeit nicht '
      + 'ausgewertet.',

    // ── Antwortvorschläge ───────────────────────────────────────────
    'feld.DisplayRulesBlock.quick_replies.label': 'Antwortvorschläge',
    'feld.DisplayRulesBlock.quick_replies.hint':
      'Die Vorschlagsknöpfe unter einer Antwort; die meisten schicken beim Klick ihren Text '
      + 'als nächste Nachricht.',
    'feld.QuickRepliesRules.max_count.label': 'Anzahl Vorschläge',
    'feld.QuickRepliesRules.max_count.hint':
      'Wie viele Vorschläge erzeugt und gezeigt werden, 0 bis 6; 0 schaltet sie ab, '
      + 'Vorgabe 4. Ein Wert am Muster geht vor; gepflegte Knöpfe der Kontext-Aktionen sind '
      + 'ausgenommen.',
    'feld.QuickRepliesRules.max_chars.label': 'Zeichen je Vorschlag',
    'feld.QuickRepliesRules.max_chars.hint':
      'Längendeckel je Vorschlag in Zeichen: Längere Vorschläge verwirft der Generator, '
      + 'gekürzt wird nie; 0 = kein Deckel, Vorgabe 48. Die Zahl steht auch im Prompt des '
      + 'Generators.',
    'feld.QuickRepliesRules.inline_fallback_enabled.label': 'Inline-Rückfall',
    'feld.QuickRepliesRules.inline_fallback_enabled.hint':
      'Aus dem Vorgängersystem übernommener Schalter. Wird derzeit nicht ausgewertet, weder '
      + 'vom Server noch vom Widget.',

    // ── Abgleich Text und Anzeige ───────────────────────────────────
    'feld.DisplayRulesBlock.prompt_anzeige_konsistenz.label': 'Abgleich Text und Anzeige',
    'feld.DisplayRulesBlock.prompt_anzeige_konsistenz.hint':
      'Hält den Antworttext bei den Treffern, die unter der Antwort erscheinen: Nach seiner '
      + 'Auswahl bekommt das Modell den Hinweis, nur diese zu nennen.',
    'feld.PromptAnzeigeKonsistenz.enabled.label': 'Hinweis aktiv',
    'feld.PromptAnzeigeKonsistenz.enabled.hint':
      'An: Hat das Modell Treffer zur Anzeige ausgewählt, erinnert ein Zusatzsatz es daran, '
      + 'im Text nur diese zu nennen. Wirkt in der Muster-Engine; Vorgabe: an.',
    'feld.PromptAnzeigeKonsistenz.exclude_patterns.label': 'Ausgenommene Muster',
    'feld.PromptAnzeigeKonsistenz.exclude_patterns.hint':
      'Muster ohne diesen Hinweis, als Kennung wie M04 oder M15; Groß- und Kleinschreibung '
      + 'zählen nicht. Wirkt in der Muster-Engine.',
  },
  en: {
    'feld.DisplayRulesArea.display_rules.label': 'Display rules',
    'feld.DisplayRulesArea.display_rules.hint':
      'What the chat shows and how: document boxes, result boxes, reply suggestions. The chat '
      + 'reads these rules again on every turn, so changes apply from the next answer.',

    // ── Document boxes ──────────────────────────────────────────────
    'feld.DisplayRulesBlock.inline_documents.label': 'Document boxes',
    'feld.DisplayRulesBlock.inline_documents.hint':
      'Long results such as learning paths, generated materials or revisions appear as a '
      + 'framed box in the conversation, with a short accompanying text in the speech bubble.',
    'feld.InlineDocumentsRules.enabled.label': 'Show boxes',
    'feld.InlineDocumentsRules.enabled.hint':
      'Off: learning paths, generated materials and other documents from the model appear in '
      + 'the answer text instead of a box. The full-text view and the preview of a change to '
      + 'WLO stay boxes; default: on.',
    'feld.InlineDocumentsRules.font_size_percent.label': 'Font size',
    'feld.InlineDocumentsRules.font_size_percent.hint':
      'Font size of the box content in percent, default 85 (standard size); smaller numbers '
      + 'mean smaller text. A value outside the limits is refused on save.',
    'feld.InlineDocumentsRules.per_pattern.label': 'Box per pattern',
    'feld.InlineDocumentsRules.per_pattern.hint':
      'On or off per pattern: whether a long answer text with a heading moves into the box. '
      + 'Only affects M09 (learning path), M10 (AI content) and M11 (revision); on if there '
      + 'is no entry.',
    'feld.InlineDocumentsRules.intro_text.label': 'Accompanying text',
    'feld.InlineDocumentsRules.intro_text.hint':
      'One fixed text per pattern in the speech bubble instead of the lead-in from the answer: '
      + 'the key is the pattern ID (M09, M10 or M11), the value the text; {topic_suffix} '
      + 'becomes " zum Thema …" (German) or is dropped without a topic. Without an entry the '
      + 'lead-in stays. Does not apply to boxes the model delivers itself, and appears '
      + 'unchanged in English conversations.',

    // ── Materials box ───────────────────────────────────────────────
    'feld.DisplayRulesBlock.single_content_box.label': 'Materials box',
    'feld.DisplayRulesBlock.single_content_box.hint':
      'The "Selected materials" box with individual items below the answer. How many it shows '
      + 'is set under "Maximum per box".',
    'feld.SingleContentBoxRules.enabled.label': 'Show box',
    'feld.SingleContentBoxRules.enabled.hint':
      'Off: individual items are removed from the results; topic pages and collections remain. '
      + 'Default: on.',
    'feld.SingleContentBoxRules.layout.label': 'Layout',
    'feld.SingleContentBoxRules.layout.hint':
      'Intended as card view (card) or list (list); other values count as card. Currently not '
      + 'evaluated: the widget always shows the box the same way.',
    'feld.SingleContentBoxRules.max_count.label': 'Legacy maximum',
    'feld.SingleContentBoxRules.max_count.hint':
      'Former place for the maximum number of materials. Only takes effect if "Maximum per '
      + 'box" has no value for materials; better maintain it there.',

    // ── Maximum per box ─────────────────────────────────────────────
    'feld.DisplayRulesBlock.groups.label': 'Maximum per box',
    'feld.DisplayRulesBlock.groups.hint':
      'How many entries each result box below the answer shows at most; server and widget '
      + 'both cut to these numbers. In the pattern engine the values also set how many results '
      + 'the model may select (5 to 20).',
    'feld.GroupsRules.themenseiten_max.label': 'Topic pages',
    'feld.GroupsRules.themenseiten_max.hint':
      'Maximum in the "Topic pages" box, 1 to 20; default 3.',
    'feld.GroupsRules.sammlungen_max.label': 'Collections',
    'feld.GroupsRules.sammlungen_max.hint':
      'Maximum in the "Collections" box, 1 to 20; default 3.',
    'feld.GroupsRules.materialien_max.label': 'Materials',
    'feld.GroupsRules.materialien_max.hint':
      'Maximum in the "Selected materials" box, 1 to 8; default 3.',
    'feld.GroupsRules.materialien_max_lernpfad.label': 'Materials in learning paths',
    'feld.GroupsRules.materialien_max_lernpfad.hint':
      'Maximum number of materials when the answer is a learning path (pattern M09), 1 to 8; '
      + 'default 5. The widget still shows at most as many in the box as set under '
      + '"Materials".',
    'feld.GroupsRules.webseiten_max.label': 'Web page contents',
    'feld.GroupsRules.webseiten_max.hint':
      'Maximum in the "Web page contents" box (links from the answer text), 1 to 30; '
      + 'default 3. The server rarely takes more than five links from one answer.',

    // ── Links in the answer text ────────────────────────────────────
    'feld.DisplayRulesBlock.inline_card_links.label': 'Links in answer text',
    'feld.DisplayRulesBlock.inline_card_links.hint':
      'Intended for result links directly in the answer text. Currently not evaluated; the '
      + '“Result list in the text” further down has no effect either, the server appends none.',
    'feld.InlineCardLinksRules.limit.label': 'Number of links',
    'feld.InlineCardLinksRules.limit.hint':
      'Maximum number of result links in the text, 1 to 6; default 3. Currently not '
      + 'evaluated.',
    'feld.InlineCardLinksRules.title_max_chars.label': 'Title length',
    'feld.InlineCardLinksRules.title_max_chars.hint':
      'Maximum length of a link title in characters, 30 to 200; default 70. Currently not '
      + 'evaluated.',

    // ── Reply suggestions ───────────────────────────────────────────
    'feld.DisplayRulesBlock.quick_replies.label': 'Reply suggestions',
    'feld.DisplayRulesBlock.quick_replies.hint':
      'The suggestion buttons below an answer; most of them send their text as the next '
      + 'message when clicked.',
    'feld.QuickRepliesRules.max_count.label': 'Number of suggestions',
    'feld.QuickRepliesRules.max_count.hint':
      'How many suggestions are generated and shown, 0 to 6; 0 turns them off, default 4. A '
      + 'value set on the pattern takes precedence; maintained context-action buttons are '
      + 'exempt.',
    'feld.QuickRepliesRules.max_chars.label': 'Characters per suggestion',
    'feld.QuickRepliesRules.max_chars.hint':
      'Length cap per suggestion in characters: the generator discards longer suggestions and '
      + 'never truncates; 0 = no cap, default 48. The number also appears in the generator’s '
      + 'prompt.',
    'feld.QuickRepliesRules.inline_fallback_enabled.label': 'Inline fallback',
    'feld.QuickRepliesRules.inline_fallback_enabled.hint':
      'Switch carried over from the previous system. Currently not evaluated, neither by the '
      + 'server nor by the widget.',

    // ── Text matches display ────────────────────────────────────────
    'feld.DisplayRulesBlock.prompt_anzeige_konsistenz.label': 'Text matches display',
    'feld.DisplayRulesBlock.prompt_anzeige_konsistenz.hint':
      'Keeps the answer text to the results that appear below the answer: after its selection '
      + 'the model is told to mention only those.',
    'feld.PromptAnzeigeKonsistenz.enabled.label': 'Reminder active',
    'feld.PromptAnzeigeKonsistenz.enabled.hint':
      'On: once the model has selected results for display, an added sentence reminds it to '
      + 'mention only those in the text. Applies in the pattern engine; default: on.',
    'feld.PromptAnzeigeKonsistenz.exclude_patterns.label': 'Excluded patterns',
    'feld.PromptAnzeigeKonsistenz.exclude_patterns.hint':
      'Patterns without this reminder, given as IDs such as M04 or M15; case does not matter. '
      + 'Applies in the pattern engine.',
  },
};
