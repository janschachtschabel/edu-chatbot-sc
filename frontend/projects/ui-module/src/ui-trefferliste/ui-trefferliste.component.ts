import {
  afterNextRender, ChangeDetectionStrategy, Component, computed, ElementRef, inject, Injector, input,
  linkedSignal,
} from '@angular/core';

import { type CardAction, CardListComponent } from '@boerdi/ui/cards/card-list.component';
import type { WloCard } from '@boerdi/ui/cards/card-types';
import type { ChatMessage, PaginationInfo, QueryMetaEntry } from '@boerdi/ui/grouping/message-types';
import type { ResultGroupsContext } from '@boerdi/ui/grouping/result-grouping';
import { ResultGroupsComponent } from '@boerdi/ui/grouping/result-groups.component';

import { type KartenAktion, MODUL_HOST } from '../_vertrag/modul-host';
import type { ModulKontext } from '../_vertrag/ui-block';

/** Eingabe laut manifest.json (`eingabe`) — die Felder wie in der Antwort (`cards`, …). */
export interface UiTrefferlisteDaten {
  readonly karten: readonly (Partial<WloCard> & { readonly node_id: string })[];
  readonly such_metas: readonly Partial<QueryMetaEntry>[];
  readonly seiten: Partial<PaginationInfo> | null;
  readonly typ_fokus: string;
}

/**
 * Die WLO-Treffer einer Antwort (Paket U1-c2a). Ein Adapter auf die bisherigen Trefferboxen
 * (`boerdi-result-groups`): aus den Daten des Blocks entsteht die Nachricht, die die Boxen
 * erwarten — gleiche Darstellung, gleiche Regeln (Gruppen-Grenzen, Typ-Fokus, Such-Absprung).
 * Link- und Such-Kontext, Darstellungsart und Aktionen kommen vom Host. Im Kachel-Modus (U1-c2b)
 * dieselbe Brücke zur Kachelliste (`boerdi-card-list`): „mehr anzeigen“ zählt das Modul selbst,
 * „mehr laden“, Sammlung öffnen, Lernpfad und Volltext gehen als Aktionen an den Host.
 */
@Component({
  selector: 'ui-trefferliste',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ResultGroupsComponent, CardListComponent],
  template: `
    @if (umgebung().kacheln) {
      <boerdi-card-list
        [message]="nachricht()"
        [ctx]="trefferKontext()"
        [isLoading]="umgebung().beschaeftigt"
        (browse)="karte('sammlung', $event)"
        (learningPath)="karte('lernpfad', $event)"
        (showContentText)="karte('volltext', $event)"
        (showMore)="mehrAnzeigen()"
        (loadMore)="mehrLaden()"
      />
    } @else {
      <boerdi-result-groups
        [message]="nachricht()"
        [ctx]="trefferKontext()"
        [isLoading]="umgebung().beschaeftigt"
        (showContentText)="karte('volltext', $event)"
      />
    }
  `,
})
export class UiTrefferliste {
  readonly daten = input.required<UiTrefferlisteDaten>();
  readonly kontext = input.required<ModulKontext>();

  private readonly host = inject(MODUL_HOST);
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);

  /** Sichtbare Kacheln: anfangs eine Seite (wie `addBotMessage`), „mehr anzeigen“ +5; kommen
   *  neue Karten dazu („mehr laden“), stehen alle sichtbar da — wie bisher `loadMore`. */
  private readonly sichtbar = linkedSignal<number, number>({
    source: () => this.daten().karten?.length ?? 0,
    computation: (anzahl, vorher) =>
      vorher && anzahl > vorher.source ? anzahl : (vorher?.value ?? (this.daten().seiten?.page_size || 5)),
  });

  protected readonly umgebung = computed(() => this.host.treffer());
  protected readonly trefferKontext = computed(() => this.umgebung().kontext as ResultGroupsContext);

  /** Die Nachricht, wie die Trefferboxen sie lesen — ohne Text und ohne Web-Links (die zeigt die
   *  Linkbox), mit Typ-Fokus und Anzeige-Regeln. */
  protected readonly nachricht = computed<ChatMessage>(() => {
    const d = this.daten();
    return {
      id: this.kontext().blockId,
      sender: 'bot',
      content: '',
      timestamp: new Date(0),
      cards: (d.karten ?? []) as WloCard[],
      visibleCardCount: this.sichtbar(),
      queryMetas: (d.such_metas ?? []) as QueryMetaEntry[],
      pagination: (d.seiten ?? undefined) as PaginationInfo | undefined,
      displayRules: (this.kontext().anzeigeRegeln ?? undefined) as ChatMessage['displayRules'],
      ui: { type_focus: d.typ_fokus || undefined },
    };
  });

  protected karte(name: KartenAktion, a: CardAction): void {
    this.host.aktion(name, { nodeId: a.nodeId, title: a.title });
  }

  /** Wie bisher `showMoreCards`: fünf mehr, dann zur ersten neu sichtbaren Kachel scrollen. */
  protected mehrAnzeigen(): void {
    const vorher = this.sichtbar();
    this.sichtbar.set(vorher + 5);
    afterNextRender(() => {
      const ziel = this.element.nativeElement.querySelectorAll('.wlo-card-wrapper')[vorher] as HTMLElement | undefined;
      // Weniger Bewegung gewünscht → springen statt gleiten (Review U1 gesamt).
      const ruhig = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
      ziel?.scrollIntoView?.({ behavior: ruhig ? 'auto' : 'smooth', block: 'center' });
    }, { injector: this.injector });
  }

  protected mehrLaden(): void {
    this.host.aktion('mehrLaden', { blockId: this.kontext().blockId });
  }
}
