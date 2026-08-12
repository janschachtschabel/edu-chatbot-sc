/**
 * Die Ansicht „Vorschau" (C1-d3b) — das echte Widget im Studio.
 *
 * Die vier Seitentyp-Namen und ihre Feld-Beschriftungen standen bis hierher als
 * fertige deutsche Zeichenketten in `views/preview-embed.ts`, also auf
 * Modulebene: Text, der in der Sprache einfriert, die beim Laden des Moduls
 * galt. `id` und `field` sind dort geblieben — das sind Daten, die ins Backend
 * gehen, keine Oberfläche.
 */
import type { CataloguePart } from './catalogue-part';

export const PREVIEW: CataloguePart = {
  de: {
    /** `{apiUrl}` ist die eigene Herkunft — ein Wert im Satz, kein Satzteil.
     *  Wie `login.passwordEnv`; kostet die `<code>`-Auszeichnung. */
    'preview.intro':
      'Das echte Chat-Widget mit dem aktuellen Stand der Konfiguration. Es spricht mit '
      + 'dem Backend dieser Studio-Instanz ({apiUrl}) und schwebt unten rechts über dieser '
      + 'Seite — genauso wie auf einer Host-Seite. Begrüßung, Quick-Replies und '
      + 'Lotsen-Einstellungen liest es einmal beim Öffnen: nach einer Änderung neu starten.',

    'preview.context.title': 'Seitenkontext',
    'preview.context.lead':
      'Auf einer echten Seite erkennt das Widget den Kontext selbst; hier wird er '
      + 'vorgegeben. Nur diese drei Seitentypen lösen die proaktive Begrüßung samt '
      + 'Kontext-Pills aus — ohne ID oder Slug bleibt sie aus, weil das Backend nichts '
      + 'aufzulösen hat.',
    'preview.kindLabel': 'Seitentyp',

    // Die Schlüssel tragen die Kennung des Seitentyps, weil `preview-embed.ts`
    // sie als Erlaubnisliste führt — nicht zusammengesetzt zur Laufzeit.
    'preview.kind.kein': 'Kein Seitenkontext',
    'preview.kind.topic': 'Themenseite',
    'preview.kind.collection': 'Sammlung',
    'preview.kind.content': 'Inhaltsseite',
    'preview.field.topic': 'Slug der Themenseite',
    'preview.field.collection': 'Sammlungs-ID (edu-sharing)',
    'preview.field.content': 'Node-ID des Materials',

    'preview.restart': 'Vorschau neu starten',
    'preview.state.loading': 'Das Widget wird geladen …',
    'preview.state.ready': 'Das Widget ist bereit und schwebt unten rechts über der Seite.',
    'preview.error':
      'Die Vorschau konnte nicht geladen werden. Beim zweiten Versuch klappt es meist; '
      + 'bleibt es dabei, fehlt dem Studio-Build das Widget-Bündel.',
  },

  en: {
    'preview.intro':
      'The real chat widget with the current configuration. It talks to the backend of '
      + 'this studio instance ({apiUrl}) and floats over the bottom right of this page — '
      + 'exactly as it does on a host page. Greeting, quick replies and guide settings are '
      + 'read once when it opens: restart it after a change.',

    'preview.context.title': 'Page context',
    'preview.context.lead':
      'On a real page the widget detects the context itself; here it is supplied. Only '
      + 'these three page types trigger the proactive greeting and its context pills — '
      + 'without an ID or slug it stays silent, because the backend has nothing to resolve.',
    'preview.kindLabel': 'Page type',

    'preview.kind.kein': 'No page context',
    'preview.kind.topic': 'Topic page',
    'preview.kind.collection': 'Collection',
    'preview.kind.content': 'Content page',
    'preview.field.topic': 'Topic page slug',
    'preview.field.collection': 'Collection ID (edu-sharing)',
    'preview.field.content': 'Node ID of the material',

    'preview.restart': 'Restart preview',
    'preview.state.loading': 'The widget is loading …',
    'preview.state.ready': 'The widget is ready and floats over the bottom right of the page.',
    'preview.error':
      'The preview could not be loaded. A second attempt usually works; if it keeps '
      + 'failing, the studio build is missing the widget bundle.',
  },
};
