/**
 * Feldtexte (ST-1) der Web-Tour (`01-base/website-tour`, Seite Domänen-Wissen):
 * der Block und die Einträge seiner Listen — Besucherwege (`TourFlow`),
 * Besuchergruppen (`TourGroup`) und Links (`LabelPath`, geteilt von Stöber- und
 * Kontakt-Links).
 *
 * Schlüsselschema aller `fields-*.ts`: siehe `fields-layer-doc.ts`. Die
 * Wirkungen stammen aus der Zustandsmaschine `domain/tour.py`, dem Knoten
 * `graph/nodes/tour.py` und der Sprachwahl `domain/tour_i18n.py`. Nicht
 * ausgewertet werden `start_label` (kein Leser) und `flows` samt `TourFlow`
 * (reine Doku; die Einstiege erkennt `detect_entry` selbst).
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_TOUR: CataloguePart = {
  de: {
    // ── Web-Tour (01-base/website-tour) ──────────────────────────────
    'feld.WebsiteTourArea.website_tour.label': 'Web-Tour',
    'feld.WebsiteTourArea.website_tour.hint':
      'Die geführte Tour durch WirLernenOnline: Stationen, Texte, Besuchergruppen und Links. '
      + 'Start über den Tour-Chip oder eine Auslöser-Phrase, danach feste Schritte ohne '
      + 'Sprachmodell.',
    'feld.WebsiteTourBlock.enabled.label': 'Tour aktiv',
    'feld.WebsiteTourBlock.enabled.hint':
      'Schaltet die Web-Tour ein oder aus. Aus: Tour-Chip und Auslöser-Phrasen starten keine '
      + 'Tour, die Nachricht beantwortet der normale Chat.',
    'feld.WebsiteTourBlock.base_host.label': 'Website-Adresse',
    'feld.WebsiteTourBlock.base_host.hint':
      'Adresse, die die Tour vor jeden Pfad setzt, etwa https://wirlernenonline.de. Das Widget '
      + 'muss dort eingebettet sein, sonst bemerkt Boerdi die Ankunft auf der nächsten Seite '
      + 'nicht.',
    'feld.WebsiteTourBlock.home_path.label': 'Startseite',
    'feld.WebsiteTourBlock.home_path.hint':
      'Pfad der Startseite, etwa /home/: Ziel des ersten Weiter-Knopfs. Startet die Tour dort, '
      + 'fragt sie gleich nach der Besuchergruppe.',
    'feld.WebsiteTourBlock.content_hub.label': 'Bildungsinhalte-Seite',
    'feld.WebsiteTourBlock.content_hub.hint':
      'Pfad der Bildungsinhalte, etwa /bildungsinhalte/: kurzer Zwischenhalt nach der '
      + 'Gruppenseite. Kommt der Besucher dort an, zeigt die Tour die passenden Angebote.',
    'feld.WebsiteTourBlock.contact_hub.label': 'Mitmach-Seite',
    'feld.WebsiteTourBlock.contact_hub.hint':
      'Pfad der Anfrage- und Mitmach-Seite, etwa /mitmachen/: Ziel und Ende der Tour. Startet die '
      + 'Tour dort oder auf einer Unterseite, zeigt sie gleich den letzten Schritt.',
    'feld.WebsiteTourBlock.start_label.label': 'Start-Beschriftung',
    'feld.WebsiteTourBlock.start_label.hint':
      'Wird derzeit nicht ausgewertet: die Tour startet über den Tour-Chip der Begrüßung oder '
      + 'eine Auslöser-Phrase.',
    'feld.WebsiteTourBlock.trigger_phrases.label': 'Auslöser-Phrasen',
    'feld.WebsiteTourBlock.trigger_phrases.hint':
      'Enthält eine Nachricht eine dieser Phrasen, startet die Tour; läuft sie schon, zeigt sie '
      + 'den aktuellen Schritt erneut. Groß-/Kleinschreibung egal, unter drei Zeichen '
      + 'wirkungslos; eindeutig halten.',
    'feld.WebsiteTourBlock.flows.label': 'Besucherwege',
    'feld.WebsiteTourBlock.flows.hint':
      'Typische Wege von Besuchern, als Nachschlagewerk für die Redaktion. Nur beschreibend: wo '
      + 'die Tour einsteigt, erkennt der Code selbst an der Seite, auf der sie beginnt.',
    'feld.WebsiteTourBlock.intro.label': 'Einstiegstext',
    'feld.WebsiteTourBlock.intro.hint':
      'Erste Tour-Nachricht, wenn die Tour weder auf der Start-, einer Gruppen-, einer Angebots- '
      + 'noch der Mitmach-Seite beginnt; darunter der Knopf zur Startseite.',
    'feld.WebsiteTourBlock.intro_en.label': 'Englischer Einstiegstext',
    'feld.WebsiteTourBlock.intro_en.hint':
      'Einstiegstext für die englische Oberfläche. Leer: deutscher Text.',
    'feld.WebsiteTourBlock.nudge.label': 'Umweg-Hinweis',
    'feld.WebsiteTourBlock.nudge.hint':
      'Hinweis, wenn der Besucher mitten in der Tour auf einer unerwarteten Seite landet; '
      + 'darunter erneut der Weiter-Knopf des aktuellen Schritts.',
    'feld.WebsiteTourBlock.nudge_en.label': 'Englischer Umweg-Hinweis',
    'feld.WebsiteTourBlock.nudge_en.hint':
      'Umweg-Hinweis für die englische Oberfläche. Leer: deutscher Text.',
    'feld.WebsiteTourBlock.explore.label': 'Stöber-Text',
    'feld.WebsiteTourBlock.explore.hint':
      'Text, wenn der Besucher im Angebots-Schritt (solutions) eine der verlinkten Angebots-, '
      + 'Stöber- oder Gruppenseiten öffnet; darunter der Knopf zur Anfrage.',
    'feld.WebsiteTourBlock.explore_en.label': 'Englischer Stöber-Text',
    'feld.WebsiteTourBlock.explore_en.hint':
      'Stöber-Text für die englische Oberfläche. Leer: deutscher Text.',
    'feld.WebsiteTourBlock.entry.label': 'Quereinstiegs-Texte',
    'feld.WebsiteTourBlock.entry.hint':
      'Texte für einen Start mitten in der Tour. Ausgewertet werden nur solutions (Start auf '
      + 'einer Gruppen- oder Angebotsseite) und solutions_en, mit {group}; leer bleibt nur die '
      + 'Angebotsliste.',
    'feld.WebsiteTourBlock.groups.label': 'Besuchergruppen',
    'feld.WebsiteTourBlock.groups.hint':
      'Gruppen, aus denen der Besucher im Gruppen-Schritt wählt; jede wird ein Chip, in dieser '
      + 'Reihenfolge. Erkennt die Tour zweimal keine Gruppe, endet sie.',
    'feld.WebsiteTourBlock.content_sublinks.label': 'Stöber-Links',
    'feld.WebsiteTourBlock.content_sublinks.hint':
      'Links zum Stöbern im Angebots-Schritt, unter der Überschrift aus den Schritt-Texten. '
      + 'Öffnet der Besucher einen davon, gilt das als Abstecher, nicht als Umweg.',
    'feld.WebsiteTourBlock.contact_links.label': 'Kontakt-Links',
    'feld.WebsiteTourBlock.contact_links.hint':
      'Links, die der letzte Schritt auf der Mitmach-Seite unter seiner Überschrift zeigt. Knapp '
      + 'halten: hier soll der Besucher zur Anfrage finden.',
    'feld.WebsiteTourBlock.steps.label': 'Schritt-Texte',
    'feld.WebsiteTourBlock.steps.hint':
      'Texte und Knöpfe je Schritt (intro, group, group_page, content, solutions, contact) als '
      + 'JSON, je mit _en-Fassung. {group} wirkt in group_page, content.text, solutions.text und '
      + 'solutions.angebote_label.',

    // ── Besucherwege (TourFlow) ──────────────────────────────────────
    'feld.TourFlow.id.label': 'Kurzname',
    'feld.TourFlow.id.hint':
      'Kurzname des Wegs, etwa A1 oder D2. Nur beschreibend.',
    'feld.TourFlow.weg.label': 'Weg',
    'feld.TourFlow.weg.hint':
      'Die Stationen des Wegs, etwa Startseite → Produkt/Angebot → Anfrage. Nur beschreibend.',
    'feld.TourFlow.bedeutung.label': 'Bedeutung',
    'feld.TourFlow.bedeutung.hint':
      'Was der Weg über den Besucher und sein Anliegen sagt. Nur beschreibend.',
    'feld.TourFlow.tour_einstieg.label': 'Tour-Einstieg',
    'feld.TourFlow.tour_einstieg.hint':
      'Schritt, an dem die Tour auf diesem Weg einsetzt, etwa intro, solutions oder contact. Nur '
      + 'beschreibend: die Einstiege legt der Code fest.',

    // ── Besuchergruppen (TourGroup) ──────────────────────────────────
    'feld.TourGroup.id.label': 'Kennung',
    'feld.TourGroup.id.hint':
      'Kennung der Gruppe, etwa lehrkraft. Die laufende Tour merkt sich die Gruppe darüber; '
      + 'eindeutig halten.',
    'feld.TourGroup.label.label': 'Gruppenname',
    'feld.TourGroup.label.hint':
      'Text des Gruppen-Chips; der Klick sendet ihn als Antwort. Er ersetzt {group} in den '
      + 'Schritt-Texten und zählt beim Erkennen getippter Antworten mit.',
    'feld.TourGroup.label_en.label': 'Englischer Gruppenname',
    'feld.TourGroup.label_en.hint':
      'Chip-Text für die englische Oberfläche; dort erkennt die Tour die Gruppe auch daran. Leer: '
      + 'deutscher Name.',
    'feld.TourGroup.synonyms.label': 'Synonyme',
    'feld.TourGroup.synonyms.hint':
      'Weitere Wörter, an denen die Tour getippte Antworten dieser Gruppe zuordnet: als Teil der '
      + 'Nachricht, Groß-/Kleinschreibung egal, ab drei Zeichen. Gelten in beiden Sprachen; die '
      + 'erste passende Gruppe gewinnt.',
    'feld.TourGroup.page.label': 'Gruppenseite',
    'feld.TourGroup.page.hint':
      'Pfad der Zielgruppenseite, etwa /home/redaktionen/: nächster Halt nach der Gruppenwahl. '
      + 'Startet die Tour dort, springt sie gleich zu den Angeboten; teilen sich Gruppen eine '
      + 'Seite, gilt die erste.',
    'feld.TourGroup.angebote.label': 'Angebote',
    'feld.TourGroup.angebote.hint':
      'Passende Angebotsseiten als JSON-Liste mit label, label_en und path. Der Angebots-Schritt '
      + 'verlinkt sie; startet die Tour auf einer davon, gilt die erste Gruppe, die sie führt.',

    // ── Links (LabelPath: Stöber- und Kontakt-Links) ─────────────────
    'feld.LabelPath.label.label': 'Linktext',
    'feld.LabelPath.label.hint':
      'Text des Links, wie er in der Tour-Nachricht steht.',
    'feld.LabelPath.label_en.label': 'Englischer Linktext',
    'feld.LabelPath.label_en.hint':
      'Linktext für die englische Oberfläche. Leer: deutscher Text.',
    'feld.LabelPath.path.label': 'Pfad',
    'feld.LabelPath.path.hint':
      'Pfad der Zielseite, etwa /fachportale/; die Tour setzt die Website-Adresse davor. Ohne '
      + 'Pfad entfällt der Link.',
    // Paket 15 (D2): die Schritte der Tour als Felder — bis dahin ein JSON-Kasten.
    'feld.TourSteps.intro.label': '1 · Startseite',
    'feld.TourSteps.intro.hint': 'Der erste Schritt: zurück zur Startseite der Plattform.',
    'feld.TourSteps.group.label': '2 · Wer bist du?',
    'feld.TourSteps.group.hint': 'Die Frage nach der Besuchergruppe, mit der die Tour beginnt.',
    'feld.TourSteps.group_page.label': '3 · Seite der Gruppe',
    'feld.TourSteps.group_page.hint': 'Die Seite, die zur gewählten Gruppe passt.',
    'feld.TourSteps.content.label': '4 · Bildungsinhalte',
    'feld.TourSteps.content.hint': 'Der Weg zu den Bildungsinhalten.',
    'feld.TourSteps.solutions.label': '5 · Angebote',
    'feld.TourSteps.solutions.hint': 'Was die Gruppe bei WLO findet, mit den Angeboten der Gruppe.',
    'feld.TourSteps.contact.label': '6 · Mitmachen',
    'feld.TourSteps.contact.hint': 'Der Abschluss: Kontakt und Mitmachen.',
    'feld.TourStepIntro.nav_label.label': 'Knopf zum nächsten Schritt',
    'feld.TourStepIntro.nav_label.hint': 'Beschriftung des Knopfs, der die Seite öffnet. Leer: die Vorgabe.',
    'feld.TourStepIntro.nav_label_en.label': 'Knopf (englisch)',
    'feld.TourStepIntro.nav_label_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepGroup.text.label': 'Text des Schritts',
    'feld.TourStepGroup.text.hint': 'Was der Chatbot in diesem Schritt schreibt.',
    'feld.TourStepGroup.text_en.label': 'Text (englisch)',
    'feld.TourStepGroup.text_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepGroup.unsure_label.label': 'Knopf „Weiß nicht“',
    'feld.TourStepGroup.unsure_label.hint': 'Beschriftung für Besucher, die keine Gruppe wählen wollen.',
    'feld.TourStepGroup.unsure_label_en.label': 'Knopf „Weiß nicht“ (englisch)',
    'feld.TourStepGroup.unsure_label_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepGroup.unsure_text.label': 'Text bei „Weiß nicht“',
    'feld.TourStepGroup.unsure_text.hint': 'Steht vor dem Text des Schritts, wenn jemand „Weiß nicht“ wählt.',
    'feld.TourStepGroup.unsure_text_en.label': 'Text bei „Weiß nicht“ (englisch)',
    'feld.TourStepGroup.unsure_text_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepGroupPage.nav_label.label': 'Knopf zum nächsten Schritt',
    'feld.TourStepGroupPage.nav_label.hint': 'Beschriftung des Knopfs, der die Seite öffnet. Leer: die Vorgabe.',
    'feld.TourStepGroupPage.nav_label_en.label': 'Knopf (englisch)',
    'feld.TourStepGroupPage.nav_label_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepGroupPage.text.label': 'Text des Schritts',
    'feld.TourStepGroupPage.text.hint': 'Was der Chatbot in diesem Schritt schreibt.',
    'feld.TourStepGroupPage.text_en.label': 'Text (englisch)',
    'feld.TourStepGroupPage.text_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepContent.nav_label.label': 'Knopf zum nächsten Schritt',
    'feld.TourStepContent.nav_label.hint': 'Beschriftung des Knopfs, der die Seite öffnet. Leer: die Vorgabe.',
    'feld.TourStepContent.nav_label_en.label': 'Knopf (englisch)',
    'feld.TourStepContent.nav_label_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepContent.text.label': 'Text des Schritts',
    'feld.TourStepContent.text.hint': 'Was der Chatbot in diesem Schritt schreibt.',
    'feld.TourStepContent.text_en.label': 'Text (englisch)',
    'feld.TourStepContent.text_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepSolutions.nav_label.label': 'Knopf zum nächsten Schritt',
    'feld.TourStepSolutions.nav_label.hint': 'Beschriftung des Knopfs, der die Seite öffnet. Leer: die Vorgabe.',
    'feld.TourStepSolutions.nav_label_en.label': 'Knopf (englisch)',
    'feld.TourStepSolutions.nav_label_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepSolutions.text.label': 'Text des Schritts',
    'feld.TourStepSolutions.text.hint': 'Was der Chatbot in diesem Schritt schreibt.',
    'feld.TourStepSolutions.text_en.label': 'Text (englisch)',
    'feld.TourStepSolutions.text_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepSolutions.angebote_label.label': 'Überschrift der Angebote',
    'feld.TourStepSolutions.angebote_label.hint': 'Steht über den Angeboten der gewählten Gruppe.',
    'feld.TourStepSolutions.angebote_label_en.label': 'Überschrift der Angebote (englisch)',
    'feld.TourStepSolutions.angebote_label_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepSolutions.sublinks_label.label': 'Überschrift der Stöber-Links',
    'feld.TourStepSolutions.sublinks_label.hint': 'Steht über den Stöber-Links.',
    'feld.TourStepSolutions.sublinks_label_en.label': 'Überschrift der Stöber-Links (englisch)',
    'feld.TourStepSolutions.sublinks_label_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepContact.text.label': 'Text des Schritts',
    'feld.TourStepContact.text.hint': 'Was der Chatbot in diesem Schritt schreibt.',
    'feld.TourStepContact.text_en.label': 'Text (englisch)',
    'feld.TourStepContact.text_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
    'feld.TourStepContact.links_label.label': 'Überschrift der Kontakt-Links',
    'feld.TourStepContact.links_label.hint': 'Steht über den Kontakt-Links.',
    'feld.TourStepContact.links_label_en.label': 'Überschrift der Kontakt-Links (englisch)',
    'feld.TourStepContact.links_label_en.hint': 'Leer: der deutsche Text gilt auch auf Englisch.',
  },
  en: {
    'feld.WebsiteTourArea.website_tour.label': 'Site tour',
    'feld.WebsiteTourArea.website_tour.hint':
      'The guided tour through WirLernenOnline: stops, texts, visitor groups and links. Start via '
      + 'the tour chip or a trigger phrase, then fixed steps without a language model.',
    'feld.WebsiteTourBlock.enabled.label': 'Tour active',
    'feld.WebsiteTourBlock.enabled.hint':
      'Switches the site tour on or off. Off: neither the tour chip nor trigger phrases start a '
      + 'tour; the normal chat answers the message.',
    'feld.WebsiteTourBlock.base_host.label': 'Website address',
    'feld.WebsiteTourBlock.base_host.hint':
      'Address the tour puts in front of every path, such as https://wirlernenonline.de. The '
      + 'widget must be embedded there, otherwise Boerdi does not notice the arrival on the next '
      + 'page.',
    'feld.WebsiteTourBlock.home_path.label': 'Home page',
    'feld.WebsiteTourBlock.home_path.hint':
      'Path of the home page, such as /home/: target of the first next button. If the tour starts '
      + 'there, it asks for the visitor group straight away.',
    'feld.WebsiteTourBlock.content_hub.label': 'Educational content page',
    'feld.WebsiteTourBlock.content_hub.hint':
      'Path of the educational content, such as /bildungsinhalte/: a short stop after the group '
      + 'page. When the visitor arrives there, the tour shows the matching offers.',
    'feld.WebsiteTourBlock.contact_hub.label': 'Get-involved page',
    'feld.WebsiteTourBlock.contact_hub.hint':
      'Path of the enquiry and get-involved page, such as /mitmachen/: goal and end of the tour. '
      + 'If the tour starts there or on a subpage, it shows the last step straight away.',
    'feld.WebsiteTourBlock.start_label.label': 'Start label',
    'feld.WebsiteTourBlock.start_label.hint':
      'Currently not evaluated: the tour starts via the tour chip of the greeting or a trigger '
      + 'phrase.',
    'feld.WebsiteTourBlock.trigger_phrases.label': 'Trigger phrases',
    'feld.WebsiteTourBlock.trigger_phrases.hint':
      'If a message contains one of these phrases, the tour starts; if it is already running, it '
      + 'shows the current step again. Case-insensitive, no effect below three characters; keep '
      + 'them unambiguous.',
    'feld.WebsiteTourBlock.flows.label': 'Visitor routes',
    'feld.WebsiteTourBlock.flows.hint':
      'Typical visitor routes, as a reference for the editorial team. Descriptive only: the code '
      + 'itself works out where the tour joins from the page it begins on.',
    'feld.WebsiteTourBlock.intro.label': 'Intro text',
    'feld.WebsiteTourBlock.intro.hint':
      'First tour message when the tour begins on none of the home, group, offer or get-involved '
      + 'pages; below it the button to the home page.',
    'feld.WebsiteTourBlock.intro_en.label': 'English intro text',
    'feld.WebsiteTourBlock.intro_en.hint':
      'Intro text for the English interface. Empty: German text.',
    'feld.WebsiteTourBlock.nudge.label': 'Detour hint',
    'feld.WebsiteTourBlock.nudge.hint':
      'Hint when the visitor lands on an unexpected page in the middle of the tour; below it the '
      + 'next button of the current step again.',
    'feld.WebsiteTourBlock.nudge_en.label': 'English detour hint',
    'feld.WebsiteTourBlock.nudge_en.hint':
      'Detour hint for the English interface. Empty: German text.',
    'feld.WebsiteTourBlock.explore.label': 'Browsing text',
    'feld.WebsiteTourBlock.explore.hint':
      'Text when the visitor, in the offers step (solutions), opens one of the linked offer, '
      + 'browsing or group pages; below it the button to the enquiry.',
    'feld.WebsiteTourBlock.explore_en.label': 'English browsing text',
    'feld.WebsiteTourBlock.explore_en.hint':
      'Browsing text for the English interface. Empty: German text.',
    'feld.WebsiteTourBlock.entry.label': 'Mid-tour entry texts',
    'feld.WebsiteTourBlock.entry.hint':
      'Texts for a start in the middle of the tour. Only solutions (start on a group or offer '
      + 'page) and solutions_en are evaluated, with {group}; if empty, only the list of offers '
      + 'remains.',
    'feld.WebsiteTourBlock.groups.label': 'Visitor groups',
    'feld.WebsiteTourBlock.groups.hint':
      'Groups the visitor chooses from in the group step; each becomes a chip, in this order. If '
      + 'the tour recognises no group twice, it ends.',
    'feld.WebsiteTourBlock.content_sublinks.label': 'Browsing links',
    'feld.WebsiteTourBlock.content_sublinks.hint':
      'Links for browsing in the offers step, under the heading from the step texts. If the '
      + 'visitor opens one of them, it counts as a side trip, not as a detour.',
    'feld.WebsiteTourBlock.contact_links.label': 'Contact links',
    'feld.WebsiteTourBlock.contact_links.hint':
      'Links the last step shows on the get-involved page, under its heading. Keep them short: '
      + 'this is where the visitor should find the enquiry.',
    'feld.WebsiteTourBlock.steps.label': 'Step texts',
    'feld.WebsiteTourBlock.steps.hint':
      'Texts and buttons per step (intro, group, group_page, content, solutions, contact) as '
      + 'JSON, each with an _en version. {group} works in group_page, content.text, '
      + 'solutions.text and solutions.angebote_label.',
    'feld.TourFlow.id.label': 'Short name',
    'feld.TourFlow.id.hint':
      'Short name of the route, such as A1 or D2. Descriptive only.',
    'feld.TourFlow.weg.label': 'Route',
    'feld.TourFlow.weg.hint':
      'The stops along the route, such as home page → product/offer → enquiry. Descriptive only.',
    'feld.TourFlow.bedeutung.label': 'Meaning',
    'feld.TourFlow.bedeutung.hint':
      'What the route says about the visitor and their concern. Descriptive only.',
    'feld.TourFlow.tour_einstieg.label': 'Tour entry point',
    'feld.TourFlow.tour_einstieg.hint':
      'Step at which the tour joins on this route, such as intro, solutions or contact. '
      + 'Descriptive only: the code sets the entry points.',
    'feld.TourGroup.id.label': 'Identifier',
    'feld.TourGroup.id.hint':
      'Identifier of the group, such as lehrkraft. The running tour remembers the group by it; '
      + 'keep it unique.',
    'feld.TourGroup.label.label': 'Group name',
    'feld.TourGroup.label.hint':
      'Text of the group chip; the click sends it as the answer. It replaces {group} in the step '
      + 'texts and counts when typed answers are matched.',
    'feld.TourGroup.label_en.label': 'English group name',
    'feld.TourGroup.label_en.hint':
      'Chip text for the English interface; there the tour also recognises the group by it. '
      + 'Empty: German name.',
    'feld.TourGroup.synonyms.label': 'Synonyms',
    'feld.TourGroup.synonyms.hint':
      'Further words by which the tour assigns typed answers to this group: as part of the '
      + 'message, case-insensitive, from three characters. They apply in both languages; the '
      + 'first matching group wins.',
    'feld.TourGroup.page.label': 'Group page',
    'feld.TourGroup.page.hint':
      'Path of the audience page, such as /home/redaktionen/: next stop after choosing the group. '
      + 'If the tour starts there, it jumps straight to the offers; if groups share a page, the '
      + 'first applies.',
    'feld.TourGroup.angebote.label': 'Offers',
    'feld.TourGroup.angebote.hint':
      'Matching offer pages as a JSON list with label, label_en and path. The offers step links '
      + 'them; if the tour starts on one of them, the first group listing it applies.',
    'feld.LabelPath.label.label': 'Link text',
    'feld.LabelPath.label.hint':
      'Text of the link as it appears in the tour message.',
    'feld.LabelPath.label_en.label': 'English link text',
    'feld.LabelPath.label_en.hint':
      'Link text for the English interface. Empty: German text.',
    'feld.LabelPath.path.label': 'Path',
    'feld.LabelPath.path.hint':
      'Path of the target page, such as /fachportale/; the tour puts the website address in '
      + 'front. Without a path, the link is left out.',
    // Paket 15 (D2): die Schritte der Tour als Felder — bis dahin ein JSON-Kasten.
    'feld.TourSteps.intro.label': '1 · Start',
    'feld.TourSteps.intro.hint': 'The first step: back to the platform home page.',
    'feld.TourSteps.group.label': '2 · Who are you?',
    'feld.TourSteps.group.hint': 'The question about the visitor group the tour starts with.',
    'feld.TourSteps.group_page.label': '3 · Group page',
    'feld.TourSteps.group_page.hint': 'The page that fits the chosen group.',
    'feld.TourSteps.content.label': '4 · Educational content',
    'feld.TourSteps.content.hint': 'The way to the educational content.',
    'feld.TourSteps.solutions.label': '5 · Offers',
    'feld.TourSteps.solutions.hint': 'What the group finds at WLO, with the group’s offers.',
    'feld.TourSteps.contact.label': '6 · Get involved',
    'feld.TourSteps.contact.hint': 'The end: contact and getting involved.',
    'feld.TourStepIntro.nav_label.label': 'Button to the next step',
    'feld.TourStepIntro.nav_label.hint': 'Label of the button that opens the page. Empty: the default.',
    'feld.TourStepIntro.nav_label_en.label': 'Button (English)',
    'feld.TourStepIntro.nav_label_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepGroup.text.label': 'Step text',
    'feld.TourStepGroup.text.hint': 'What the chatbot writes in this step.',
    'feld.TourStepGroup.text_en.label': 'Text (English)',
    'feld.TourStepGroup.text_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepGroup.unsure_label.label': 'Button “Not sure”',
    'feld.TourStepGroup.unsure_label.hint': 'Label for visitors who do not want to pick a group.',
    'feld.TourStepGroup.unsure_label_en.label': 'Button “Not sure” (English)',
    'feld.TourStepGroup.unsure_label_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepGroup.unsure_text.label': 'Text for “Not sure”',
    'feld.TourStepGroup.unsure_text.hint': 'Shown before the step text when someone picks “Not sure”.',
    'feld.TourStepGroup.unsure_text_en.label': 'Text for “Not sure” (English)',
    'feld.TourStepGroup.unsure_text_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepGroupPage.nav_label.label': 'Button to the next step',
    'feld.TourStepGroupPage.nav_label.hint': 'Label of the button that opens the page. Empty: the default.',
    'feld.TourStepGroupPage.nav_label_en.label': 'Button (English)',
    'feld.TourStepGroupPage.nav_label_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepGroupPage.text.label': 'Step text',
    'feld.TourStepGroupPage.text.hint': 'What the chatbot writes in this step.',
    'feld.TourStepGroupPage.text_en.label': 'Text (English)',
    'feld.TourStepGroupPage.text_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepContent.nav_label.label': 'Button to the next step',
    'feld.TourStepContent.nav_label.hint': 'Label of the button that opens the page. Empty: the default.',
    'feld.TourStepContent.nav_label_en.label': 'Button (English)',
    'feld.TourStepContent.nav_label_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepContent.text.label': 'Step text',
    'feld.TourStepContent.text.hint': 'What the chatbot writes in this step.',
    'feld.TourStepContent.text_en.label': 'Text (English)',
    'feld.TourStepContent.text_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepSolutions.nav_label.label': 'Button to the next step',
    'feld.TourStepSolutions.nav_label.hint': 'Label of the button that opens the page. Empty: the default.',
    'feld.TourStepSolutions.nav_label_en.label': 'Button (English)',
    'feld.TourStepSolutions.nav_label_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepSolutions.text.label': 'Step text',
    'feld.TourStepSolutions.text.hint': 'What the chatbot writes in this step.',
    'feld.TourStepSolutions.text_en.label': 'Text (English)',
    'feld.TourStepSolutions.text_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepSolutions.angebote_label.label': 'Heading of the offers',
    'feld.TourStepSolutions.angebote_label.hint': 'Shown above the chosen group’s offers.',
    'feld.TourStepSolutions.angebote_label_en.label': 'Heading of the offers (English)',
    'feld.TourStepSolutions.angebote_label_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepSolutions.sublinks_label.label': 'Heading of the browse links',
    'feld.TourStepSolutions.sublinks_label.hint': 'Shown above the browse links.',
    'feld.TourStepSolutions.sublinks_label_en.label': 'Heading of the browse links (English)',
    'feld.TourStepSolutions.sublinks_label_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepContact.text.label': 'Step text',
    'feld.TourStepContact.text.hint': 'What the chatbot writes in this step.',
    'feld.TourStepContact.text_en.label': 'Text (English)',
    'feld.TourStepContact.text_en.hint': 'Empty: the German text applies in English too.',
    'feld.TourStepContact.links_label.label': 'Heading of the contact links',
    'feld.TourStepContact.links_label.hint': 'Shown above the contact links.',
    'feld.TourStepContact.links_label_en.label': 'Heading of the contact links (English)',
    'feld.TourStepContact.links_label_en.hint': 'Empty: the German text applies in English too.',
  },
};
