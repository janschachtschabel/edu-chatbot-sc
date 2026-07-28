// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { applyPrimaryColor, isValidCssColor } from './primary-color';

describe('isValidCssColor', () => {
  it('accepts hex colors of every length', () => {
    for (const c of ['#fff', '#ffff', '#1f6feb', '#1f6febcc']) {
      expect(isValidCssColor(c)).toBe(true);
    }
  });

  it('accepts rgb/hsl function colors and named colors', () => {
    expect(isValidCssColor('rgb(31, 111, 235)')).toBe(true);
    expect(isValidCssColor('rgba(31,111,235,0.5)')).toBe(true);
    expect(isValidCssColor('hsl(212 84% 52%)')).toBe(true);
    expect(isValidCssColor('rebeccapurple')).toBe(true);
  });

  it('rejects style-injection payloads and junk', () => {
    expect(isValidCssColor('red; } body { display: none')).toBe(false);
    expect(isValidCssColor('url(https://evil.example/x)')).toBe(false);
    expect(isValidCssColor('#12')).toBe(false);
    expect(isValidCssColor('')).toBe(false);
  });
});

describe('applyPrimaryColor', () => {
  it('sets --boerdi-primary for a valid color', () => {
    const el = document.createElement('div');
    applyPrimaryColor(el, '#1f6feb');
    expect(el.style.getPropertyValue('--boerdi-primary')).toBe('#1f6feb');
  });

  it('clears the override for null, empty, or invalid input', () => {
    const el = document.createElement('div');
    el.style.setProperty('--boerdi-primary', '#1f6feb');
    applyPrimaryColor(el, null);
    expect(el.style.getPropertyValue('--boerdi-primary')).toBe('');

    el.style.setProperty('--boerdi-primary', '#1f6feb');
    applyPrimaryColor(el, 'red; } body { display: none');
    expect(el.style.getPropertyValue('--boerdi-primary')).toBe('');
  });

  it('does not throw when the host has no style object', () => {
    expect(() => applyPrimaryColor(null as unknown as HTMLElement, '#fff')).not.toThrow();
  });
});
