/**
 * Das Bedienelement EINES Einzelwerts (ST-2a): Text, Auswahl, Textfläche,
 * Zahl, Wahrheitswert — oder, wenn das Schema keine passende Form kennt, der
 * JSON-Editor.
 *
 * Aus `SchemaFieldComponent` geschnitten, bevor die Bausteine aus ST-2 dazu
 * kommen (Plan 2026-09-26 §9.3): die behält Beschriftung, Hilfetext und die
 * Behälter (Gruppe, Liste, Map), hier steht, wie ein Wert BEDIENT wird. Ein
 * Wert verlässt das Element als `valueChange`, eine nicht lesbare JSON-Eingabe
 * als `errorChange` — den Pfad im Dokument setzt die Feld-Komponente dazu.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { ChoicesApi } from '../core/choices-api.service';
import { StudioFormat } from '../i18n/studio-format.service';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { JsonValueComponent } from './json-value.component';
import type { SchemaField } from './schema-to-fields';

/** Grobe Zeichen je Zeile bei 46rem Feldbreite und Schriftgrad 0.8125rem. */
const CHARS_PER_ROW = 70;
/** Auch leer eine Fläche, die zum Schreiben einlädt … */
const MIN_ROWS = 3;
/** … und nach oben ein Bildschirm, nicht mehr. */
const MAX_ROWS = 20;

@Component({
  selector: 'studio-field-control',
  imports: [JsonValueComponent, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './field-control.component.html',
  styleUrl: './schema-form.scss',
})
export class FieldControlComponent {
  private readonly lang = inject(StudioLanguageService);
  private readonly choices = inject(ChoicesApi);
  private readonly format = inject(StudioFormat);
  protected readonly t = this.lang.t;

  readonly field = input.required<SchemaField>();
  readonly value = input<unknown>();
  /** `id` des Elements — das `<label for>` der Feld-Komponente zeigt darauf. */
  readonly controlId = input.required<string>();
  /** `id` des Hilfetexts, `null` ohne einen. */
  readonly describedBy = input<string | null>(null);
  /** Präfix der Vorschlagslisten — dieselbe Kennung, die das Formular vergibt. */
  readonly idPrefix = input('sf');
  /** Der Server hat den Wert abgelehnt (ST-2e) — `aria-invalid`, roter Rand. */
  readonly invalid = input(false);

  readonly valueChange = output<unknown>();
  /** Eine JSON-Eingabe ist nicht lesbar; `''` hebt die Meldung auf. */
  readonly errorChange = output<string>();

  /** Typed views of `value` — a template cannot bind `unknown` to an input. */
  readonly asText = computed(() => {
    const value = this.value();
    if (typeof value === 'string') return value;
    return value === null || value === undefined ? '' : String(value);
  });
  readonly asNumber = computed(() => {
    const value = this.value();
    return typeof value === 'number' && Number.isFinite(value) ? String(value) : '';
  });
  readonly asBoolean = computed(() => this.value() === true);

  /**
   * Die Höhe einer Textfläche, aus dem Inhalt.
   *
   * Eine feste Höhe kann nur eines von beidem: ein leeres Feld nicht zur
   * halben Seite aufblasen, oder einen 700-Zeichen-Text zeigen. Die Zahl
   * wächst beim Tippen mit — ein Attribut, kein Elementwechsel, also ohne
   * Fokusverlust. Wer selbst zieht, gewinnt: die gezogene Höhe steht als
   * `style` und schlägt `rows`.
   */
  readonly rows = computed(() => {
    const geschaetzt = Math.ceil(this.asText().length / CHARS_PER_ROW);
    return Math.min(MAX_ROWS, Math.max(MIN_ROWS, geschaetzt));
  });

  /**
   * Die Optionen eines Auswahlfeldes: die leere zuerst, dann der Vorrat — und
   * ein gespeicherter Wert, den der Vorrat nicht kennt, als eigener Eintrag.
   *
   * Ohne diesen letzten Teil zeigte das Feld die erste Option an, obwohl etwas
   * anderes gespeichert ist, und der nächste Speichervorgang schriebe die
   * Anzeige fest. Ein Auswahlfeld darf einen Bestandswert nicht wegwerfen — es
   * darf ihn nur ausweisen.
   */
  readonly options = computed<readonly { value: string; label: string }[]>(() => {
    const vorrat = this.field().choices ?? [];
    const rows = [
      { value: '', label: this.lang.t('schemaField.noChoice') },
      ...vorrat.map((value) => ({ value, label: this.optionLabel(value) })),
    ];
    const current = this.asText();
    if (current && !vorrat.includes(current)) {
      rows.push({ value: current, label: this.lang.t('schemaField.foreignChoice', { current }) });
    }
    return rows;
  });

  /**
   * Klartext eines Auswahlwerts (ST-2d): „Muster-Maschine (pattern)". Der Wert
   * bleibt dahinter lesbar — so heißt er im YAML-Reiter und in der Doku. Ohne
   * Katalogtext der Wert allein.
   */
  private optionLabel(value: string): string {
    const prefix = this.field().choiceKey;
    const key = prefix ? `${prefix}.wahl.${value}` : null;
    return key && this.lang.has(key) ? `${this.lang.t(key)} (${value})` : value;
  }

  /**
   * Die `id` der Vorschlagsliste, oder `null` wenn das Feld keine hat. Aus dem
   * KATALOG-Namen gebildet, nicht aus dem Feld: die Liste selbst rendert das
   * Formular einmal je Katalog (`SchemaFormComponent`), sonst stünde derselbe
   * Vorrat einmal je Listeneintrag in der Seite.
   */
  readonly datalistId = computed(() => {
    const catalog = this.field().catalog;
    return catalog ? `${this.idPrefix()}-cat-${catalog}` : null;
  });

  /**
   * Der Sprung zum gewählten Element, als Routen-Segmente. `null`, solange der
   * Wert in keinem Katalog steht oder das Element keine eigene Seite hat
   * (Werkzeuge) — dann zeigt das Formular keinen Link statt eines toten.
   *
   * Segmente und nicht ein Stück: ein Bereichsschlüssel trägt einen
   * Schrägstrich (`03-patterns/m06-…`), und als EIN Segment übergeben landet er
   * `%2F`-kodiert in der Adresse. Ebenso in `areas.component.ts`.
   */
  readonly linkSegments = computed<readonly string[] | null>(() => {
    const area = this.choices.areaFor(this.field().catalog, this.asText());
    return area ? ['/bereich', ...area.split('/')] : null;
  });

  /**
   * Die Grenzen eines Zahlfelds als Satz (ST-2c), `null` ohne Grenze. Sichtbar
   * und per `aria-describedby` am Feld: `min`/`max` allein sieht niemand, und
   * der Browser meldet eine Verletzung nur beim Absenden eines `<form>`.
   */
  readonly range = computed(() => {
    const { minimum: min, maximum: max } = this.field();
    const zahl = (wert: number) => this.format.decimal(wert);
    if (min !== undefined && max !== undefined) {
      return this.t('schemaField.range', { min: zahl(min), max: zahl(max) });
    }
    if (min !== undefined) return this.t('schemaField.rangeMin', { min: zahl(min) });
    if (max !== undefined) return this.t('schemaField.rangeMax', { max: zahl(max) });
    return null;
  });
  readonly rangeId = computed(() => `${this.controlId()}-range`);

  // ── ST-2h: Schieberegler ──────────────────────────────────────────

  /** Die Knopfstellung — ein leerer Wert steht in der Mitte der Bahn. */
  readonly sliderValue = computed(() => {
    const value = this.value();
    return typeof value === 'number' ? value : 0;
  });

  /**
   * Was der Wert bewirkt, in Worten: „0,2 · Eine Stufe länger". Sichtbar UND
   * als `aria-valuetext` — ein Screenreader sagte sonst nur „0,2".
   */
  readonly sliderText = computed(() => {
    const value = this.value();
    if (typeof value !== 'number') return this.t('schemaField.sliderUnset');
    const zahl = this.format.decimal(value);
    const zone = this.zoneText(value);
    return zone ? `${zahl} · ${zone}` : zahl;
  });

  /** Unter der ersten Schwelle, über der letzten, sonst dazwischen — die
   *  Schwelle selbst zählt zur Mitte, wie in der Engine (`> 0.15`). */
  private zoneText(value: number): string | null {
    const { thresholds, textKey } = this.field();
    if (!thresholds?.length || !textKey) return null;
    const zone = value < thresholds[0] ? 'unter'
      : value > thresholds[thresholds.length - 1] ? 'ueber' : 'mitte';
    const key = `${textKey}.zone.${zone}`;
    return this.lang.has(key) ? this.t(key) : null;
  }
  /** Hilfetext und Grenzen zusammen — `aria-describedby` nimmt mehrere Kennungen. */
  readonly describedByAll = computed(() => {
    const ids = [this.describedBy(), this.range() ? this.rangeId() : null].filter(Boolean);
    return ids.length ? ids.join(' ') : null;
  });

  /** Text, Textfläche und Auswahlfeld — alle drei tragen ihren Wert in `value`. */
  onText(event: Event): void {
    const control = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
    this.valueChange.emit(control.value);
  }

  onNumber(event: Event): void {
    const input = event.target as HTMLInputElement;
    // An empty numeric field is not 0 — sending null keeps "I cleared this"
    // distinguishable, and the save surfaces a 422 naming the field if it was
    // required. Silently substituting 0 would write a value nobody chose.
    this.valueChange.emit(input.value === '' ? null : input.valueAsNumber);
  }

  onBoolean(event: Event): void {
    this.valueChange.emit((event.target as HTMLInputElement).checked);
  }
}
