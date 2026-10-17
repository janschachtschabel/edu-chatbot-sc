/**
 * Where the bot's facts come from, and where its configuration is kept
 * (A5-Rest, from ALT `InfoView.tsx:552-687`).
 *
 * Four ALT statements did not survive the check against NEU and are corrected
 * in the template rather than ported:
 *
 *  - "SQLite-Vec": NEU stores chunks in Postgres and searches them with pgvector
 *    cosine (`services/rag/retrieval.py` — a rewrite, not a port).
 *  - "10 Tools": no fixed count any more (Paket 6, S3 — it was wrong twice);
 *    the page points to the tool list on the Agent page. `query_knowledge` is
 *    callable but NOT an MCP tool — it is the RAG entry point declared in
 *    `services/response_tool_selection.py`.
 *  - the snapshot section described files on disk (`backend/snapshots/snap-*.zip`,
 *    the SQLite database inside the ZIP, a "Als Factory" promotion). NEU keeps
 *    snapshots as rows in `config_snapshots`, config-only, and has no promotion
 *    endpoint — see `snapshots-panel.component.ts`.
 *  - "Werkseinstellungen zurücksetzen … überschreibt die Datenbank": a restore
 *    writes config areas and nothing else.
 *
 * Confirmed unchanged: the resolver's TTLs (30 min resolved / 2 min failed,
 * `services/page_context.py:41-42`) and its two MCP calls.
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { StudioLanguageService } from '../i18n/studio-language.service';
import { RichTextComponent } from './rich-text.component';

@Component({
  selector: 'studio-reference-knowledge',
  imports: [RouterLink, RichTextComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reference-knowledge.component.html',
  styleUrl: './reference-knowledge.component.scss',
})
export class ReferenceKnowledgeComponent {
  private readonly lang = inject(StudioLanguageService);

  /** Die Prosa dieses Abschnitts (C1-d5b1) aus `i18n/catalogue/reference-knowledge.ts`. */
  protected readonly t = this.lang.t;

  /** Zwölf Sätze führen `<code>` oder `<strong>` mitten im Satz. */
  protected readonly rich = this.lang.rich;

}
