import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';

import { MODUL_REGISTER } from '../register.generated';
import { UI_MODUL_REGISTER } from './register';

describe('UI_MODUL_REGISTER', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('liefert ohne eigene Angabe das erzeugte Register', () => {
    expect(TestBed.inject(UI_MODUL_REGISTER)).toBe(MODUL_REGISTER);
  });

  it('jeder Eintrag trägt Name, Version und Komponente, der Name ist sein Schlüssel', () => {
    for (const [name, eintrag] of Object.entries(MODUL_REGISTER)) {
      expect(eintrag.manifest.name).toBe(name);
      expect(eintrag.manifest.version).toBeGreaterThanOrEqual(1);
      expect(typeof eintrag.komponente).toBe('function');
    }
  });
});
