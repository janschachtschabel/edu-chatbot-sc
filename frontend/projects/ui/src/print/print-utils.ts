/**
 * Print-/PDF-Views (Druckfenster via ``window.open`` + ``document.write``)
 * — extrahiert aus ``chat.component.ts`` (Frontend-Split Welle 2,
 * Schritt 7, 2026-07-09).
 *
 * Die Komponente behält gleichnamige dünne Delegates (Template-Bindings
 * und Specs bleiben unverändert). Bodies verbatim übernommen — KEINE
 * Logik-Änderung.
 *
 * Hier stand, die Print-Pfade seien ungetestet, weil jsdom ``window.open`` in
 * ein Zweitfenster nicht ehrlich faken könne. Das stimmt so nicht: eine
 * Attrappe **nur** für `window.open` lässt den Modul-Pfad echt bis in das
 * geschriebene HTML laufen (``print-gates.spec`` tut das seit dem Port, seit
 * C1-b4 auch ``print-utils.spec`` für Canvas- und Lernpfad-Fenster). Was
 * ungetestet bleibt, ist allein der Druck selbst.
 *
 * mdToHtml-Dedup-Befund (Diff der 3 Inline-Kopien, 2026-07-09):
 *  - ``printCanvasMaterial`` und ``printLearningPath`` waren semantisch
 *    IDENTISCH (byte-gleich modulo Kommentare/Heading-Formatierung).
 *  - ``_printMarkdown`` unterschied sich NUR im Blockquote-Handling:
 *    kein ``^&gt;``-Restore nach dem HTML-Escape und kein
 *    ``<blockquote>``-Zeilen-Branch (``> x`` wird dort als ``<p>&gt; x</p>``
 *    ausgegeben). Dieses IST-Verhalten bleibt über den dokumentierten
 *    ``blockquotes``-Parameter je Call-Site exakt erhalten — KEINE
 *    Vereinheitlichung abweichenden Verhaltens.
 */
import { ChatMessage } from '../grouping/message-types';
import { BOERDI_LOGO_DATA_URL } from '../branding/boerdi-logo';
import type { TranslateFn } from '../i18n/i18n';
import { stripLatex } from '../markdown/latex';

// Sentinel-Format vom Backend (chat.py _apply_widget_modes_postprocess):
//   <!-- boerdi:printable-canvas|<material_type>|<title> -->
// Wird vor jedes Canvas-Markdown im Inline-Modus (canvas-enabled="false")
// gestellt, sodass das Frontend den Print-Button anbieten kann.
// (Nicht-global → kein lastIndex-State; Instanz gefahrlos teilbar.)
export const PRINTABLE_CANVAS_RE =
  /<!--\s*boerdi:printable-canvas\|([^|]*)\|([^>]*?)\s*-->/;

/** HTML-Escape für Text, der in die Druck-Templates interpoliert wird.
 *  Vorher 3× byte-identisch inline in den Print-Methoden. */
const esc = (s: string) =>
  (s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c] as string));

/** Nur http(s)-URLs als klickbaren Print-Link zulassen. Das Druckfenster
 *  erbt die Host-Origin — ein ``javascript:``/``data:``-URI in einem
 *  ``href`` wäre dort klickbar (Audit 2026-07-09). Alles außer http(s)
 *  (getrimmt) → ``''`` = kein Link. Gleiche Protokoll-Prüfung wie
 *  ``withBsid``/``resolveGuideNavUrl``. */
export function safePrintHref(url: string | null | undefined): string {
  const raw = (url || '').trim();
  return /^https?:\/\//i.test(raw) ? raw : '';
}

/**
 * Datum der Kopf-/Fußzeile in der Sprache des Nutzers (C1-b4).
 *
 * Der BCP-47-Tag kommt aus dem Katalog (`format.dateLocale`), nicht aus einem
 * zweiten Parameter: das Druckfenster ist ein Dokument ohne Angular, das sein
 * HTML als String baut — `t` ist der einzige Kanal, über den die Sprache dort
 * ankommt, und ein zweiter wäre ein Weg mehr für dieselbe Sache. Dass der Tag
 * für `Intl` brauchbar ist, prüft ein Test (der Katalog ist Code, kein
 * Nutzereingabe-Feld).
 */
function printDate(t: TranslateFn): string {
  return new Date().toLocaleDateString(t('format.dateLocale'), {
    year: 'numeric', month: 'long', day: 'numeric',
  });
}

/**
 * Minimaler Markdown→HTML-Renderer für die Druckfenster (bewusst unabhängig
 * von ``renderMarkdown``/Angular DomSanitizer — die Print-Page läuft im
 * neuen Window ohne Angular). LaTeX-Stripping wird vorab angewendet, damit
 * ``\frac12`` etc. nicht roh in den Print landen.
 *
 * ``blockquotes: true`` (Default, Canvas/Lernpfad-Pfad): ``> x``-Zeilen
 * werden nach dem HTML-Escape zurückrestauriert und als ``<blockquote>``
 * gerendert. ``blockquotes: false`` (InlineDocument-Pfad, IST-Verhalten
 * von ``_printMarkdown``): kein Restore, ``> x`` erscheint als
 * ``<p>&gt; x</p>``.
 */
export function printMdToHtml(
  text: string,
  opts: { blockquotes?: boolean } = {},
): string {
  const blockquotes = opts.blockquotes !== false;
  let html = stripLatex(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>');
  if (blockquotes) {
    // Restore blockquote markers (we just HTML-escaped them to &gt;)
    html = html.replace(/^&gt;\s?/gm, '> ');
  }
  html = html.replace(/\[(.+?)\]\((https?:[^)]+)\)/g,
    // A4 (2026-06-10): URL-Sonderzeichen encoden — ein '"' in der
    // Markdown-URL brach sonst aus dem href-Attribut aus (XSS im
    // Druckfenster, das die Host-Origin erbt).
    (_m: string, label: string, url: string) =>
      `<a href="${url.replace(/["'\s]/g, (c: string) => encodeURIComponent(c))}" target="_blank" rel="noopener">${label}</a>`);
  const lines = html.split('\n');
  const out: string[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      const lvl = Math.min(h[1].length + 1, 6);
      out.push(`<h${lvl}>${h[2]}</h${lvl}>`);
      continue;
    }
    if (blockquotes) {
      const bq = line.match(/^>\s?(.*)$/);
      if (bq) { out.push(`<blockquote>${bq[1]}</blockquote>`); continue; }
    }
    const ol = line.match(/^(\d+)\.\s+(.*)$/);
    if (ol) { out.push(`<div class="ol"><span class="n">${ol[1]}.</span> ${ol[2]}</div>`); continue; }
    const li = line.match(/^(?:[-•]|\*(?!\*))\s+(.*)/);
    if (li) { out.push(`<div class="li"><span class="b">•</span> ${li[1]}</div>`); continue; }
    if (line) out.push(`<p>${line}</p>`);
  }
  return out.join('\n');
}

/** Gemeinsamer Markdown-Print-Helper für InlineDocument + Legacy-Canvas
 *  (vorher ``ChatComponent._printMarkdown``). Auto-Print nach Load.
 *
 *  `t` (C1-b4) trägt hier keinen sichtbaren Text — der Titel kommt vom
 *  Aufrufer —, sondern die `lang`-Auszeichnung. Die fehlte bisher ganz; mit
 *  zwei Sprachen im Spiel wäre ein nicht ausgezeichnetes Dokument die Vorlage
 *  dafür, dass ein Screenreader englischen Text deutsch vorliest (WCAG 3.1.1). */
export function printMarkdownDocument(title: string, markdown: string, t: TranslateFn): void {
  const body = printMdToHtml(markdown || '', { blockquotes: false });
  /* eslint-disable no-useless-escape -- Das `<\/script>` weiter unten ist
     bewusst escaped (verbatim aus ALT): das Widget-Bundle darf von einer
     Host-Seite inline in einen `<script>`-Block gelegt werden, wo ein
     wörtliches `</script>` diesen Block vorzeitig beenden würde. Für JS selbst
     ist der Backslash bedeutungslos — die Regel sieht nur den halben Grund. */
  const html = `<!doctype html><html lang="${esc(t('format.htmlLang'))}"><head><meta charset="utf-8"><title>${esc(title)}</title>
<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:780px;margin:32px auto;padding:0 24px;color:#111;line-height:1.5}
h1,h2,h3,h4{color:#1c4587;margin:1em 0 .4em}h1{font-size:1.6em;border-bottom:2px solid #1c4587;padding-bottom:.2em}
p{margin:.4em 0}.li,.ol{margin:.2em 0 .2em 1em}.n,.b{display:inline-block;width:1.5em;color:#1c4587;font-weight:600}
a{color:#1c4587}@media print{a{color:inherit;text-decoration:none}}</style></head>
<body><h1>${esc(title)}</h1>${body}<script>window.onload=function(){setTimeout(function(){window.print()},300)}<\/script></body></html>`;
  /* eslint-enable no-useless-escape */
  const w = window.open('', '_blank');
  if (w) { w.document.write(html); w.document.close(); }
}

/**
 * Render an inline canvas-material message (Arbeitsblatt, Quiz, Bericht,
 * …) into a clean printable window — same pattern as ``printLearningPath``
 * but generic over the material type. The sentinel-comment is stripped
 * from the markdown before rendering so it doesn't show up in print.
 */
export function printCanvasMaterial(msg: ChatMessage, t: TranslateFn): void {
  const m = (msg.content || '').match(PRINTABLE_CANVAS_RE);
  if (!m) return;
  // Typ und Titel stehen im Backend-Sentinel und bleiben unübersetzt (C1-b3);
  // nur ihr Rückfall geht durch den Katalog — derselbe Schlüssel, den auch
  // `printableCanvasLabel` für die Knopf-Beschriftung nimmt.
  const materialType = ((m[1] || 'material').trim() || 'material');
  const rueckfall = t('chat.print.canvasFallback');
  const docTitle = ((m[2] || rueckfall).trim() || rueckfall);
  // Markdown ohne Sentinel — der ist nur ein Marker, nicht Teil des Inhalts.
  const md = (msg.content || '')
    .replace(PRINTABLE_CANVAS_RE, '')
    .trim();

  // Material-Type-Label für Header — capitalize first letter.
  const typeLabel = materialType
    ? materialType.charAt(0).toUpperCase() + materialType.slice(1)
    : rueckfall;
  const today = printDate(t);

  const html = `<!doctype html>
<html lang="${esc(t('format.htmlLang'))}">
<head>
<meta charset="utf-8">
<title>${esc(t('print.docTitle', { title: docTitle }))}</title>
<style>
  /* @page steuert den Druck-Rand (A4 mit komfortabler Marge). Im Browser-
     Modus arbeitet der body mit auto-margin + festem max-width, damit der
     Inhalt zentriert ist und genug Rand-Whitespace zum Fenster bleibt. */
  @page { size: A4; margin: 18mm 16mm 18mm 16mm; }
  html { background: #f1f5f9; }
  body {
    font: 11pt/1.55 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    color: #222; max-width: 760px; margin: 32px auto 64px;
    padding: 36px 44px; background: #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    border-radius: 4px;
  }
  header { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-bottom: 14px; }
  header h1 { margin: 0; font-size: 16pt; color: #1e40af; }
  header .meta { font-size: 9pt; color: #6b7280; }
  h1, h2, h3, h4 { color: #1e40af; margin: 14px 0 4px; }
  h2 { font-size: 13pt; }
  h3 { font-size: 12pt; }
  blockquote { border-left: 3px solid #c5cbd6; background: #f6f8fb; margin: 6px 0; padding: 6px 12px; color: #3a4252; }
  p { margin: 4px 0; }
  .ol, .li { display: flex; margin: 3px 0; padding-left: 2px; }
  .ol .n, .li .b { flex-shrink: 0; margin-right: 8px; color: #3b82f6; font-weight: 600; }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
  footer { margin-top: 24px; padding-top: 8px; border-top: 1px solid #e5e7eb; font-size: 8.5pt; color: #6b7280; text-align: center; }
  .print-bar { position: fixed; top: 0; right: 0; padding: 10px 14px; background: #fff; border-bottom-left-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,.1); z-index: 10; }
  .print-bar button { padding: 6px 14px; background: #3b82f6; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 10pt; }
  .print-bar button:hover { background: #2563eb; }
  /* Im Druck: keine Schatten, keine max-width — die @page-margins über-
     nehmen das Seiten-Layout, sonst verschwendet die feste body-Breite
     Platz auf der Druckseite. Body behält ein Mindest-Padding, falls
     der User in Chrome "Ränder: Minimum" oder "Keine" wählt und damit
     die @page-margins überschreibt — sonst wäre der Druck randlos. */
  @media print {
    html { background: #fff; }
    .print-bar { display: none; }
    body {
      padding: 12mm 14mm;
      margin: 0;
      max-width: none;
      box-shadow: none;
      border-radius: 0;
    }
  }
</style>
</head>
<body>
<div class="print-bar"><button onclick="window.print()">${esc(t('print.button'))}</button></div>
<header>
  <h1><img src="${BOERDI_LOGO_DATA_URL}" alt="" style="width:28px;height:28px;vertical-align:-6px;margin-right:6px;"/> ${esc(docTitle || typeLabel)}</h1>
  <span class="meta">${esc(t('print.meta', { date: today }))}</span>
</header>
<main>
  ${printMdToHtml(md)}
</main>
<footer>${esc(t('print.footer', { date: today }))}</footer>
<!-- Kein auto-print mehr: der User sieht erst die Preview im neuen
     Tab und klickt dann selbst "Drucken / Als PDF speichern". Vorher
     auto-print direkt nach load, was den User vor dem Druck-Dialog
     stranden ließ wenn er ihn versehentlich abbrach. -->
</body>
</html>`;

  const w = window.open('', '_blank', 'width=900,height=1100');
  if (!w) {
    alert(t('print.popupBlockedMaterial'));
    return;
  }
  w.document.open();
  w.document.write(html);
  w.document.close();
}

/**
 * Open a clean, printable Lernpfad view in a new window and trigger the
 * browser print dialog. Users can then "Save as PDF" from the dialog —
 * no server-side PDF rendering needed, works identically on all browsers.
 */
export function printLearningPath(msg: ChatMessage, t: TranslateFn): void {
  // Wenn der Lernpfad im Inline-Modus erzeugt wurde, hat das Backend einen
  // ``<!-- boerdi:printable-canvas|... -->``-Sentinel vor das Markdown
  // gestellt (siehe chat.py _apply_widget_modes_postprocess). Im PDF-
  // Render-Pfad würde printMdToHtml den Kommentar HTML-escapen und als
  // sichtbaren Text auswerfen — daher hier vorher strippen, identisch
  // zu printCanvasMaterial.
  const lpContent = (msg.content || '').replace(PRINTABLE_CANVAS_RE, '').trim();
  const cards = msg.cards || [];
  const cardsHtml = cards.map(c => {
    const types = (c.learning_resource_types || []).filter(
      t => t !== 'Sammlung' && t !== 'collection'
    );
    const meta = [
      ...(c.disciplines || []),
      ...(c.educational_contexts || []),
      ...types,
      c.license,
    ].filter(Boolean).map(x => `<span class="chip">${esc(x!)}</span>`).join('');
    // Nur http(s) durchlassen — ein ``javascript:``-URI wäre im Druckfenster
    // (das die Host-Origin erbt) sonst klickbar. Kein Link → nur Titel-Text.
    const href = safePrintHref(c.link || c.guide_url || c.wlo_url || c.url);
    const desc = c.description
      ? `<div class="desc">${esc(c.description.slice(0, 220))}${c.description.length > 220 ? '…' : ''}</div>`
      : '';
    const thumb = c.preview_url
      ? `<img class="thumb" src="${esc(c.preview_url)}" alt="">`
      : `<div class="thumb thumb-ph">📄</div>`;
    const titleHtml = href
      ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(c.title)}</a>`
      : esc(c.title);
    return `
      <div class="card">
        ${thumb}
        <div class="card-body">
          <div class="card-title">${titleHtml}</div>
          <div class="chips">${meta}</div>
          ${desc}
          ${href ? `<div class="card-url">${esc(href)}</div>` : ''}
        </div>
      </div>`;
  }).join('');

  const today = printDate(t);
  const lpTitel = t('print.learningPath');

  const html = `<!doctype html>
<html lang="${esc(t('format.htmlLang'))}">
<head>
<meta charset="utf-8">
<title>${esc(t('print.docTitle', { title: lpTitel }))}</title>
<style>
  /* Browser-Preview: zentriertes "Papier" auf grauem Hintergrund. Im
     Druck übernehmen die @page-margins, body wird entkleidet. */
  @page { size: A4; margin: 18mm 16mm 18mm 16mm; }
  html { background: #f1f5f9; }
  body {
    font: 11pt/1.55 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    color: #222; max-width: 760px; margin: 32px auto 64px;
    padding: 36px 44px; background: #fff;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    border-radius: 4px;
  }
  header { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-bottom: 14px; }
  header h1 { margin: 0; font-size: 16pt; color: #1e40af; }
  header .meta { font-size: 9pt; color: #6b7280; }
  h1, h2, h3, h4 { color: #1e40af; margin: 14px 0 4px; }
  h2 { font-size: 13pt; }
  h3 { font-size: 12pt; }
  blockquote { border-left: 3px solid #c5cbd6; background: #f6f8fb; margin: 6px 0; padding: 6px 12px; color: #3a4252; }
  p { margin: 4px 0; }
  .ol, .li { display: flex; margin: 3px 0; padding-left: 2px; }
  .ol .n, .li .b { flex-shrink: 0; margin-right: 8px; color: #3b82f6; font-weight: 600; }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
  section.cards { margin-top: 22px; page-break-before: auto; }
  section.cards h2 { font-size: 12pt; margin-bottom: 8px; }
  .card { display: flex; gap: 10px; border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px; margin-bottom: 8px; page-break-inside: avoid; }
  .thumb { width: 60px; height: 60px; object-fit: cover; border-radius: 4px; flex-shrink: 0; background: #f3f4f6; display: flex; align-items: center; justify-content: center; font-size: 22pt; color: #9ca3af; }
  .card-body { flex: 1; min-width: 0; }
  .card-title { font-weight: 600; font-size: 10.5pt; }
  .card-title a { color: #1e40af; }
  .chips { margin: 3px 0; }
  .chip { display: inline-block; font-size: 8pt; background: #eef2ff; color: #4338ca; border-radius: 10px; padding: 1px 7px; margin-right: 4px; margin-bottom: 2px; }
  .desc { font-size: 9.5pt; color: #4b5563; margin: 3px 0; }
  .card-url { font-size: 8pt; color: #6b7280; word-break: break-all; }
  footer { margin-top: 24px; padding-top: 8px; border-top: 1px solid #e5e7eb; font-size: 8.5pt; color: #6b7280; text-align: center; }
  .print-bar { position: fixed; top: 0; right: 0; padding: 10px 14px; background: #fff; border-bottom-left-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,.1); z-index: 10; }
  .print-bar button { padding: 6px 14px; background: #3b82f6; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 10pt; }
  .print-bar button:hover { background: #2563eb; }
  @media print {
    html { background: #fff; }
    .print-bar { display: none; }
    /* Mindest-Padding, falls der User "Ränder: Minimum/Keine" wählt und
       damit die @page-margins (18/16mm) überschreibt. Sonst randlos. */
    body {
      padding: 12mm 14mm;
      margin: 0;
      max-width: none;
      box-shadow: none;
      border-radius: 0;
    }
  }
</style>
</head>
<body>
<div class="print-bar"><button onclick="window.print()">${esc(t('print.button'))}</button></div>
<header>
  <h1><img src="${BOERDI_LOGO_DATA_URL}" alt="" style="width:28px;height:28px;vertical-align:-6px;margin-right:6px;"/> ${esc(lpTitel)}</h1>
  <span class="meta">${esc(t('print.meta', { date: today }))}</span>
</header>
<main>
  ${printMdToHtml(lpContent)}
</main>
${cards.length ? `<section class="cards"><h2>${esc(t('print.usedContents', { count: cards.length }))}</h2>${cardsHtml}</section>` : ''}
<footer>${esc(t('print.footer', { date: today }))}</footer>
<!-- Kein auto-print mehr: der User sieht erst die Preview im neuen
     Tab und klickt dann selbst "Drucken / Als PDF speichern". Vorher
     auto-print direkt nach load, was den User vor dem Druck-Dialog
     stranden ließ wenn er ihn versehentlich abbrach. -->
</body>
</html>`;

  const w = window.open('', '_blank', 'width=900,height=1100');
  if (!w) {
    alert(t('print.popupBlockedLearningPath'));
    return;
  }
  w.document.open();
  w.document.write(html);
  w.document.close();
}
