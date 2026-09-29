/**
 * Feldtexte (ST-1) der Seiten Begrüßung (`01-base/welcome-config`) und
 * Kontext-Aktionen (`01-base/context-actions`).
 *
 * Schlüsselschema aller `fields-*.ts`: siehe `fields-layer-doc.ts`. Die
 * Wirkungen stammen aus dem Lader `services/config_loader/widget.py` (samt
 * Rückfällen), dem Widget (`ui/src/widget/guide-mode-config.ts`,
 * `ui/src/shell/lifecycle.ts`, `ui/src/shell/input-routing.ts`) und dem
 * Backend (`graph/nodes/context_greeting.py`, `domain/page_host.py`,
 * `services/direct_actions.py`). Nicht ausgewertet werden `ContextPill.url`
 * und `ContextPill.params`: der Lader reicht sie nicht weiter.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_BEGRUESSUNG: CataloguePart = {
  de: {
    // ── Begrüßung (01-base/welcome-config) ───────────────────────────
    'feld.WelcomeArea.welcome.label': 'Begrüßung',
    'feld.WelcomeArea.welcome.hint':
      'Begrüßungsblase und Start-Chips einer neuen Unterhaltung. Grüßt Boerdi auf einer erkannten '
      + 'Seite von selbst, entfallen sie; die Einbau-Attribute greeting und start-replies haben '
      + 'Vorrang.',
    'feld.WelcomeBlock.greeting.label': 'Begrüßungstext',
    'feld.WelcomeBlock.greeting.hint':
      'Text der Begrüßungsblase. Der Satz, dass hier eine KI antwortet, muss bleiben (EU AI Act); '
      + 'leer gilt ein eingebauter Text ohne diesen Satz.',
    'feld.WelcomeBlock.quick_replies.label': 'Start-Chips',
    'feld.WelcomeBlock.quick_replies.hint':
      'Chips unter der Begrüßung. Ein Klick sendet den Text als Nachricht, der Tour-Chip startet '
      + 'stattdessen die Web-Tour. Leer: vier eingebaute Chips.',
    'feld.WelcomeBlock.tour_reply.label': 'Tour-Chip',
    'feld.WelcomeBlock.tour_reply.hint':
      'Der Start-Chip, der die Web-Tour startet, statt seinen Text zu senden. Muss wörtlich einem '
      + 'der Start-Chips gleichen; leer gilt nur ein Chip mit genau „Web-Tour starten“ als '
      + 'Tour-Chip.',
    'feld.WelcomeBlock.greeting_en.label': 'Englischer Begrüßungstext',
    'feld.WelcomeBlock.greeting_en.hint':
      'Begrüßungstext für die englische Oberfläche; auch hier gehört der KI-Hinweis hinein. Leer: '
      + 'dort erscheint der deutsche Text.',
    'feld.WelcomeBlock.quick_replies_en.label': 'Englische Start-Chips',
    'feld.WelcomeBlock.quick_replies_en.hint':
      'Start-Chips für die englische Oberfläche. Leer: dort erscheinen die deutschen; schon ein '
      + 'Eintrag ersetzt die ganze deutsche Liste.',
    'feld.WelcomeBlock.tour_reply_en.label': 'Englischer Tour-Chip',
    'feld.WelcomeBlock.tour_reply_en.hint':
      'Tour-Chip der englischen Oberfläche; muss wörtlich einem der englischen Start-Chips '
      + 'gleichen. Leer: Als Tour-Chip zählt nur der deutsche.',

    // ── Kontext-Aktionen (01-base/context-actions) ───────────────────
    'feld.ContextActionsArea.context_actions.label': 'Kontext-Aktionen',
    'feld.ContextActionsArea.context_actions.hint':
      'Begrüßung und Pills, mit denen sich Boerdi auf einer erkannten Seite von selbst meldet, '
      + 'einmal je Seite und Unterhaltung. Beim ersten Öffnen ersetzt das die normale Begrüßung.',
    'feld.ContextActionsBlock.enabled.label': 'Proaktive Begrüßung',
    'feld.ContextActionsBlock.enabled.hint':
      'Schaltet die Begrüßung samt Pills auf erkannten Seiten ein oder aus. Aus: Boerdi meldet '
      + 'sich nirgends von selbst, beim ersten Öffnen erscheint die normale Begrüßung.',
    'feld.ContextActionsBlock.report_url.label': 'Melde-Adresse',
    'feld.ContextActionsBlock.report_url.hint':
      'Ziel der Pills mit Art report. {node_id} wird durch die Kennung des Inhalts bzw. der '
      + 'Sammlung ersetzt, {collection_id} durch die der Sammlung. Leer: WLO-Formular „Inhalt '
      + 'vorschlagen“.',
    'feld.ContextActionsBlock.own_hosts.label': 'Eigene Hosts',
    'feld.ContextActionsBlock.own_hosts.hint':
      'Hostnamen der eigenen Websites, exakt oder als *.beispiel.de (nur Unterdomains). Eine '
      + 'Seite, die sonst nicht erkannt wird, gilt damit als eigene (home), sonst als fremd '
      + '(external). Leer: alles fremd.',
    'feld.ContextActionsBlock.greetings.label': 'Begrüßung je Seitentyp',
    'feld.ContextActionsBlock.greetings.hint':
      'Text je Seitentyp: collection, content, topic, search, home, external, editorial. '
      + 'Platzhalter: {title}, {bestand} (Satz mit Bestandszahlen), {query}, {host}. Leer: '
      + 'eingebauter Text.',
    'feld.ContextActionsBlock.greetings_en.label': 'Englische Begrüßungen',
    'feld.ContextActionsBlock.greetings_en.hint':
      'Begrüßung je Seitentyp für die englische Oberfläche, mit denselben Schlüsseln und '
      + 'Platzhaltern. Leer: deutscher Text.',
    'feld.ContextActionsBlock.pills.label': 'Pills je Seitentyp',
    'feld.ContextActionsBlock.pills.hint':
      'Pills unter der Begrüßung, je Seitentyp wie dort und in dieser Reihenfolge; höchstens acht '
      + 'erscheinen. Eine leere oder ungültige Liste bringt die eingebauten Pills zurück.',
    'feld.ContextActionsBlock.duplicate_greeting.label': 'Dubletten-Begrüßung',
    'feld.ContextActionsBlock.duplicate_greeting.hint':
      'Begrüßung auf einer fremden Seite, die WLO schon enthält, statt des Angebots, sie '
      + 'aufzunehmen. {title} ist der Titel des vorhandenen Eintrags. Leer: eingebauter Text.',
    'feld.ContextActionsBlock.duplicate_greeting_en.label': 'Englische Dubletten-Begrüßung',
    'feld.ContextActionsBlock.duplicate_greeting_en.hint':
      'Dubletten-Begrüßung für die englische Oberfläche, {title} wie dort. Leer: deutscher Text.',
    'feld.ContextActionsBlock.duplicate_pill_label.label': 'Dubletten-Pill',
    'feld.ContextActionsBlock.duplicate_pill_label.hint':
      'Text der einzigen Pill unter der Dubletten-Begrüßung; sie öffnet den vorhandenen Eintrag '
      + 'im Repositorium. Leer: eingebauter Text.',
    'feld.ContextActionsBlock.duplicate_pill_label_en.label': 'Englische Dubletten-Pill',
    'feld.ContextActionsBlock.duplicate_pill_label_en.hint':
      'Text dieser Pill für die englische Oberfläche. Leer: deutscher Text.',
    'feld.ContextActionsBlock.curate_prompt.label': 'Kuratier-Prompt',
    'feld.ContextActionsBlock.curate_prompt.hint':
      'Anweisung an das Sprachmodell für die Aktion curate_collection: das Soll laut Kompendium '
      + 'mit den vorhandenen Inhalten abgleichen. Ohne Kompendium kein Abgleich. Leer: eingebaute '
      + 'Anweisung.',

    // ── Pills je Seitentyp (ContextPill) ─────────────────────────────
    'feld.ContextPill.label.label': 'Beschriftung',
    'feld.ContextPill.label.hint':
      'Text auf der Pill. Bei Art text ist er zugleich die Nachricht, die der Klick sendet, also '
      + 'als Bitte formulieren, die Boerdi versteht. {title} wird durch Titel, Suchbegriff oder '
      + 'Host der Seite ersetzt.',
    'feld.ContextPill.label_en.label': 'Englische Beschriftung',
    'feld.ContextPill.label_en.hint':
      'Pill-Text für die englische Oberfläche; bei Art text zugleich die gesendete Nachricht. '
      + 'Leer: deutscher Text.',
    'feld.ContextPill.kind.label': 'Art',
    'feld.ContextPill.kind.hint':
      'Art der Pill: text sendet die Beschriftung als Nachricht, action startet die gewählte '
      + 'Aktion direkt, report öffnet die Melde-Adresse. Andere Werte lassen die Pill wegfallen.',
    'feld.ContextPill.action.label': 'Aktion',
    'feld.ContextPill.action.hint':
      'Nur für Art action; ohne Aktion fällt die Pill weg. browse_collection zeigt die '
      + 'Sammlungsinhalte, curate_collection prüft sie gegen das Kompendium, '
      + 'generate_learning_path baut einen Lernpfad, show_content_text holt den Volltext.',
    'feld.ContextPill.url.label': 'Adresse',
    'feld.ContextPill.url.hint':
      'Wird derzeit nicht ausgewertet: report-Pills führen immer zur Melde-Adresse.',
    'feld.ContextPill.params.label': 'Parameter',
    'feld.ContextPill.params.hint':
      'Wird derzeit nicht ausgewertet: Sammlung, Inhalt und Titel für eine Aktion setzt der Chat '
      + 'selbst aus der Seite ein.',
  },
  en: {
    'feld.WelcomeArea.welcome.label': 'Greeting',
    'feld.WelcomeArea.welcome.hint':
      'Greeting bubble and starting chips of a new conversation. If Boerdi greets on a recognised '
      + 'page of its own accord, they are left out; the embed attributes greeting and '
      + 'start-replies take precedence.',
    'feld.WelcomeBlock.greeting.label': 'Greeting text',
    'feld.WelcomeBlock.greeting.hint':
      'Text of the greeting bubble. The sentence saying that an AI is answering must stay (EU AI '
      + 'Act); if empty, a built-in text without that sentence applies.',
    'feld.WelcomeBlock.quick_replies.label': 'Starting chips',
    'feld.WelcomeBlock.quick_replies.hint':
      'Chips below the greeting. A click sends the text as a message; the tour chip starts the '
      + 'site tour instead. Empty: four built-in chips.',
    'feld.WelcomeBlock.tour_reply.label': 'Tour chip',
    'feld.WelcomeBlock.tour_reply.hint':
      'The starting chip that starts the site tour instead of sending its text. Must match one of '
      + 'the starting chips word for word; if empty, only a chip reading exactly “Web-Tour '
      + 'starten” counts as the tour chip.',
    'feld.WelcomeBlock.greeting_en.label': 'English greeting text',
    'feld.WelcomeBlock.greeting_en.hint':
      'Greeting text for the English interface; the AI notice belongs here too. Empty: the German '
      + 'text appears there.',
    'feld.WelcomeBlock.quick_replies_en.label': 'English starting chips',
    'feld.WelcomeBlock.quick_replies_en.hint':
      'Starting chips for the English interface. Empty: the German ones appear there; a single '
      + 'entry already replaces the whole German list.',
    'feld.WelcomeBlock.tour_reply_en.label': 'English tour chip',
    'feld.WelcomeBlock.tour_reply_en.hint':
      'Tour chip of the English interface; must match one of the English starting chips word for '
      + 'word. Empty: only the German tour chip counts.',
    'feld.ContextActionsArea.context_actions.label': 'Context actions',
    'feld.ContextActionsArea.context_actions.hint':
      'Greeting and pills with which Boerdi speaks up on a recognised page of its own accord, '
      + 'once per page and conversation. On first opening this replaces the normal greeting.',
    'feld.ContextActionsBlock.enabled.label': 'Proactive greeting',
    'feld.ContextActionsBlock.enabled.hint':
      'Switches the greeting and its pills on recognised pages on or off. Off: Boerdi never '
      + 'speaks up of its own accord; on first opening the normal greeting appears.',
    'feld.ContextActionsBlock.report_url.label': 'Report address',
    'feld.ContextActionsBlock.report_url.hint':
      'Target of pills of kind report. {node_id} is replaced with the ID of the content or '
      + 'collection, {collection_id} with that of the collection. Empty: the WLO form for '
      + 'suggesting content.',
    'feld.ContextActionsBlock.own_hosts.label': 'Own hosts',
    'feld.ContextActionsBlock.own_hosts.hint':
      'Hostnames of our own websites, exact or as *.example.com (subdomains only). A page not '
      + 'recognised otherwise then counts as our own (home), else as foreign (external). Empty: '
      + 'all foreign.',
    'feld.ContextActionsBlock.greetings.label': 'Greeting per page kind',
    'feld.ContextActionsBlock.greetings.hint':
      'Text per page kind: collection, content, topic, search, home, external, editorial. '
      + 'Placeholders: {title}, {bestand} (sentence with holdings figures), {query}, {host}. '
      + 'Empty: built-in text.',
    'feld.ContextActionsBlock.greetings_en.label': 'English greetings',
    'feld.ContextActionsBlock.greetings_en.hint':
      'Greeting per page kind for the English interface, with the same keys and placeholders. '
      + 'Empty: German text.',
    'feld.ContextActionsBlock.pills.label': 'Pills per page kind',
    'feld.ContextActionsBlock.pills.hint':
      'Pills below the greeting, per page kind as there and in this order; at most eight appear. '
      + 'An empty or invalid list brings back the built-in pills.',
    'feld.ContextActionsBlock.duplicate_greeting.label': 'Duplicate greeting',
    'feld.ContextActionsBlock.duplicate_greeting.hint':
      'Greeting on a foreign page that WLO already holds, instead of the offer to add it. {title} '
      + 'is the title of the existing entry. Empty: built-in text.',
    'feld.ContextActionsBlock.duplicate_greeting_en.label': 'English duplicate greeting',
    'feld.ContextActionsBlock.duplicate_greeting_en.hint':
      'Duplicate greeting for the English interface, {title} as there. Empty: German text.',
    'feld.ContextActionsBlock.duplicate_pill_label.label': 'Duplicate pill',
    'feld.ContextActionsBlock.duplicate_pill_label.hint':
      'Text of the only pill below the duplicate greeting; it opens the existing entry in the '
      + 'repository. Empty: built-in text.',
    'feld.ContextActionsBlock.duplicate_pill_label_en.label': 'English duplicate pill',
    'feld.ContextActionsBlock.duplicate_pill_label_en.hint':
      'Text of this pill for the English interface. Empty: German text.',
    'feld.ContextActionsBlock.curate_prompt.label': 'Curation prompt',
    'feld.ContextActionsBlock.curate_prompt.hint':
      'Instruction to the language model for the curate_collection action: compare what the '
      + 'compendium calls for with the existing content. Without a compendium, no comparison. '
      + 'Empty: built-in instruction.',
    'feld.ContextPill.label.label': 'Label',
    'feld.ContextPill.label.hint':
      'Text on the pill. For kind text it is also the message the click sends, so phrase it as a '
      + 'request Boerdi understands. {title} is replaced with the title, search term or host of '
      + 'the page.',
    'feld.ContextPill.label_en.label': 'English label',
    'feld.ContextPill.label_en.hint':
      'Pill text for the English interface; for kind text also the message that is sent. Empty: '
      + 'German text.',
    'feld.ContextPill.kind.label': 'Kind',
    'feld.ContextPill.kind.hint':
      'Kind of pill: text sends the label as a message, action runs the chosen action directly, '
      + 'report opens the report address. Any other value drops the pill.',
    'feld.ContextPill.action.label': 'Action',
    'feld.ContextPill.action.hint':
      'Only for kind action; without it the pill is dropped. browse_collection lists the '
      + 'collection, curate_collection checks it against the compendium, generate_learning_path '
      + 'builds a learning path, show_content_text gets the full text.',
    'feld.ContextPill.url.label': 'Address',
    'feld.ContextPill.url.hint':
      'Currently not evaluated: report pills always lead to the report address.',
    'feld.ContextPill.params.label': 'Parameters',
    'feld.ContextPill.params.hint':
      'Currently not evaluated: the chat fills in collection, content and title for an action '
      + 'from the page itself.',
  },
};
