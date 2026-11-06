/**
 * Die drei Schritte der Ablage im persönlichen Bereich (Paket U3-3b, T6) an `POST /api/ui/ablage/*`:
 * `vorbereiten` (JSON: Ordnername und je Datei Titel, sha256, Größe, Art → Vorschau und Schlüssel),
 * `datei` (multipart, eine Datei zur Zeit, mit Fortschritt) und `abschluss` (JSON → `vorgang.json`).
 *
 * Über `xhr-senden.ts` wie das Dokument: Zugangsblock im Kopf, Fehler als `status` + `code` aus
 * `detail`. Kein Zug, keine KI; das Backend prüft Anmeldung, Schalter und offene Frage selbst.
 */
import type { AblageSchritt } from '@boerdi/ui-module';

import { transportFehler, xhrSenden } from './xhr-senden';

export interface AblageOptionen {
  /** `…/api` — die Basis des Chat-Clients. */
  readonly basis: string;
  readonly sessionId: string;
  readonly blockId: string;
  readonly schritt: AblageSchritt;
  readonly signal?: AbortSignal;
  /** Für Tests. */
  readonly xhrFabrik?: () => XMLHttpRequest;
}

/** Vorbereiten fragt das MCP nach Rechten und Namen; eine Datei geht hoch UND wird angelegt. */
const FRIST_MS = { vorbereiten: 60_000, datei: 180_000, abschluss: 60_000 } as const;

function rumpfFuer(o: AblageOptionen): FormData | Record<string, unknown> {
  const s = o.schritt;
  const kopf = { session_id: o.sessionId, block_id: o.blockId };
  if (s.schritt === 'vorbereiten') return { ...kopf, ordner: s.ordner, eintraege: s.eintraege };
  if (s.schritt === 'abschluss') return { ...kopf, batch_token: s.batchToken };
  const rumpf = new FormData();
  rumpf.append('session_id', o.sessionId);
  rumpf.append('block_id', o.blockId);
  rumpf.append('batch_token', s.batchToken);
  rumpf.append('index', String(s.index));
  rumpf.append('datei', s.datei, s.datei.name);
  return rumpf;
}

export async function ablageSenden(o: AblageOptionen): Promise<Record<string, unknown>> {
  const s = o.schritt;
  const antwort = await xhrSenden({
    url: `${o.basis}/ui/ablage/${s.schritt}`,
    rumpf: rumpfFuer(o),
    onFortschritt: s.schritt === 'datei' ? s.onFortschritt : undefined,
    signal: o.signal,
    fristMs: FRIST_MS[s.schritt],
    xhrFabrik: o.xhrFabrik,
  });
  if (!antwort || typeof antwort !== 'object' || Array.isArray(antwort)) throw transportFehler(200, 'fehler');
  return antwort as Record<string, unknown>;
}
