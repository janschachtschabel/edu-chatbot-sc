/**
 * „Vorschau" — das echte `<boerdi-chat>` im Studio, gegen dieses Backend
 * (A6-Rest, 9-6 / §5.6 „Live-Widget-Preview", Verbesserung V8).
 *
 * Kein ALT-Gegenstück: dort gab es keine Möglichkeit, eine Änderung anders zu
 * prüfen als auf einer echten Host-Seite. Entsprechend ist hier nichts portiert,
 * sondern entschieden — und jede Entscheidung ist gemessen:
 *
 *  - **Das Element schwebt.** `:host { position: fixed; z-index: 999999 }`
 *    (`_widget-fab.scss:21`). Es wird deshalb NICHT in einen Rahmen gesperrt:
 *    ein Container mit eigenem Enthaltungsblock (`transform`/`contain`) würde
 *    `position: fixed` umdeuten und eine Anordnung zeigen, die es auf keiner
 *    echten Seite gibt. Die Vorschau sagt stattdessen, wo das Widget sitzt.
 *  - **`auto-context="false"`.** Mit dem Default sammelt das Widget Pfad, Titel,
 *    Query und DOM-Text der TRAGENDEN Seite ein (`widget-init.ts:65-92`) — im
 *    Studio also die Studio-Seite, und schickte sie als Besucher-Kontext ans
 *    Backend. Der Kontext kommt hier aus dem Formular (`preview-embed.ts`).
 *  - **`persist-session="false"`.** Der Default legt die Sitzungs-ID unter
 *    `boerdi_session_id` ab; jede Vorschau würde das Gespräch von gestern
 *    fortsetzen, statt den Konfigurations-Boot zu zeigen, um den es geht.
 *  - **`initial-state="expanded"`.** Zu prüfen ist die Begrüßung, und die steht
 *    im Panel.
 *  - **`api-url` = eigene Herkunft.** Dieselbe Herkunft liefert `/api` (in Prod
 *    dieselbe FastAPI-App, im Dev der Proxy). Der Client würde ohne Attribut auf
 *    `'/api'` zurückfallen (`chat-api.ts:120`) und dort landen — gesetzt wird es,
 *    weil die Seite dem Redakteur zeigen soll, mit welchem Backend sie spricht.
 *
 * `CUSTOM_ELEMENTS_SCHEMA` ist auf diese eine Komponente begrenzt und der
 * vorgesehene Weg, ein Custom Element in einem Angular-Template zu benutzen;
 * `strictTemplates` bleibt für alle anderen Templates das Gate aus 9-2.
 */
import {
  CUSTOM_ELEMENTS_SCHEMA, ChangeDetectionStrategy, Component, computed, inject, signal,
} from '@angular/core';

import { WidgetElementLoader } from '../core/widget-element-loader';
import { PREVIEW_CONTEXT_KINDS, buildPreviewContext } from './preview-embed';

type LoadState = 'laden' | 'bereit' | 'fehler';

@Component({
  selector: 'studio-widget-preview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  templateUrl: './widget-preview.component.html',
  styleUrl: './widget-preview.component.scss',
})
export class WidgetPreviewComponent {
  private readonly loader = inject(WidgetElementLoader);

  readonly kinds = PREVIEW_CONTEXT_KINDS;
  readonly kind = signal(PREVIEW_CONTEXT_KINDS[0].id);
  readonly value = signal('');
  readonly status = signal<LoadState>('laden');

  /** Zählt die Neustarts und ist der `track`-Schlüssel des Elements: ein neuer
   *  Wert wirft das alte Element weg und baut ein neues. Der Konfigurations-Boot
   *  (Begrüßung, Quick-Replies, Lotse) läuft nur beim Verbinden — ohne neues
   *  Element zeigte die Vorschau nach einer Änderung den alten Stand. */
  readonly boot = signal(1);

  /** Der abgeschickte Kontext als JSON, oder `null` = Attribut weglassen. */
  readonly applied = signal<string | null>(null);

  readonly apiUrl = window.location.origin;

  private readonly chosen = computed(() => this.kinds.find((k) => k.id === this.kind()));
  readonly field = computed(() => this.chosen()?.field ?? '');
  readonly fieldLabel = computed(() => this.chosen()?.fieldLabel ?? '');
  readonly example = computed(() => this.chosen()?.example ?? '');

  constructor() {
    void this.load();
  }

  async load(): Promise<void> {
    this.status.set('laden');
    try {
      await this.loader.load();
      this.status.set('bereit');
    } catch (err) {
      // Die technische Ursache (fehlender Chunk, gescheiterter Bootstrap) hilft
      // nur beim Debuggen, nicht dem Redakteur — Muster wie `main.ts`.
      console.error('[Studio] Widget-Vorschau konnte nicht geladen werden:', err);
      this.status.set('fehler');
    }
  }

  /** Nur der Typ wechselt — der eingegebene Wert bleibt stehen. Sammlung und
   *  Inhaltsseite meinen dieselbe UUID in anderer Bedeutung (`page_context.py`
   *  Z. 6-7); ein Wechsel zwischen beiden wäre sonst jedes Mal ein Neu-Einfügen,
   *  und was abgeschickt wird, steht sichtbar im Feld. */
  onKind(id: string): void {
    this.kind.set(id);
  }

  /** Kontext übernehmen und die Vorschau neu starten — ein Knopf, weil beides
   *  ohnehin nur zusammen wirkt. */
  apply(event: Event): void {
    event.preventDefault();
    const context = buildPreviewContext(this.kind(), this.value());
    this.applied.set(context && JSON.stringify(context));
    this.boot.update((n) => n + 1);
  }
}
