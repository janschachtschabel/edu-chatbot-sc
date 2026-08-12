/**
 * The safety-level picker (9-4c, spec §5.6 "Safety-Level-Picker off/regex/
 * standard/strict/paranoid").
 *
 * Two deliberate departures from ALT (SecurityLevelPicker.tsx):
 *
 *  - ALT rewrote the YAML source with a regex (`/^(\s*security_level\s*:\s*).*$/m`)
 *    to keep the other keys. Here the whole document travels through the
 *    section's editor, so the level is a normal field change and the other
 *    keys are never at risk in the first place.
 *  - ALT saved on click. This picker only emits: it sits inside the
 *    safety-config section, and two save models on one page — one instant, one
 *    behind a button — is how an editor loses track of what is written.
 *
 * The five levels are the documented ones. Which of them a document actually
 * DEFINES is another question: the safety service falls back to the legacy
 * escalation block for a level with no preset, so a level without one is
 * marked rather than silently offered as equal.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';

interface Level {
  readonly id: string;
  readonly label: string;
  readonly desc: string;
  /** `false` for a level this document defines no preset for. */
  readonly defined: boolean;
}

/**
 * The five documented levels, in ALT's order (SecurityLevelPicker.tsx:5-11).
 *
 * `label` is the preset key as this file writes it, NOT a translated word: a
 * custom preset carries its own key as its label, and translating the known
 * five would make the picker disagree with the document. Only the description
 * is prose, so only the description has a catalogue key — spelled out rather
 * than composed from the id, so an unknown level cannot print a key as text.
 */
const KNOWN: readonly { id: string; label: string; descKey: string }[] = [
  { id: 'off', label: 'Off', descKey: 'safetyLevel.desc.off' },
  { id: 'regex', label: 'Regex', descKey: 'safetyLevel.desc.regex' },
  { id: 'standard', label: 'Standard', descKey: 'safetyLevel.desc.standard' },
  { id: 'strict', label: 'Strict', descKey: 'safetyLevel.desc.strict' },
  { id: 'paranoid', label: 'Paranoid', descKey: 'safetyLevel.desc.paranoid' },
];

@Component({
  selector: 'studio-safety-level',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './safety-level.component.html',
  styleUrl: './safety-level.component.scss',
})
export class SafetyLevelComponent {
  /** Uebersetzer fuer Legende, Hinweis und die Beschreibungen der Stufen. */
  protected readonly t = inject(StudioLanguageService).t;

  /** The whole safety-config document. */
  readonly doc = input.required<Record<string, unknown>>();
  /** The whole document back, with `security_level` replaced. */
  readonly docChange = output<Record<string, unknown>>();

  private readonly presets = computed(() => {
    const raw = this.doc()['presets'];
    return raw && typeof raw === 'object' && !Array.isArray(raw)
      ? Object.keys(raw as Record<string, unknown>)
      : [];
  });

  /** `basic` was merged into `standard` — services/safety/service.py:56. */
  readonly current = computed(() => {
    const level = String(this.doc()['security_level'] ?? 'standard').toLowerCase();
    return level === 'basic' ? 'standard' : level;
  });

  readonly levels = computed<Level[]>(() => {
    const defined = new Set(this.presets());
    const known = KNOWN.map(({ id, label, descKey }) => ({
      id, label, desc: this.t(descKey), defined: defined.has(id),
    }));
    // A preset this document adds beyond the five: it is real, it works, and
    // hiding it would make the picker disagree with the file.
    const extra = [...defined, this.current()]
      .filter((id) => !KNOWN.some((k) => k.id === id))
      .filter((id, index, all) => all.indexOf(id) === index)
      .map((id) => ({
        id,
        label: id,
        desc: this.t('safetyLevel.desc.custom'),
        defined: defined.has(id),
      }));
    return [...known, ...extra];
  });

  readonly anyMissing = computed(() => this.levels().some((level) => !level.defined));

  select(id: string): void {
    if (id === this.current()) return;
    this.docChange.emit({ ...this.doc(), security_level: id });
  }
}
