// @vitest-environment jsdom
import type { SafeHtml } from '@angular/platform-browser';
import { describe, expect, it } from 'vitest';

import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { formelnHerausnehmen, texZuMathml } from './formel';
import { MarkdownRenderer, type MarkdownRenderContext } from './markdown-renderer';

/**
 * Plan 2026-11-10, TB-E4 (Nutzer-Entscheid N5): Formeln im Widget direkt darstellen. LaTeX in
 * `\( … \)`, `\[ … \]`, `$$ … $$` und `$ … $` wird MathML — eine kleine eigene Umwandlung der
 * häufigen Formen, keine Bibliothek und keine Netzquelle (die fertigen sprengen das Bündel). Der
 * Browser zeichnet MathML selbst. Eingesetzt wird es nach DOMPurify, im DOM (`formelnEinsetzen`).
 */

function ctx(): MarkdownRenderContext {
  return {
    bypassSecurityTrustHtml: (h: string) => h as unknown as SafeHtml,
    sessionId: () => 'bb-1', t: createTranslator(DE, DE),
    isHostTrusted: () => false, withBsid: (u) => u ?? '',
  };
}

const render = (md: string): string => new MarkdownRenderer(ctx()).render(md) as unknown as string;

describe('Formeln herausnehmen (TB-E4)', () => {
  it('findet die vier Schreibweisen, inline und abgesetzt', () => {
    const { text, formeln } = formelnHerausnehmen(
      'a \\(x^2\\) b \\[\\frac{a}{b}\\] c $$y$$ d $z_1$ e', 'n0nce');
    expect(formeln.map((f) => [f.tex, f.abgesetzt])).toEqual([
      ['x^2', false], ['\\frac{a}{b}', true], ['y', true], ['z_1', false]]);
    expect(formeln[0].quelle).toBe('\\(x^2\\)');
    expect(text).not.toContain('\\(');
    // Review TB-E4: der Platzhalter trägt den Zufallswert des Renders
    expect(text).toContain('@@FORMEL-n0nce-0@@');
  });

  it('lässt Geldbeträge und Code in Ruhe', () => {
    expect(formelnHerausnehmen('Das kostet $5 und $10.').formeln).toEqual([]);
    expect(formelnHerausnehmen('`$x$` und\n```\n\\(y\\)\n```').formeln).toEqual([]);
  });
});

describe('LaTeX → MathML (TB-E4)', () => {
  it('Potenz, Index, Bruch, Wurzel', () => {
    expect(texZuMathml('x^2', false)).toBe(
      '<math><msup><mi>x</mi><mn>2</mn></msup></math>');
    expect(texZuMathml('a_{n+1}', false)).toBe(
      '<math><msub><mi>a</mi><mrow><mi>n</mi><mo>+</mo><mn>1</mn></mrow></msub></math>');
    expect(texZuMathml('\\frac{1}{2}', true)).toBe(
      '<math display="block"><mfrac><mn>1</mn><mn>2</mn></mfrac></math>');
    expect(texZuMathml('\\sqrt{2}', false)).toBe('<math><msqrt><mn>2</mn></msqrt></math>');
    expect(texZuMathml('\\sqrt[3]{8}', false)).toBe(
      '<math><mroot><mn>8</mn><mn>3</mn></mroot></math>');
  });

  it('Zeichen, griechische Buchstaben und Text', () => {
    expect(texZuMathml('\\alpha \\cdot \\pi \\leq 3,14', false)).toBe(
      '<math><mi>α</mi><mo>·</mo><mi>π</mi><mo>≤</mo><mn>3,14</mn></math>');
    expect(texZuMathml('v = \\frac{s}{t}\\,\\text{in m/s}', false)).toContain(
      '<mtext>in m/s</mtext>');
    expect(texZuMathml('x^2 + y^2 = r^2', false)).toContain('<mo>=</mo>');
  });

  it('Unbekanntes bleibt lesbar, nichts wird zu Markup', () => {
    expect(texZuMathml('\\unbekannt{x}', false)).toContain('<mtext>\\unbekannt</mtext>');
    const gefaehrlich = texZuMathml('<img src=x onerror=alert(1)>', false);
    expect(gefaehrlich).not.toContain('<img');
    expect(gefaehrlich).toContain('&lt;');
  });

  it('kaputte Klammern brechen nichts', () => {
    expect(() => texZuMathml('\\frac{a}{', false)).not.toThrow();
    expect(() => texZuMathml('x^', false)).not.toThrow();
    expect(() => texZuMathml('}}}{{{', false)).not.toThrow();
  });
});

describe('MarkdownRenderer mit Formeln (TB-E4)', () => {
  it('zeigt MathML statt roher Zeichen und nach DOMPurify', () => {
    const html = render('Der Satz des Pythagoras: \\(a^2 + b^2 = c^2\\).');
    expect(html).toContain('<math');
    expect(html).toContain('<msup>');
    expect(html).not.toContain('\\(');
    expect(html).not.toContain('@@FORMEL');
  });

  it('eine abgesetzte Formel ist ein Block', () => {
    expect(render('\\[\\frac{1}{2}\\]')).toContain('display="block"');
  });

  it('auch im Fett-Text und in Listen', () => {
    expect(render('- **Fläche:** \\(A = \\pi r^2\\)')).toContain('<mi>π</mi>');
  });

  it('das Muster vom 10.11.: Brüche, \\cdot und Zähler mit Summe', () => {
    // vorher: „(⅔\cdot³⁄₅)“ und „(\frac{1+2}{4}=¾)“ — stripLatex lief vor dem Erkennen der Formel
    const html = render('4. **Berechne:** \\(\\frac{2}{3}\\cdot\\frac{3}{5}\\)\n\n'
      + '2. **B** – Bei gleichem Nenner: \\(\\frac{1+2}{4}=\\frac{3}{4}\\).');
    expect(html).toContain('<mfrac><mn>2</mn><mn>3</mn></mfrac><mo>·</mo>');
    expect(html).toContain('<mfrac><mrow><mn>1</mn><mo>+</mo><mn>2</mn></mrow><mn>4</mn></mfrac>');
    expect(html).not.toContain('\\cdot');
    expect(html).not.toContain('\\frac');
  });

  it('ein Skript im LaTeX bleibt wirkungslos', () => {
    const html = render('\\(\\text{<script>alert(1)</script>}\\)');
    expect(html).not.toContain('<script');
  });
});

/** Review TB-E4 (CRITICAL 1–2): das Ergebnis als DOM — was ein Browser daraus machte. */
function dom(md: string): HTMLElement {
  const tpl = document.createElement('template');
  tpl.innerHTML = render(md);
  const div = document.createElement('div');
  div.append(tpl.content);
  return div;
}

describe('Formeln — Sicherheit an Attributen und Platzhaltern (Review TB-E4)', () => {
  it('ein getippter Platzhalter wird nie leer ersetzt — kein javascript:-Link', () => {
    const el = dom('[klick](@@FORMEL:9@@javascript:alert(document.domain)) und '
      + '<a href="java@@FORMEL:9@@script:alert(1)">b</a> und \\(x\\)');
    for (const a of Array.from(el.querySelectorAll('a'))) {
      expect((a.getAttribute('href') ?? '').toLowerCase()).not.toMatch(/^\s*javascript:/);
    }
  });

  it('eine Formel im Link-Titel bricht nicht aus dem Attribut aus', () => {
    const el = dom('[a](https://x.de "\\(\\vec{x}\\)<img src=x onerror=alert(1)>")');
    expect(el.querySelectorAll('img').length).toBe(0);
    expect(el.querySelectorAll('[onerror]').length).toBe(0);
    expect(el.querySelector('a')?.getAttribute('title') ?? '').not.toContain('<math');
  });

  it('eine Formel als Linkziel wird kein javascript:-Link und kein MathML im href', () => {
    const el = dom('[a](\\(javascript:alert(1)\\))');
    for (const a of Array.from(el.querySelectorAll('a'))) {
      const href = a.getAttribute('href') ?? '';
      expect(href.toLowerCase()).not.toMatch(/^\s*javascript:/);
      expect(href).not.toContain('<');
    }
  });

  it('Formeln in Code bleiben Quelltext — auch in ~~~, `` und eingerückt', () => {
    const el = dom('`` \\(x^2\\) ``\n\n~~~\n\\(y^2\\)\n~~~\n\n    \\(z^2\\)\n');
    expect(el.querySelectorAll('math').length).toBe(0);
    expect(el.textContent).toContain('\\(y^2\\)');
  });

  it('\\[1\\] aus maskierten Klammern ist keine Formel; Absätze trennen Formeln', () => {
    expect(formelnHerausnehmen('Quelle \\[1\\] und \\[Quelle\\]').formeln).toEqual([]);
    expect(formelnHerausnehmen('\\(a\n\nb\\)').formeln).toEqual([]);
    expect(formelnHerausnehmen('echo $PATH:$HOME').formeln).toEqual([]);
  });

  it('Geldbeträge behalten ihr Dollarzeichen', () => {
    expect(render('Das kostet $5 und $10.')).toContain('$5');
  });

  it('Zeichen außerhalb der BMP bleiben ganz', () => {
    expect(texZuMathml('𝑥+1', false)).toContain('<mi>𝑥</mi>');
  });

  it('\\left mit Leerzeichen und \\\\ als Zeilenumbruch', () => {
    expect(texZuMathml('\\left ( x \\right )', false)).toBe(
      '<math><mo>(</mo><mi>x</mi><mo>)</mo></math>');
    expect(texZuMathml('a \\\\ b', false)).not.toContain('\\\\');
  });
});

describe('Werte aus Ablauf-Platzhaltern (Querschnitts-Review Gruppe E)', () => {
  it('maskierte Klammern als Entitäten werden keine Formel', () => {
    const html = render('Thema: Brüche &#40;Klasse 6&#41; und &#91;a\\.b&#93;');
    expect(html).not.toContain('<math');
    const el = document.createElement('div');
    el.innerHTML = html;
    expect(el.textContent).toContain('Brüche (Klasse 6) und [a.b]');
  });
});
