// @vitest-environment jsdom
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { STUDIO_LOCALE_STORAGE_KEY } from '../i18n/studio-language.service';
import { AblaufBildComponent } from './ablauf-bild.component';

import { schrittFolge } from './ablauf-folge';
import { bildAus } from './ablauf-bild';

/**
 * AS-2b: das Ablaufbild — je Schritt ein Kasten untereinander, der reguläre Weg zum nächsten als
 * gerade Linie, Sprünge, Regeln und „bei Fehler“ als Bögen rechts daneben (je Bogen eine eigene
 * Spur, damit sie sich nicht überdecken). Ein unbekanntes Ziel hat keinen Bogen, sein Kasten ist
 * markiert.
 */
const ABLAUF = { schritte: [
  { id: 'frage', typ: 'modul', bei_fehler: 'ende' },
  { id: 'wohin', typ: 'verzweigung', weiter: [{ wenn_gewaehlt: 'a', dann: 'ende' }, { sonst: 'frage' }] },
  { id: 'mitte', typ: 'nachricht', weiter: 'gibtsnicht' },
  { id: 'ende', typ: 'ende' },
] };

describe('bildAus (AS-2b)', () => {
  const bild = bildAus(schrittFolge(ABLAUF));

  it('ein Kasten je Schritt, untereinander', () => {
    expect(bild.kaesten.map((k) => k.id)).toEqual(['frage', 'wohin', 'mitte', 'ende']);
    const ys = bild.kaesten.map((k) => k.y);
    expect([...ys].sort((a, b) => a - b)).toEqual(ys);
    expect(bild.kaesten[2].unbekannt).toBe(true);
    expect(bild.kaesten[0].unbekannt).toBe(false);
  });

  it('der Weg zum nächsten ist gerade, Sprünge sind Bögen auf eigenen Spuren', () => {
    const gerade = bild.linien.filter((l) => l.gerade);
    // frage → wohin (regulär)
    expect(gerade.map((l) => [l.von, l.nach])).toEqual([[0, 1]]);
    const boegen = bild.linien.filter((l) => !l.gerade);
    expect(boegen.map((l) => [l.von, l.nach, l.art])).toEqual([
      [0, 3, 'fehler'], [1, 3, 'regel'], [1, 0, 'regel']]);
    expect(new Set(boegen.map((l) => l.spur)).size).toBe(boegen.length);
    expect(boegen.find((l) => l.art === 'regel' && l.nach === 0)!.bedingung).toBe('sonst');
    const wahl = boegen.find((l) => l.art === 'regel' && l.nach === 3)!;
    expect([wahl.bedingung, wahl.beschriftung]).toEqual(['gewaehlt', 'a']);
  });

  it('die Fläche reicht für alle Spuren und Kästen', () => {
    expect(bild.breite).toBeGreaterThan(bild.kaesten[0].breite);
    expect(bild.hoehe).toBeGreaterThan(bild.kaesten[3].y);
    expect(bildAus([]).kaesten).toEqual([]);
  });
});

describe('AblaufBildComponent (AS-2b)', () => {
  it('zeichnet nur (für Screenreader steht die Schrittfolge da) und wählt per Klick einen Schritt', () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(AblaufBildComponent);
    fixture.componentRef.setInput('folge', schrittFolge(ABLAUF));
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const svg = el.querySelector('svg')!;
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(el.querySelectorAll('.ab-kasten').length).toBe(4);
    expect(el.querySelectorAll('.ab-bogen').length).toBe(3);
    expect(el.querySelectorAll('.ab-fehler').length).toBe(1);
    expect(el.querySelector('.ab-unbekannt')).not.toBeNull();
    const gewaehlt: number[] = [];
    fixture.componentInstance.waehlen.subscribe((nr) => gewaehlt.push(nr));
    (el.querySelectorAll('.ab-kasten')[3] as SVGGElement).dispatchEvent(new MouseEvent('click'));
    expect(gewaehlt).toEqual([3]);
  });
});

describe('Ablaufbild — Schnellantworten (AS-3a)', () => {
  it('je Wahl ein Bogen mit ihrem Label, der Freitext mit „Text“', () => {
    TestBed.resetTestingModule();
    sessionStorage.setItem(STUDIO_LOCALE_STORAGE_KEY, 'de');
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
    const fixture = TestBed.createComponent(AblaufBildComponent);
    fixture.componentRef.setInput('folge', schrittFolge({ schritte: [
      { id: 'f', typ: 'nachricht', optionen: [{ id: 'a', label: { de: 'Neu anlegen' }, ziel: 'e' }],
        freitext: { ziel: 'e', schreibt: 'w' } },
      { id: 'e', typ: 'ende' }] }));
    fixture.detectChanges();
    const texte = [...(fixture.nativeElement as HTMLElement).querySelectorAll('.ab-beschriftung')]
      .map((t) => t.textContent?.trim());
    expect(texte).toEqual(['Neu anlegen', 'Text']);
  });
});
