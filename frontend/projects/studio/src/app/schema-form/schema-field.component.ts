/**
 * One field of a config document, rendered from its schema description and
 * recursing into groups, lists and maps (9-3d).
 *
 * It never owns the value. Every change leaves as a `FormEdit` carrying the
 * absolute path, and `SchemaFormComponent` applies it to the document — so the
 * parts of the document no field describes (357 unpinned paths in the ALT
 * config) are never rebuilt and therefore never lost.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  forwardRef,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';

import { pathKey } from '../core/field-problems';
import { StudioLanguageService } from '../i18n/studio-language.service';
import { safeIdPart } from './field-ids';
import type { ValuePath } from './form-value';
import { AblaufPruefenComponent } from './ablauf-pruefen.component';
import { FieldControlComponent } from './field-control.component';
import { FORM_WIRKUNG } from './form-wirkung';
import { gesetzt } from './field-hints';
import { JsonValueComponent } from './json-value.component';
import { ListItems } from './list-items';
import { MapEntries } from './map-entries';
import { ObjectListComponent } from './object-list.component';
import type { SchemaField } from './schema-to-fields';

/** A change to the document itself. */
export type DocumentEdit =
  | { readonly kind: 'set'; readonly path: ValuePath; readonly value: unknown }
  | { readonly kind: 'remove'; readonly path: ValuePath }
  | { readonly kind: 'rename'; readonly path: ValuePath; readonly from: string; readonly to: string }
  /** Several changes applied to ONE document and reported once (ST-2i). Two
   *  edits emitted in the same tick would each start from the same stale
   *  input, and the second would silently undo the first. */
  | { readonly kind: 'batch'; readonly edits: readonly DocumentEdit[] };

export type FormEdit =
  | DocumentEdit
  /** Not a document change: a field reporting that its input cannot be parsed,
   *  so the form can stop a save that would silently drop it. `''` clears. */
  | {
    readonly kind: 'field-error'; readonly path: ValuePath; readonly message: string;
    /** Paket K2c-2 (Re-Review, Befund 2): mit `''` auch die Meldungen unter diesem Pfad — ein
     *  ausgeblendetes Feld nimmt die seiner JSON-Boxen mit. */
    readonly mitUnterpfaden?: boolean;
  };

const NO_PROBLEMS: ReadonlyMap<string, string> = new Map();

@Component({
  selector: 'studio-schema-field',
  // forwardRef: the template recurses into this very component, and a bare
  // self-reference would read the binding before the class exists. The object
  // list (ST-3) renders its editor with this component in turn — same reason.
  imports: [
    FieldControlComponent, JsonValueComponent, AblaufPruefenComponent,
    forwardRef(() => SchemaFieldComponent), forwardRef(() => ObjectListComponent),
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './schema-field.component.html',
  styleUrl: './schema-form.scss',
})
export class SchemaFieldComponent {
  private readonly lang = inject(StudioLanguageService);
  protected readonly t = this.lang.t;

  readonly field = input.required<SchemaField>();
  readonly path = input.required<ValuePath>();
  readonly value = input<unknown>();
  /** Prefix that makes `<label for>` ids unique when two forms share a page. */
  readonly idPrefix = input('sf');
  /** Overrides `field.label` — a list entry is "quick_replies 2", a map entry
   * carries its own key as the heading. */
  readonly labelOverride = input<string | null>(null);
  /** The server's messages by absolute path (ST-2e); each field takes its own. */
  readonly problems = input<ReadonlyMap<string, string>>(NO_PROBLEMS);
  /** `list` with a marker (ST-2i): the value of the sibling that marks a row. */
  readonly markerValue = input<unknown>(undefined);
  /** Paket 15 (Review-Runde 2): ein Vorfahr fehlt im Dokument — dieser Wert stammt aus seiner
   *  Vorgabe, gespeichert ist er nicht. */
  readonly geerbt = input(false);
  /** Paket K2c-2: die Kennung eines Hinweises der Elterngruppe („wirkt bei diesem typ nicht“) —
   *  kommt mit ins `aria-describedby`, damit ein Screenreader ihn am Feld vorliest. */
  readonly zusatzId = input<string | null>(null);
  /** Oberste Gruppe eines Formular-Abschnitts: der Abschnitt ist ihr Rahmen, sie bekommt
   *  Abstand rundum statt Einzug und Strich. Als Eingabe, weil eine Regel über beide
   *  Komponenten an der Kapselung scheiterte (Studio-Rundgang 2026-10-18). */
  readonly oben = input(false);

  readonly edit = output<FormEdit>();

  /** Rundgang 3: wirkt dieses Feld im offenen Arbeitsbereich nicht, sagt es eine Plakette. */
  private readonly wirkung = inject(FORM_WIRKUNG, { optional: true });
  readonly wirkungsPlakette = computed(() => this.wirkung?.(this.path().join('.')) ?? null);

  /**
   * Paket 15 (A3): fehlt der Schlüssel im Dokument, zeigt das Feld die Schema-Vorgabe — den
   * Wert, den der Server nimmt — statt eines leeren oder ausgeschalteten Felds.
   */
  readonly ausVorgabe = computed(
    () => this.value() === undefined && this.field().defaultValue !== undefined);
  /** Der angezeigte Wert: der gespeicherte, sonst die Vorgabe. */
  readonly wert = computed(() => (this.ausVorgabe() ? this.field().defaultValue : this.value()));
  /** Nicht im Dokument: die eigene Vorgabe oder die eines fehlenden Vorfahren. */
  readonly nichtGespeichert = computed(() => this.ausVorgabe() || this.geerbt());
  /** Eine Vorgabe, die etwas sagt — eine leere (`''`, `[]`, `{}`, `null`) ist keine Auskunft;
   *  Plakette und Knopf stünden sonst unter jedem ausgefüllten Feld (Browser-Abnahme P15). */
  readonly sprechendeVorgabe = computed(() => !leer(this.field().defaultValue));
  readonly vorgabePlakette = computed(() => this.nichtGespeichert() && !leer(this.wert()));
  /** „Auf Vorgabe zurück“: ein gespeicherter Einzelwert weicht von einer sprechenden Vorgabe
   *  ab. Nicht bei Schaltern — da ist der Schalter selbst der Weg zurück. */
  readonly abweichend = computed(() => {
    const vorgabe = this.field().defaultValue;
    return this.sprechendeVorgabe() && this.field().kind !== 'boolean' && !this.geerbt()
      && this.value() !== undefined && JSON.stringify(this.value()) !== JSON.stringify(vorgabe);
  });

  /** Was Liste und Map lesen und schreiben — der angezeigte Wert, Änderungen über `weiter`. */
  private readonly host = {
    field: this.field, path: this.path, value: this.wert, markerValue: this.markerValue,
    groupLabel: () => this.groupLabel(), edit: { emit: (e: FormEdit) => this.weiter(e) },
  };
  /** Bearbeitung einer Liste — Chips, hervorgehobener Eintrag (`list-items.ts`). */
  readonly list = new ListItems(this.host, this.lang);
  /** Bearbeitung einer Map — Schlüssel anlegen, umbenennen (`map-entries.ts`). */
  readonly map = new MapEntries(this.host, this.lang);

  /** Beschriftung aus dem Katalog (ST-1), `null` ohne Eintrag. */
  private readonly catalogueLabel = computed(() => this.catalogueText('label'));
  readonly label = computed(
    () => this.labelOverride() ?? this.catalogueLabel() ?? this.field().label,
  );
  /**
   * Der Rohschlüssel, klein hinter einer Katalog-Beschriftung: so benennen
   * Formular und YAML-Reiter weiter dasselbe Ding. Ohne Katalogtext IST die
   * Beschriftung schon der Schlüssel, und ein Listeneintrag („Regeln 2") hat
   * keinen eigenen.
   */
  readonly rawKey = computed(() =>
    this.labelOverride() === null && this.catalogueLabel() !== null ? this.field().key : null,
  );
  /** Hilfetext: der Katalog vor dem `description` des Schemas. */
  readonly hint = computed(() => this.catalogueText('hint') ?? this.field().description ?? null);
  /**
   * A list or map always needs a name — for its legend and for its buttons'
   * accessible names. The ROOT of a map area (`05-knowledge/rag-config`) has
   * no key, which produced an empty legend and "Eintrag zu  hinzufügen".
   * A group keeps the empty label: its legend is simply omitted.
   */
  readonly groupLabel = computed(
    () => this.label() || this.lang.t('schemaField.fallbackGroup'),
  );
  readonly fieldId = computed(() => {
    const suffix = this.path().map(safeIdPart).join('.');
    return suffix ? `${this.idPrefix()}-${suffix}` : this.idPrefix();
  });
  readonly descId = computed(() => (this.hint() ? `${this.fieldId()}-desc` : null));
  /** Die Prüfmeldung des Servers zu GENAU diesem Feld (ST-2e), sonst `null`. */
  readonly problem = computed(() => this.problems().get(pathKey(this.path())) ?? null);
  readonly errId = computed(() => (this.problem() ? `${this.fieldId()}-err` : null));
  /** Paket 15 (Review-Runde 2): die Meldung zum ausgeblendeten Ziel des Markers — sie steht
   *  an der Liste, die es bedient, sonst an keinem Feld. */
  readonly markerProblem = computed(() => {
    const marker = this.field().marker;
    return marker
      ? this.problems().get(pathKey([...this.path().slice(0, -1), marker])) ?? null
      : null;
  });

  /** Die Meldung zu einem Wert der Map-Tabelle (dort gibt es kein Kindfeld, das sie zeigt). */
  eintragsProblem(key: string): string | null {
    return this.problems().get(pathKey(this.childPath(key))) ?? null;
  }

  /** Hilfetext und Meldung zusammen — `aria-describedby` nimmt mehrere Kennungen. */
  readonly describedWith = computed(
    () => [this.zusatzId(), this.descId(), this.errId()].filter(Boolean).join(' ') || null,
  );

  /**
   * The stored value cannot hold what this field renders — an array where the
   * schema says object, a scalar where it says list. Showing an empty group
   * would be a lie AND every edit into it would be discarded, so the value is
   * handed to the JSON editor instead, where it can be seen and repaired.
   */
  readonly shapeMismatch = computed(() => {
    const value = this.wert();
    if (value === undefined || value === null) return false;
    switch (this.field().kind) {
      case 'list':
        return !Array.isArray(value);
      case 'group':
      case 'map':
        return typeof value !== 'object' || Array.isArray(value);
      default:
        return false;
    }
  });

  // Die Formnamen tragen ihren Artikel, weil der Satz sie so einsetzt („ist
  // eine Liste") — und welcher Artikel das ist, entscheidet die Sprache.
  readonly expectedShape = computed(() => this.lang.t(
    this.field().kind === 'list' ? 'schemaField.shape.list' : 'schemaField.shape.object',
  ));
  readonly actualShape = computed(() => {
    const value = this.wert();
    if (Array.isArray(value)) return this.lang.t('schemaField.shape.list');
    return typeof value === 'object'
      ? this.lang.t('schemaField.shape.object')
      : this.lang.t('schemaField.shape.scalar', { type: typeof value });
  });

  /** Paket 4c, B2: nicht gesetzt — es gilt die Vorgabe, nicht „keine“. */
  readonly unset = computed(() => this.field().vorgabe === true && this.value() == null);

  private catalogueText(part: 'label' | 'hint'): string | null {
    const key = this.field().textKey;
    return key && this.lang.has(`${key}.${part}`) ? this.lang.t(`${key}.${part}`) : null;
  }

  childPath(key: string | number): ValuePath {
    return [...this.path(), key];
  }

  /** Paket K2c-2: Felder, die schon `rest` waren, und der Wert des Nachbarfelds dabei. Review K2c-2,
   *  Befund 1: wer einen Restwert leert, tippt gerade darin — das Feld bleibt stehen, bis sich das
   *  Nachbarfeld ändert oder „Wert entfernen“ es ausdrücklich nimmt. */
  private readonly restBei = new Map<string, string>();
  /** Re-Review K2c-2, Befund 1: eine Instanz zeigt nacheinander mehrere Schritte (Liste mit
   *  Auswahl) — der klebende Zustand gilt nur für den Pfad, für den er entstand. */
  private restPfad = '';
  /** „Wert entfernen“ zeichnet neu, auch wenn das Dokument gleich bleibt (Schlüssel fehlte schon). */
  private readonly restNeu = signal(0);
  /** Der letzte Stand je Kind — um ein Ausblenden (→ `aus`) zu bemerken. */
  private vorher: Record<string, 'ja' | 'rest' | 'aus'> = {};
  private vorherPfad = '';

  /** Paket K2c-2: wirkt jedes Kind beim aktuellen Wert seines Nachbarfelds? `ja` (oder ohne
   *  Auszeichnung, oder das Nachbarfeld ist noch leer), `rest` — wirkt nicht, trägt aber einen
   *  Wert, eine Meldung oder war eben noch `rest` (sichtbar mit Hinweis), `aus` — wirkt nicht und
   *  ist leer (ausgeblendet). Einmal je Änderung für alle Kinder (Review K2c-2, Befund 8). */
  private readonly giltJe = computed(() => {
    this.restNeu();
    const kinder = this.field().children ?? [];
    if (!kinder.some((c) => c.nurBei)) return {};          // Re-Review, Befund 6
    const pfad = pathKey(this.path());
    if (pfad !== this.restPfad) {
      this.restBei.clear();
      this.restPfad = pfad;
    }
    const probleme = [...this.problems().keys()];
    const aus: Record<string, 'ja' | 'rest' | 'aus'> = {};
    for (const child of kinder) aus[child.key] = this.bewerte(child, probleme);
    return aus;
  });

  /** Re-Review K2c-2, Befund 2: blendet der Typ ein Feld aus, gehen die Meldungen seiner JSON-Boxen
   *  mit — sonst sperrten sie das Speichern unsichtbar. Nur hier, nicht beim Abbau einer Box: ein
   *  Reiterwechsel muss die Sperre behalten (A7, `feld-reiter.ts`). */
  private readonly ausgeblendetMelden = effect(() => {
    const jetzt = this.giltJe();
    const pfad = pathKey(this.path());
    untracked(() => {
      // Zeigt die Instanz einen anderen Schritt, ist der alte Stand kein Vorher.
      if (pfad !== this.vorherPfad) {
        this.vorher = {};
        this.vorherPfad = pfad;
      }
      for (const [key, stand] of Object.entries(jetzt)) {
        if (stand === 'aus' && this.vorher[key] && this.vorher[key] !== 'aus') {
          this.edit.emit({ kind: 'field-error', path: this.childPath(key), message: '',
                           mitUnterpfaden: true });
        }
      }
      this.vorher = jetzt;
    });
  });

  gilt(child: SchemaField): 'ja' | 'rest' | 'aus' {
    return this.giltJe()[child.key] ?? 'ja';
  }

  private bewerte(child: SchemaField, probleme: readonly string[]): 'ja' | 'rest' | 'aus' {
    const marke = child.nurBei;
    if (!marke) return 'ja';
    const nachbar = this.childValue(marke.feld);
    if (!gesetzt(nachbar) || marke.werte.includes(String(nachbar))) {
      this.restBei.delete(pathKey(this.childPath(child.key)));
      return 'ja';
    }
    const pfad = pathKey(this.childPath(child.key));
    // Review K2c-2, Befund 2: eine Meldung an einem ausgeblendeten Feld stünde nirgends.
    const meldung = probleme.some((k) => k === pfad || k.startsWith(`${pfad}.`));
    if (gesetzt(this.childValue(child.key)) || meldung
        || this.restBei.get(pfad) === String(nachbar)) {
      this.restBei.set(pfad, String(nachbar));
      return 'rest';
    }
    return 'aus';
  }

  /** Der Hinweis mit den Beschriftungen aus dem Katalog, nicht den Rohschlüsseln (Befund 6). */
  nurBeiText(child: SchemaField): string {
    const nachbar = (this.field().children ?? []).find((c) => c.key === child.nurBei?.feld);
    const schluessel = gesetzt(this.childValue(child.key)) ? 'schemaField.nurBei'
      : 'schemaField.nurBeiLeer';
    return this.t(schluessel, {
      feld: this.textOf(child) ?? child.key,
      nachbar: (nachbar && this.textOf(nachbar)) ?? child.nurBei?.feld ?? '',
    });
  }

  private textOf(f: SchemaField): string | null {
    return f.textKey && this.lang.has(`${f.textKey}.label`) ? this.lang.t(`${f.textKey}.label`) : null;
  }

  /** „Wert entfernen“ am Restwert (Befund 1/4): nimmt den Schlüssel heraus — auch eine Gruppe oder
   *  Map, die das Formular sonst nicht ganz leeren kann — und gibt den Fokus an das Nachbarfeld. */
  entfernen(child: SchemaField): void {
    this.restBei.delete(pathKey(this.childPath(child.key)));
    this.edit.emit({ kind: 'field-error', path: this.childPath(child.key), message: '',
                     mitUnterpfaden: true });
    this.weiter({ kind: 'remove', path: this.childPath(child.key) });
    this.restNeu.update((n) => n + 1);
    const ziel = child.nurBei ? `${this.idPrefix()}-${this.childPath(child.nurBei.feld)
      .map(safeIdPart).join('.')}` : null;
    if (ziel) setTimeout(() => document.getElementById(ziel)?.focus(), 0);
  }

  /** Kennung des Hinweises am Kind — aus dessen Pfad, also eindeutig je Eintrag einer Liste. */
  nurBeiId(child: SchemaField): string {
    return `${this.idPrefix()}-${this.childPath(child.key).map(safeIdPart).join('.')}-nur-bei`;
  }

  childValue(key: string): unknown {
    const value = this.wert();
    if (typeof value !== 'object' || value === null) return undefined;
    return (value as Record<string, unknown>)[key];
  }

  setValue(value: unknown): void {
    this.edit.emit({ kind: 'set', path: this.path(), value });
  }

  /**
   * Leitet eine Änderung von unterhalb weiter. Steht hier nur die Vorgabe, schreibt die erste
   * Änderung darunter sie zuerst ins Dokument: ein Eintrag mehr in einer Vorgabe-Liste
   * ergänzt sie, statt sie still durch diesen einen zu ersetzen. Gilt auch für einen Wert aus
   * der Vorgabe eines fehlenden Vorfahren (`geerbt`): ein Entfernen per Index träfe sonst ins
   * Leere (Review-Runde 2). Eine Gruppe, deren angezeigter Wert genau den Vorgaben ihrer Kinder
   * entspricht, bleibt draußen: die Lücken füllt der Server genauso, und die Geschwister folgen
   * künftigen Vorgabe-Änderungen weiter (Review Paket 15, #3).
   */
  weiter(edit: FormEdit): void {
    if (edit.kind === 'field-error' || !this.nichtGespeichert() || this.folgtKindern()) {
      this.edit.emit(edit);
      return;
    }
    const angezeigt: DocumentEdit = {
      kind: 'set', path: this.path(), value: structuredClone(this.wert()),
    };
    this.edit.emit({ kind: 'batch', edits: [angezeigt, edit] });
  }

  /** Über ALLE Kinder (`kinderVorgaben`), auch wenn ein Abschnitt nur einige zeigt. */
  private folgtKindern(): boolean {
    const { kind, kinderVorgaben } = this.field();
    const wert = this.wert();
    if (kind !== 'group' || !kinderVorgaben || typeof wert !== 'object' || wert === null) {
      return false;
    }
    return Object.entries(wert).every(([key, teil]) => key in kinderVorgaben
      && JSON.stringify(kinderVorgaben[key]) === JSON.stringify(teil));
  }

  /** Paket 15: entfernt den Schlüssel — fehlend nimmt der Server die Vorgabe. */
  zurueckZurVorgabe(): void {
    this.edit.emit({ kind: 'remove', path: this.path() });
  }

  /** `aria-disabled` statt `disabled`: der Knopf behält den Fokus, wirkt aber nur, wenn gesetzt.
   *  Entfernt den Schlüssel statt `null` zu schreiben — fehlend liest die Laufzeit als Vorgabe. */
  restoreDefault(): void {
    if (!this.unset()) this.zurueckZurVorgabe();
  }

  /** Paket 15: eine Map einfacher Werte (an/aus, Zahl, Text, Textfläche, Auswahl) — als
   *  Tabelle. */
  readonly einfacheMap = computed(() => ['boolean', 'text', 'multiline', 'select', 'number',
    'integer'].includes(this.field().item?.kind ?? ''));

  setzeEintrag(key: string, value: unknown): void {
    this.weiter({ kind: 'set', path: this.childPath(key), value });
  }

  /** Eine Liste oder Map von OBJEKTEN (ST-3): als Liste│Editor statt Wand. */
  readonly objectItems = computed(() => this.field().item?.kind === 'group');

  /** Wo die JSON-Box ihre Meldung setzte (Re-Review K2c-2, älterer Befund P1): eine Instanz kann
   *  danach einen anderen Eintrag zeigen — die Rücknahme gilt dem alten Pfad. */
  private jsonFehlerPfad: ValuePath | null = null;

  onJsonError(message: string): void {
    const path = message ? this.path() : (this.jsonFehlerPfad ?? this.path());
    this.jsonFehlerPfad = message ? this.path() : null;
    this.edit.emit({ kind: 'field-error', path, message });
  }
}

function leer(wert: unknown): boolean {
  return !gesetzt(wert);
}
