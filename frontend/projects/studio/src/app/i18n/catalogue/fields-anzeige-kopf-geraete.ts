/**
 * Feldtexte (ST-1) der Seite „Anzeige“, Abschnitte Kopfzeilen-Navigation
 * (`01-base/header-nav`) und Geräte (`01-base/device-config`). Die
 * Darstellungsregeln derselben Seite stehen in `fields-anzeige-regeln.ts`.
 *
 * Schlüsselschema wie in allen `fields-*.ts` (Kopf von `fields-layer-doc.ts`).
 * Die Knöpfe holt das Widget einmal beim Start über `GET /api/config/guide-mode`:
 * `config_loader/widget.py` wirft abgeschaltete, adresslose und doppelte heraus,
 * `ui/src/widget/guide-mode-config.ts` löst Symbol und Sitzungsanhang auf. Die
 * Geräte-Werte liest nur der Server: `pattern_engine.phase3_modulate` (Grenze im
 * Prompt der Muster-Engine, Anrede-Rückfall) und `services/agent_kopf.py`
 * (Anrede-Rückfall im Agent-Kopf, dort nur für die exakten Werte Sie/du/neutral).
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_ANZEIGE_KOPF_GERAETE: CataloguePart = {
  de: {
    // ── Kopfzeilen-Navigation ───────────────────────────────────────
    'feld.HeaderNavArea.header_nav.label': 'Kopfzeilen-Navigation',
    'feld.HeaderNavArea.header_nav.hint':
      'Knöpfe vorn in der Kopfzeile des Widgets, die aus dem Chat auf andere Seiten führen. '
      + 'Das Widget lädt sie beim Start; ohne Kopfzeile (rahmenlose Einbettung) fehlen sie.',
    'feld.HeaderNavBlock.buttons.label': 'Knöpfe',
    'feld.HeaderNavBlock.buttons.hint':
      'Die Knöpfe in der Reihenfolge der Liste. Zu sehen ist nur das Symbol, die Beschriftung '
      + 'erscheint als Tooltip.',
    'feld.NavButton.id.label': 'Kennung',
    'feld.NavButton.id.hint':
      'Eindeutiger Name des Knopfs, etwa home. Von zwei Knöpfen mit derselben Kennung '
      + 'erscheint nur der erste; ohne Beschriftung dient die Kennung als Tooltip.',
    'feld.NavButton.enabled.label': 'Aktiv',
    'feld.NavButton.enabled.hint':
      'Aus: Der Knopf bleibt gespeichert, erscheint aber nicht. Vorgabe: an.',
    'feld.NavButton.label.label': 'Beschriftung',
    'feld.NavButton.label.hint':
      'Deutscher Text zum Knopf, sichtbar als Tooltip und vorgelesen von Screenreadern. Leer: '
      + 'Es erscheint die Kennung.',
    'feld.NavButton.label_en.label': 'Englische Beschriftung',
    'feld.NavButton.label_en.hint':
      'Text für die englische Oberfläche. Leer: Das Widget zeigt dort die deutsche '
      + 'Beschriftung.',
    'feld.NavButton.icon.label': 'Symbol',
    'feld.NavButton.icon.hint':
      'Name eines Symbols aus dem Widget, etwa home, search oder menu_book. Unbekannte oder '
      + 'leere Namen zeigen explore; Vorgabe: explore.',
    'feld.NavButton.url.label': 'Zieladresse',
    'feld.NavButton.url.hint':
      'Seite, die der Knopf öffnet; ohne Adresse erscheint er nicht. Auf vertrauenswürdigen '
      + 'WLO-Seiten hängt das Widget die Sitzung an, damit der Chat dort weiterläuft, sofern '
      + 'es dort eingebettet ist.',
    'feld.NavButton.new_tab.label': 'Neuer Tab',
    'feld.NavButton.new_tab.hint':
      'An: Die Seite öffnet sich in einem neuen Tab, der Chat bleibt offen. Aus: Sie ersetzt '
      + 'die aktuelle Seite. Vorgabe: aus.',

    // ── Geräte ──────────────────────────────────────────────────────
    'feld.DeviceConfigArea.device_max_items.label': 'Ergebnisse je Gerät',
    'feld.DeviceConfigArea.device_max_items.hint':
      'Höchstzahl an Ergebnissen je Gerät (desktop, tablet, mobile; das Widget wählt nach '
      + 'Fensterbreite); ein fehlendes Gerät bekommt 6. Die Muster-Engine nennt sie dem Modell '
      + 'als Grenze, die Boxen im Widget begrenzt „Höchstzahl je Box“.',
    'feld.DeviceConfigArea.persona_formality.label': 'Anrede je Persona',
    'feld.DeviceConfigArea.persona_formality.hint':
      'Sie, du oder neutral je Persona-Kennung (etwa P-ELT), genau so geschrieben. Gilt in der '
      + 'Muster-Engine und der Agent-Schleife, wo die Persona die Anrede offenlässt (wie_user); '
      + 'ohne Eintrag bleibt die Muster-Engine neutral.',
  },
  en: {
    // ── Header navigation ───────────────────────────────────────────
    'feld.HeaderNavArea.header_nav.label': 'Header navigation',
    'feld.HeaderNavArea.header_nav.hint':
      'Buttons at the front of the widget header that lead from the chat to other pages. The '
      + 'widget loads them at start-up; without a header (frameless embedding) they are absent.',
    'feld.HeaderNavBlock.buttons.label': 'Buttons',
    'feld.HeaderNavBlock.buttons.hint':
      'The buttons in the order of the list. Only the icon is visible; the label appears as a '
      + 'tooltip.',
    'feld.NavButton.id.label': 'Identifier',
    'feld.NavButton.id.hint':
      'Unique name of the button, such as home. Of two buttons with the same identifier only '
      + 'the first appears; without a label the identifier serves as the tooltip.',
    'feld.NavButton.enabled.label': 'Active',
    'feld.NavButton.enabled.hint':
      'Off: the button stays saved but does not appear. Default: on.',
    'feld.NavButton.label.label': 'Label',
    'feld.NavButton.label.hint':
      'German text for the button, visible as a tooltip and read out by screen readers. Empty: '
      + 'the identifier appears.',
    'feld.NavButton.label_en.label': 'English label',
    'feld.NavButton.label_en.hint':
      'Text for the English interface. Empty: the widget shows the German label there.',
    'feld.NavButton.icon.label': 'Icon',
    'feld.NavButton.icon.hint':
      'Name of an icon from the widget, such as home, search or menu_book. Unknown or empty '
      + 'names show explore; default: explore.',
    'feld.NavButton.url.label': 'Target URL',
    'feld.NavButton.url.hint':
      'Page the button opens; without a URL it does not appear. On trusted WLO pages the '
      + 'widget appends the session so the chat continues there, provided it is embedded there.',
    'feld.NavButton.new_tab.label': 'New tab',
    'feld.NavButton.new_tab.hint':
      'On: the page opens in a new tab and the chat stays open. Off: it replaces the current '
      + 'page. Default: off.',

    // ── Devices ─────────────────────────────────────────────────────
    'feld.DeviceConfigArea.device_max_items.label': 'Results per device',
    'feld.DeviceConfigArea.device_max_items.hint':
      'Maximum results per device (desktop, tablet, mobile; the widget decides by window '
      + 'width); a missing device gets 6. The pattern engine gives it to the model as a limit; '
      + 'the widget boxes follow "Maximum per box".',
    'feld.DeviceConfigArea.persona_formality.label': 'Address form per persona',
    'feld.DeviceConfigArea.persona_formality.hint':
      'Formal Sie, informal du or neutral per persona ID (such as P-ELT), spelled exactly so. '
      + 'Applies in the pattern engine and agent loop where the persona leaves the form open '
      + '(wie_user); without an entry the pattern engine stays neutral.',
  },
};
