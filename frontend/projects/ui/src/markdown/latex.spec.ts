import { describe, expect, it } from 'vitest';

import { stripLatex } from './latex';

describe('stripLatex', () => {
  it('converts fraction, root and inline-math LaTeX to readable unicode', () => {
    expect(stripLatex('\\frac{1}{2}')).toBe('½');
    expect(stripLatex('\\frac12')).toBe('½');
    expect(stripLatex('\\frac{3}{7}')).toContain('3⁄7');
    expect(stripLatex('\\sqrt{2}')).toBe('√2');
    expect(stripLatex('$x^2$')).toBe('x^2');
  });

  it('leaves plain text untouched', () => {
    expect(stripLatex('Bruchrechnung für die 5. Klasse')).toBe('Bruchrechnung für die 5. Klasse');
  });
});
