/**
 * Rendert die Stücke aus `splitRich` (C1-d4b2) — der einzige Ort im Studio, an
 * dem Auszeichnung mitten im Satz entsteht.
 *
 * Eine Komponente und kein `@for` je Aufrufstelle: es sind fünf Stellen im
 * Lauf-Detail und vier weitere in der Startseite (C1-d5), und die Zuordnung
 * Stück-Art → Element ist genau die Entscheidung, die an allen neun gleich sein
 * muss.
 *
 * Bewusst KEIN `innerHTML`: die Auszeichnung kommt als Daten herein, nicht als
 * Markup. Ein Katalog bleibt damit eine Textquelle.
 *
 * Die Vorlage steht hier inline und OHNE Zeilenumbrüche zwischen den Zweigen.
 * Das ist keine Formatierungslaune: Angular behält den Leerraum innerhalb der
 * `@`-Blöcke, und ein Umbruch je Zweig machte aus „harte Quote 83 %" ein
 * „harte Quote  83 % " — der erste Testlauf hat genau das ausgegeben. Der
 * Abstand gehört den Stücken selbst, die ihn aus dem Katalog mitbringen.
 */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import type { RichSegment } from '@boerdi/ui';

@Component({
  selector: 'studio-rich',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template:
    '@for (part of parts(); track $index) {@switch (part.kind) {'
    + "@case ('strong') {<strong>{{ part.text }}</strong>}"
    + "@case ('code') {<code>{{ part.text }}</code>}"
    + '@default {<ng-container>{{ part.text }}</ng-container>}}}',
  styles: ':host { display: contents; }',
})
export class RichTextComponent {
  /** Bereits übersetzt und zerlegt — die Sprache gehört der Aufrufstelle. */
  readonly parts = input.required<readonly RichSegment[]>();
}
