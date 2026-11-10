/**
 * AS-2c: Querverweise zwischen UI-Modul und Abläufen über die Adresse — `/ablaeufe?ablauf=<id>`
 * wählt einen Ablauf, `/ui-module?modul=<name>` ein Modul. Ohne Router (Tests einzelner Teile)
 * bleibt der Wunsch leer.
 */
import { inject, signal, type Signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { map } from 'rxjs';

function ausAdresse(name: string): Signal<string | null> {
  const route = inject(ActivatedRoute, { optional: true });
  if (!route) return signal(null).asReadonly();
  return toSignal(route.queryParamMap.pipe(map((p) => p.get(name))), { initialValue: null });
}

/** Die Kennung des Ablaufs aus `?ablauf=` — im Konstruktor (Injektionskontext) rufen. */
export const ablaufAusAdresse = (): Signal<string | null> => ausAdresse('ablauf');
/** Der Name des Moduls aus `?modul=` — im Konstruktor (Injektionskontext) rufen. */
export const modulAusAdresse = (): Signal<string | null> => ausAdresse('modul');
