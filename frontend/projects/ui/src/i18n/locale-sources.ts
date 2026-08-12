/**
 * Die unreinen Sprachquellen (C1-c) — Gegenstück zum reinen `locale.ts`.
 *
 * Hier steht ausschliesslich das **Lesen** aus DOM, `navigator` und Speicher;
 * entschieden wird nichts. Getrennt, weil `resolveLocale` seine Rangfolge nur
 * dann ohne gemockte Browser-Umgebung beweisen kann — und die Rangfolge ist
 * der Teil, der stimmen muss. Dieselbe Aufteilung wie `session/session-id.ts`:
 * Speicherzugriff im Modul, gegen echtes jsdom geprüft.
 *
 * Alle Leser geben den **rohen** Wert zurück. Normalisiert wird an genau einer
 * Stelle (`normalizeLocale` in `resolveLocale`) — ein zweiter Normalisierer
 * könnte davon abweichen.
 *
 * Entwurf: `docs/plans/2026-08-02-c1-i18n.md`.
 */
import { Locale } from './locale';

/**
 * Nächstes `[lang]` über dem Element, meist `<html lang>`.
 *
 * Läuft über Shadow-Grenzen hinweg weiter: steckt das Widget im Shadow-Baum
 * eines fremden Elements, hielte `closest` dort an — und `<html lang>` liegt
 * IMMER ausserhalb jedes Shadow-Roots. Die häufigste Quelle wäre sonst genau
 * dort unerreichbar, wo Seiten aus Komponenten gebaut sind.
 */
export function readHostLocale(el: Element | null | undefined): string | null {
  let node: Node | null = el ?? null;
  while (node) {
    if (node instanceof Element) {
      const treffer = node.closest('[lang]');
      if (treffer) return treffer.getAttribute('lang');
    }
    const wurzel = node.getRootNode();
    node = wurzel instanceof ShadowRoot ? wurzel.host : null;
  }
  return null;
}

/** `navigator.language` — die schwächste der vier Quellen. */
export function readBrowserLocale(): string | null {
  try {
    return navigator?.language || null;
  } catch {
    return null;
  }
}

/**
 * Die gemerkte Nutzerwahl. `null`, wenn keine getroffen wurde oder der
 * Speicher blockiert ist (Privatmodus, Drittanbieter-Kontext).
 *
 * `sessionStorage`, nicht `localStorage`: der Entwurf hält die Wahl „je
 * Sitzung" fest. Sie überlebt damit die Seitenwechsel innerhalb des Tabs — der
 * Regelfall auf WLO, wo das Widget per `?bsid=` mitwandert — und hinterlässt
 * keinen langlebigen Origin-Speicher für eine reine Anzeigeeinstellung.
 *
 * @param key Der Verbraucher nennt seinen Schlüssel selbst (C1-d1). Widget und
 *   Studio laufen auf demselben Origin; mit einem festen Namen überschriebe
 *   eine Wahl still die andere.
 */
export function readStoredLocale(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Nutzerwahl merken. Ein blockierter Speicher ist kein Fehler, den der Nutzer
 *  sehen soll — die Sprache gilt dann eben nur bis zum nächsten Rendern. */
export function writeStoredLocale(key: string, locale: Locale): void {
  try {
    sessionStorage.setItem(key, locale);
  } catch { /* ignore */ }
}
