/**
 * The editor for a `raw` field — a value whose area model declares it free-form
 * (`dict[str, Any]`, `Any`) or as a multi-type union. 13 real fields land here,
 * among them `01-base/policy` -> `rules[].match`/`effect`, so this is not a
 * corner: without it those areas would be visible but not editable, which is
 * exactly the ALT gap the generic form exists to close.
 *
 * Its own component because it is the only field with *draft* state: the text
 * being typed is not yet a value, and half-typed JSON must not be pushed into
 * the document on every keystroke.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';

@Component({
  selector: 'studio-json-value',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <textarea
      [id]="fieldId()"
      class="sf-input sf-json"
      [rows]="rows()"
      spellcheck="false"
      [attr.aria-describedby]="describedBy()"
      [attr.aria-invalid]="error() ? 'true' : null"
      [value]="text()"
      (input)="onInput($event)"
      (change)="commit($event)"
    ></textarea>
    @if (error()) {
      <p class="sf-error" [id]="fieldId() + '-err'" aria-live="polite">{{ error() }}</p>
    }
  `,
  styleUrl: './schema-form.scss',
})
export class JsonValueComponent {
  readonly fieldId = input.required<string>();
  readonly value = input<unknown>();
  /** ids of the field's help text, if any — the error id is added here. */
  readonly describedByBase = input<string | null>(null);
  readonly valueChange = output<unknown>();
  /** `''` = parseable. The form blocks a save while any field reports an error. */
  readonly errorChange = output<string>();

  /** Non-null while the text differs from the committed value. */
  private readonly draft = signal<string | null>(null);
  readonly error = signal('');

  constructor() {
    // Any change to the value from OUTSIDE (a save, "Verwerfen", a reload)
    // makes the draft and its error stale. Without this, Verwerfen restores
    // the document but leaves the rejected text — and its error — standing.
    effect(() => {
      this.value();
      // untracked: reading draft/error to decide would make them dependencies,
      // and setting the error would then immediately re-run the effect that
      // clears it — the message would never reach the screen.
      untracked(() => {
        if (this.draft() === null && !this.error()) return;
        this.draft.set(null);
        this.clearError();
      });
    });
  }

  readonly text = computed(() => this.draft() ?? serialize(this.value()));
  readonly rows = computed(() => Math.min(20, Math.max(3, this.text().split('\n').length)));
  readonly describedBy = computed(() => {
    const ids = [this.describedByBase(), this.error() ? `${this.fieldId()}-err` : null];
    return ids.filter(Boolean).join(' ') || null;
  });

  onInput(event: Event): void {
    this.draft.set((event.target as HTMLTextAreaElement).value);
  }

  /**
   * `change`, not `input`: JSON is invalid for most of the time it is being
   * typed, so parsing per keystroke would mean a permanent error message and
   * no value ever reaching the document.
   */
  commit(event: Event): void {
    const text = (event.target as HTMLTextAreaElement).value;
    if (text.trim() === '') {
      this.draft.set(null);
      this.clearError();
      this.valueChange.emit(null);
      return;
    }
    try {
      const parsed: unknown = JSON.parse(text);
      this.draft.set(null);
      this.clearError();
      this.valueChange.emit(parsed);
    } catch (err) {
      // keep the draft: discarding what was typed would be worse than the error
      this.error.set(`Kein gültiges JSON: ${(err as Error).message}`);
      this.errorChange.emit(this.error());
    }
  }

  private clearError(): void {
    if (!this.error()) return;
    this.error.set('');
    this.errorChange.emit('');
  }
}

function serialize(value: unknown): string {
  if (value === undefined) return '';
  return JSON.stringify(value, null, 2) ?? '';
}
