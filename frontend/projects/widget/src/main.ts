/**
 * Dev-harness entry for `ng serve widget` — importing the widget bootstrap
 * defines the `<boerdi-chat>` element, which index.html then renders. The
 * embeddable production bundle is built from `widget-main.ts` (build-widget
 * target), not this file.
 */
import './widget-main';
