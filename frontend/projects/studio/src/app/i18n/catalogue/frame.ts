/**
 * Der Rahmen des Studios (C1-d1): Hülle, Navigation, Statusanzeige, Anmeldung
 * — und `format.htmlLang`, das keine Ansicht betrifft, sondern die ganze Seite.
 */
import type { CataloguePart } from './catalogue-part';

export const FRAME: CataloguePart = {
  de: {
    /** Produktname — bleibt in jeder Sprache stehen. */
    'studio.title': 'BOERDi Studio',
    'studio.skipToContent': 'Zum Inhalt springen',

    // ── Navigation ──────────────────────────────────────────────────
    /** Beschriftung des Schubladen-Knopfs im geschlossenen Zustand. */
    'studio.nav.label': 'Navigation',
    'studio.nav.close': 'Navigation schließen',
    /** Zugänglicher Name des `<nav>` — trennt es von anderen Navigationen
     *  derselben Seite, sobald es mehr als eine gibt. */
    'studio.nav.areas': 'Konfigurationsbereiche',

    // ── Statusanzeige ───────────────────────────────────────────────
    'studio.status.unknown': 'Verbindung wird geprüft',
    'studio.status.online': 'Verbunden',
    'studio.status.offline': 'Offline',

    // ── Abmelden ────────────────────────────────────────────────────
    'studio.logout': 'Abmelden',
    'studio.loggingOut': 'Melde ab …',

    /** Zugänglicher Name des Sprach-Umschalters. Er benennt die ZIELsprache,
     *  denn das ist, was der Knopf tut. Ein Schlüssel je Ziel statt eines mit
     *  Platzhalter: „Auf Englisch umschalten" beugt im Deutschen den
     *  Sprachnamen, und die Zuordnung Ziel→Schlüssel bleibt eine
     *  Erlaubnisliste im Code. */
    'studio.language.toDe': 'Auf Deutsch umschalten',
    'studio.language.toEn': 'Auf Englisch umschalten',

    // ── Anmeldung ───────────────────────────────────────────────────
    'login.password': 'Passwort',
    'login.hint': 'Bitte Passwort eingeben.',
    'login.expired': 'Die Sitzung ist abgelaufen. Bitte erneut anmelden.',
    'login.submit': 'Anmelden',
    'login.checking': 'Prüfe …',
    /** Name der Umgebungsvariablen — als Platzhalterwert und nicht im Satz,
     *  damit der Satz als Ganzes übersetzbar bleibt. */
    'login.passwordEnv': 'STUDIO_PASSWORD',
    'login.notConfigured':
      'Das Studio ist nicht eingerichtet: es ist kein Passwort konfiguriert '
      + '({env}). Bitte in der Server-Konfiguration setzen.',

    // Fehlermeldungen der Anmeldung. ALT zeigte für jede Ursache denselben
    // Satz; die Trennung ist eine Verbesserung von P9-2 und bleibt erhalten.
    'login.error.wrongPassword': 'Falsches Passwort.',
    'login.error.tooMany': 'Zu viele Versuche. Bitte eine Minute warten.',
    'login.error.notConfigured': 'Das Studio ist nicht eingerichtet (kein Passwort konfiguriert).',
    'login.error.offline': 'Backend nicht erreichbar. Läuft der Server?',
    'login.error.generic': 'Anmeldung fehlgeschlagen (Fehler {status}).',
    'login.error.unexpected': 'Unerwarteter Fehler. Bitte erneut versuchen.',

    /** Kein Text, sondern der Wert für `<html lang>`. Das Studio ist eine
     *  ganze Seite und trägt ihn nach — ohne das liest ein Screenreader
     *  englische Oberfläche mit deutscher Aussprache vor (WCAG 3.1.1). */
    'format.htmlLang': 'de',
    /** Ebenfalls kein Text, sondern das BCP-47-Kürzel für `Intl` (C1-d4f):
     *  Zahlen, Datum, Währung, Prozent. Steht im Katalog und nicht im Code,
     *  weil es eine Entscheidung JE SPRACHE ist — genau wie `htmlLang`.
     *
     *  Englisch als `en-GB` und nicht `en-US`: das Studio gehört zu einer
     *  deutschen Bildungsplattform, und „7/24/2026" neben dem „24.7.2026" der
     *  Kollegin sind dieselben Ziffern in umgekehrter Bedeutung. `en-GB` hält
     *  den Tag vorn — die beiden Sprachen unterscheiden sich dann nur noch im
     *  Trennzeichen. */
    'format.locale': 'de-DE',
    /** `Intl.RelativeTimeFormat` kennt keinen Fall unter einer Minute; dieser
     *  eine Text ist daher redaktionell und kein Format. */
    'format.justNow': 'gerade eben',
  },

  en: {
    'studio.title': 'BOERDi Studio',
    'studio.skipToContent': 'Skip to content',

    'studio.nav.label': 'Navigation',
    'studio.nav.close': 'Close navigation',
    'studio.nav.areas': 'Configuration areas',

    'studio.status.unknown': 'Checking connection',
    'studio.status.online': 'Connected',
    'studio.status.offline': 'Offline',

    'studio.logout': 'Sign out',
    'studio.loggingOut': 'Signing out …',

    'studio.language.toDe': 'Switch to German',
    'studio.language.toEn': 'Switch to English',

    'login.password': 'Password',
    'login.hint': 'Please enter the password.',
    'login.expired': 'The session has expired. Please sign in again.',
    'login.submit': 'Sign in',
    'login.checking': 'Checking …',
    'login.passwordEnv': 'STUDIO_PASSWORD',
    'login.notConfigured':
      'The studio is not set up: no password is configured ({env}). '
      + 'Please set it in the server configuration.',

    'login.error.wrongPassword': 'Wrong password.',
    'login.error.tooMany': 'Too many attempts. Please wait a minute.',
    'login.error.notConfigured': 'The studio is not set up (no password configured).',
    'login.error.offline': 'Backend unreachable. Is the server running?',
    'login.error.generic': 'Sign-in failed (error {status}).',
    'login.error.unexpected': 'Unexpected error. Please try again.',

    'format.htmlLang': 'en',
    'format.locale': 'en-GB',
    'format.justNow': 'just now',
  },
};
