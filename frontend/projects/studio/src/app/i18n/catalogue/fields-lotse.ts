/**
 * Feldtexte (ST-1) der Seite „Domain-Wissen“, Bereiche Lotse (`01-base/guide-mode`)
 * und Lotsen-Regeln (`02-domain/guide-rules`).
 *
 * Schlüsselschema wie in allen `fields-*.ts` (siehe `fields-layer-doc.ts`).
 * `default_enabled` ist gestrichen (Paket 7; das Widget hat keinen Lotsen-Schalter
 * mehr, `ui/src/widget/guide-boot.ts`). Nicht ausgewertet werden die ganzen
 * `rag_area_rules`: der Lotse nimmt dafür die eingebaute Liste `_RAG_AREA_URLS`
 * in `services/guide_qr_injector.py`. Derselbe Dienst übersetzt die
 * `message_rules` neu, sobald sie sich ändern (2026-10-01) — ohne Neustart; ein
 * ungültiges Muster weist schon das Speichern ab (Paket 4, D6).
 * `max_guide_targets_per_turn` wirkt nur mit 0 oder über 20, weil
 * `services/widget_postprocess.py` ohnehin bis zu 20 Karten ein Sprungziel gibt;
 * dieses Ziel (`guide_url`) nutzt das Widget nur ohne eigenen Kartenlink
 * (`ui/src/cards/card-utils.ts`). `trusted_domains` ersetzt die
 * Umgebungsvariable `GUIDE_TRUSTED_DOMAINS` ganz (`services/config_loader/safety.py`).
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_LOTSE: CataloguePart = {
  de: {
    // ── Lotse (01-base/guide-mode) ──────────────────────────────────
    'feld.GuideModeArea.guide_mode.label': 'Lotsen-Einstellungen',
    'feld.GuideModeArea.guide_mode.hint':
      'Wie der Lotse auf Seiten der Plattform führt: Knöpfe „Bring mich hin“ unter Antworten '
      + 'und Sprungziele an Karten, dazu die freigegebenen Hosts und die Domains, zu denen das '
      + 'Gespräch mitwandert.',
    'feld.GuideModeBlock.max_guide_targets_per_turn.label': 'Karten mit Sprungziel',
    'feld.GuideModeBlock.max_guide_targets_per_turn.hint':
      'Höchstzahl der Karten je Antwort mit Sprungziel; 0 = unbegrenzt, ohne Eintrag 5. Werte '
      + 'von 1 bis 20 wirken derzeit nicht: die Nachbearbeitung der Antwort vergibt ohnehin bis '
      + 'zu 20 Sprungziele.',
    'feld.GuideModeBlock.max_guide_quick_replies.label': 'Lotsen-Knöpfe je Antwort',
    'feld.GuideModeBlock.max_guide_quick_replies.hint':
      'Höchstzahl der Knöpfe „Bring mich hin“ unter einer Antwort, 1 bis 3; ohne Eintrag 2. Die '
      + 'Knöpfe stehen vor den übrigen Antwortvorschlägen.',
    'feld.GuideModeBlock.url_fields_priority.label': 'Reihenfolge der Kartenfelder',
    'feld.GuideModeBlock.url_fields_priority.hint':
      'Reihenfolge, in der das Sprungziel einer Karte gesucht wird, etwa topic_page_url vor '
      + 'wlo_url; das erste Feld mit freigegebenem Host gilt, leer = eingebaute Reihenfolge. Das '
      + 'Widget nutzt das Ziel nur ohne eigenen Kartenlink.',
    'feld.GuideModeBlock.allowed_hosts.label': 'Freigegebene Hosts',
    'feld.GuideModeBlock.allowed_hosts.hint':
      'Hosts, auf denen der Lotse erscheint und zu denen er führt; *.openeduhub.net deckt alle '
      + 'Subdomains ab, nicht openeduhub.net selbst. Kartenlinks zu anderen Hosts ersetzt der '
      + 'Chat durch den Link ins Repositorium.',
    'feld.GuideModeBlock.trusted_domains.label': 'Vertraute Domains',
    'feld.GuideModeBlock.trusted_domains.hint':
      'Links zu diesen Domains nehmen die Sitzung mit — das Gespräch läuft auf der Zielseite '
      + 'weiter — und das Widget zeigt dort keine Warnung „Externe URL“. Wohin Lotsen-Knöpfe '
      + 'führen, regeln die freigegebenen Hosts. Die Umgebungsvariable GUIDE_TRUSTED_DOMAINS '
      + 'ersetzt die Liste, wenn gesetzt.',

    // ── Lotsen-Regeln (02-domain/guide-rules) ───────────────────────
    'feld.GuideRulesArea.message_rules.label': 'Nachrichten-Regeln',
    'feld.GuideRulesArea.message_rules.hint':
      'Passt eine Nutzernachricht auf eine Regel, bietet der Lotse einen Knopf „Bring mich hin“ '
      + 'zur hinterlegten Seite an; leer = eingebaute Regeln. Änderungen wirken sofort.',
    'feld.GuideRulesArea.rag_area_rules.label': 'Regeln je Wissensbereich',
    'feld.GuideRulesArea.rag_area_rules.hint':
      'Gedacht: Knopf zur Webseite eines Wissensbereichs, wenn die Antwort ihn beim Namen nennt '
      + '(Schlüssel = Bereichsname). Wird derzeit nicht ausgewertet: der Chat nutzt eine fest '
      + 'eingebaute Liste.',
    'feld.MessageRule.pattern.label': 'Suchausdruck',
    'feld.MessageRule.pattern.hint':
      'Regulärer Ausdruck, der in der Nutzernachricht gesucht wird, Groß-/Kleinschreibung egal; '
      + 'leer = Regel fällt weg. Ein ungültiger Ausdruck wird beim Speichern abgewiesen.',
    'feld.MessageRule.label.label': 'Beschriftung',
    'feld.MessageRule.label.hint':
      'Text auf dem Knopf, etwa „Themenseite Klimawandel“; leer = Regel fällt weg.',
    'feld.MessageRule.label_en.label': 'Englische Beschriftung',
    'feld.MessageRule.label_en.hint':
      'Knopftext für die englische Oberfläche. Leer: deutsche Beschriftung.',
    'feld.MessageRule.url.label': 'Zieladresse',
    'feld.MessageRule.url.hint':
      'Seite, zu der der Knopf führt (http wird zu https); leer = Regel fällt weg. Der Knopf '
      + 'erscheint nur, wenn ihr Host unter „Freigegebene Hosts“ steht, und eine bloße Startseite '
      + 'ohne Pfad rückt hinter Links aus der Antwort.',
    'feld.MessageRule.priority.label': 'Priorität',
    'feld.MessageRule.priority.hint':
      'Passen mehrere Regeln, gewinnt die höchste Zahl, bei Gleichstand die weiter oben; je '
      + 'Nachricht zählt nur eine Regel. Ohne Eintrag 50, auch 0 gilt als 50.',
    'feld.RagAreaRule.label.label': 'Beschriftung',
    'feld.RagAreaRule.label.hint':
      'Gedacht: Text auf dem Knopf zur Webseite des Wissensbereichs. Wird derzeit nicht '
      + 'ausgewertet: der Chat nutzt fest eingebaute Beschriftungen.',
    'feld.RagAreaRule.url.label': 'Zieladresse',
    'feld.RagAreaRule.url.hint':
      'Gedacht: Webseite des Wissensbereichs, zu der der Knopf führt. Wird derzeit nicht '
      + 'ausgewertet: der Chat nutzt fest eingebaute Adressen.',
    'feld.RagAreaRule.brand_pattern.label': 'Namens-Ausdruck',
    'feld.RagAreaRule.brand_pattern.hint':
      'Gedacht: regulärer Ausdruck, der prüft, ob die Antwort den Bereich beim Namen nennt; nur '
      + 'dann käme der Knopf. Wird derzeit nicht ausgewertet: der Chat nutzt fest eingebaute '
      + 'Ausdrücke.',
  },
  en: {
    // ── Guide (01-base/guide-mode) ──────────────────────────────────
    'feld.GuideModeArea.guide_mode.label': 'Guide settings',
    'feld.GuideModeArea.guide_mode.hint':
      'How the guide leads to platform pages: “Take me there” buttons below answers and jump '
      + 'targets on cards, plus the allowed hosts and the domains the conversation carries over '
      + 'to.',
    'feld.GuideModeBlock.max_guide_targets_per_turn.label': 'Cards with jump target',
    'feld.GuideModeBlock.max_guide_targets_per_turn.hint':
      'Maximum number of cards per answer with a jump target; 0 = unlimited, 5 without an '
      + 'entry. Values from 1 to 20 currently have no effect: post-processing of the answer '
      + 'assigns up to 20 jump targets anyway.',
    'feld.GuideModeBlock.max_guide_quick_replies.label': 'Guide buttons per answer',
    'feld.GuideModeBlock.max_guide_quick_replies.hint':
      'Maximum number of “Take me there” buttons below an answer, 1 to 3; 2 without an entry. '
      + 'They come before the other suggested replies.',
    'feld.GuideModeBlock.url_fields_priority.label': 'Card field order',
    'feld.GuideModeBlock.url_fields_priority.hint':
      'Order in which the jump target of a card is looked up, such as topic_page_url before '
      + 'wlo_url; the first field with an allowed host wins, empty = built-in order. The widget '
      + 'only uses the target if the card has no link of its own.',
    'feld.GuideModeBlock.allowed_hosts.label': 'Allowed hosts',
    'feld.GuideModeBlock.allowed_hosts.hint':
      'Hosts on which the guide appears and to which it leads; *.openeduhub.net covers all '
      + 'subdomains, not openeduhub.net itself. The chat replaces card links to other hosts '
      + 'with the link into the repository.',
    'feld.GuideModeBlock.trusted_domains.label': 'Trusted domains',
    'feld.GuideModeBlock.trusted_domains.hint':
      'Links to these domains carry the session along — the conversation continues on the '
      + 'target page — and the widget shows no “external URL” warning there. Where guide '
      + 'buttons lead is set by the allowed hosts. The environment variable '
      + 'GUIDE_TRUSTED_DOMAINS replaces the list when set.',

    // ── Guide rules (02-domain/guide-rules) ─────────────────────────
    'feld.GuideRulesArea.message_rules.label': 'Message rules',
    'feld.GuideRulesArea.message_rules.hint':
      'If a user message matches a rule, the guide offers a “Take me there” button to the '
      + 'stored page; empty = built-in rules. Changes take effect immediately.',
    'feld.GuideRulesArea.rag_area_rules.label': 'Rules per knowledge area',
    'feld.GuideRulesArea.rag_area_rules.hint':
      'Intended: a button to the website of a knowledge area when the answer names it (key = '
      + 'area name). Currently not evaluated: the chat uses a fixed built-in list.',
    'feld.MessageRule.pattern.label': 'Search expression',
    'feld.MessageRule.pattern.hint':
      'Regular expression searched for in the user message, case-insensitive; empty = the rule '
      + 'is dropped. An invalid expression is refused on save.',
    'feld.MessageRule.label.label': 'Label',
    'feld.MessageRule.label.hint':
      'Text on the button, such as “Themenseite Klimawandel”; empty = the rule is dropped.',
    'feld.MessageRule.label_en.label': 'English label',
    'feld.MessageRule.label_en.hint':
      'Button text for the English interface. Empty: German label.',
    'feld.MessageRule.url.label': 'Target address',
    'feld.MessageRule.url.hint':
      'Page the button leads to (http becomes https); empty = the rule is dropped. The button '
      + 'only appears if the host of the page is listed under “Allowed hosts”, and a bare home '
      + 'page without a path ranks behind links from the answer.',
    'feld.MessageRule.priority.label': 'Priority',
    'feld.MessageRule.priority.hint':
      'If several rules match, the highest number wins, on a tie the one further up; only one '
      + 'rule counts per message. 50 without an entry; 0 also counts as 50.',
    'feld.RagAreaRule.label.label': 'Label',
    'feld.RagAreaRule.label.hint':
      'Intended: text on the button to the website of the knowledge area. Currently not '
      + 'evaluated: the chat uses fixed built-in labels.',
    'feld.RagAreaRule.url.label': 'Target address',
    'feld.RagAreaRule.url.hint':
      'Intended: website of the knowledge area that the button leads to. Currently not '
      + 'evaluated: the chat uses fixed built-in addresses.',
    'feld.RagAreaRule.brand_pattern.label': 'Name expression',
    'feld.RagAreaRule.brand_pattern.hint':
      'Intended: regular expression checking whether the answer names the area; only then '
      + 'would the button appear. Currently not evaluated: the chat uses fixed built-in '
      + 'expressions.',
  },
};
