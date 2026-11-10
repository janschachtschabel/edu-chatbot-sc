/**
 * BadBoerdi-Logo (blaue Eule mit gelbem Schnabel) als Inline-SVG.
 *
 * Master-Datei: badboerdi/Boerdi_small.svg (17 paths, 6 KB).
 *
 * Nur die OUTER-BODY-Pfade (Hauptkörper + Federohren) nutzen `currentColor`,
 * damit das Logo per CSS `color: …` umschaltbar ist:
 *   color: white   → weiße Eule auf brand-blue Hintergrund (FAB, Header)
 *   color: #0E4A92 → blaue Eule auf weißem Hintergrund (msg-avatar)
 *
 * Die Tiefe-Akzente (Bauch hellgrau-blau #9FB7D3, Brust mittelblau #3E6EA8,
 * Augenringe), Pupillen (#1B1B1A) und Schnabel (#FFC600 / #E79800) behalten
 * ihre festen Farben — sonst würde das Gesicht der Eule auf monochromer
 * Container-Färbung verschwinden.
 *
 * Verfügbar in drei Formen:
 *   • BOERDI_LOGO_SVG       — roher SVG-String (für `[innerHTML]`)
 *   • BOERDI_LOGO_DATA_URL  — `data:image/svg+xml;…` (für `<img src=…>`)
 *   • boerdiLogoUrl(apiUrl) — Backend-URL (für Print/Mail-Templates)
 *
 * Bei Logo-Update:
 *   1. badboerdi/Boerdi_small.svg ersetzen
 *   2. backend/app/static/boerdi.svg, frontend/src/assets/boerdi.svg
 *      und studio/public/boerdi.svg synchron aktualisieren
 *   3. BOERDI_LOGO_SVG hier mit neuem Inhalt anpassen — die festen
 *      Farben (Bauch, Augenringe, Schnabel) belassen, nur Body-Pfade
 *      auf currentColor umstellen.
 *   4. Die Pfadzahlen auf eine Nachkommastelle runden (Paket BU-1: −0,8 kB gzip
 *      im Widget-Bündel; in 1000×1000 sind 0,1 Einheiten unsichtbar — geprüft
 *      per Pixelvergleich bei 512 px: nur Kantenglättung weicht ab).
 *      Vorsicht: Zahlen ohne Trenner (`1.5.04` = 1.5 und .04) dürfen beim Runden nicht
 *      verschmelzen — aus `1.5` darf vor `.04` kein `2` werden und `.04` nicht zu `.0` gekürzt
 *      an eine ganze Zahl rücken.
 */

export const BOERDI_LOGO_SVG = `<svg viewBox="0 0 1000 1000" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<path d="M496.3 776.6C610.3 776.6 711.2 832.7 773 918.9C694.5 970.2 600.7 1000 500 1000C397.1 1000 301.5 968.9 222 915.6C283.9 831.3 383.7 776.6 496.3 776.6Z" fill="currentColor"/>
<path d="M836.7 610C836.7 798.4 684.3 951.1 496.3 951.1C308.3 951.1 155.8 798.4 155.8 610C155.8 421.7 308.3 293.2 496.3 293.2C684.3 293.2 836.7 421.7 836.7 610Z" fill="currentColor"/>
<path d="M650.9 909.1C669 923.5 685 940.4 698.3 959.1C637.5 985.4 570.5 1000 500 1000C456.6 1000 414.6 994.5 374.4 984.1C367.2 957.6 355.6 932.2 339.8 909.1C387.2 936.1 440.8 950.3 495.4 950.3C549.9 950.3 603.6 936.1 650.9 909.1Z" fill="#9FB7D3"/>
<path d="M797.4 455.4C797.4 455.4 773.3 431.2 793.9 346.6C808.5 286.5 816.5 214.5 816.3 191.1C816.3 187.5 812.9 185.9 811.1 188.5C798.1 207.4 759.4 257.3 695.6 286.2C649.1 307.3 603.7 330.7 583.5 329C580.5 328.7 579.2 309.6 581.6 311.9L797.4 455.4Z" fill="currentColor"/>
<path d="M192.7 455.4C192.7 455.4 216.8 431.2 196.2 346.6C181.6 286.5 173.6 214.5 173.8 191.1C173.8 187.5 177.1 185.9 179 188.5C192 207.4 230.7 257.3 294.5 286.2C341 307.3 386.4 330.7 406.5 329C409.5 328.7 410.8 309.6 408.4 311.9L192.7 455.4Z" fill="currentColor"/>
<path d="M716.5 270.7C652.1 306.9 593.5 301.8 568.6 296.6C543.7 291.4 533.2 286.2 491.2 287.1C449.1 286.2 438.6 291.4 413.6 296.6C388.6 301.8 337 306.9 272.6 270.7C234.9 249.4 194.2 205.3 179 188C177.8 186.7 176.2 188.6 176.9 190.3C188.7 216.5 223.9 290.4 258.2 317.3C300.2 350.1 335.3 364.5 382.7 363.4C430.2 362.2 494.5 440.4 494.5 440.4C494.5 440.4 558.8 362.2 606.3 363.4C653.8 364.6 688.8 350.1 730.8 317.3C765.9 289.9 801.9 213.2 812.8 188.6C812.9 188.4 812.9 188 812.8 187.8C812.8 187.5 812.6 187.2 812.3 187.1C812.1 186.9 811.8 186.8 811.5 186.9C811.2 186.9 810.9 187.1 810.7 187.3C796.2 204 754.8 249.1 716.5 270.7Z" fill="#3E6EA8"/>
<path d="M793.1 513.2C780.4 412.5 696.8 340.1 606.3 351.5C559.7 357.4 520.4 384.5 494.9 423.2C469.5 384.5 430.2 357.4 383.5 351.5C293.1 340.1 209.4 412.5 196.8 513.2C184.1 613.9 247.1 704.8 337.5 716.4C400.5 724.3 460.2 691.6 494.9 636.8C529.6 691.6 589.3 724.3 652.4 716.4C742.8 704.9 805.8 613.9 793.1 513.2Z" fill="#9FB7D3"/>
<path d="M482.8 549.3C491.8 477.8 447.1 413.2 382.9 405.1C318.7 396.9 259.4 448.3 250.3 519.9C241.3 591.4 286 655.9 350.2 664.1C414.4 672.2 473.7 620.8 482.8 549.3Z" fill="white"/>
<path d="M459.2 582C464.9 536.9 436.6 496.1 396.1 491C355.6 485.9 318.2 518.3 312.5 563.4C306.8 608.6 335 649.3 375.5 654.4C416 659.6 453.5 627.1 459.2 582Z" fill="#1B1B1A"/>
<path d="M354.3 569.7C359 569.7 363.7 568.3 367.7 565.6C371.6 563 374.7 559.2 376.6 554.8C378.4 550.3 378.9 545.5 377.9 540.8C377 536.1 374.7 531.8 371.3 528.4C368 525 363.7 522.7 359 521.8C354.3 520.9 349.4 521.4 345 523.2C340.6 525 336.9 528.1 334.2 532.1C331.6 536.1 330.1 540.7 330.1 545.5C330.1 551.9 332.7 558.1 337.2 562.6C341.7 567.1 347.9 569.7 354.3 569.7Z" fill="white"/>
<path d="M639.1 663.1C703.2 655 748 590.4 738.9 518.9C729.9 447.4 670.5 396 606.3 404.1C542.2 412.3 497.4 476.9 506.5 548.4C515.5 619.9 574.9 671.3 639.1 663.1Z" fill="white"/>
<path d="M613.7 653.5C654.2 648.4 682.5 607.6 676.8 562.5C671.1 517.4 633.6 484.9 593.1 490.1C552.6 495.2 524.4 536 530.1 581.1C535.8 626.2 573.2 658.7 613.7 653.5Z" fill="#1B1B1A"/>
<path id="boerdi-beak-upper" d="M596.8 714.4C596.8 762.9 497.6 831.7 496 831.7C494.4 831.7 395.2 763 395.2 714.4C395.2 667 482.4 603.6 496 603.9C509.6 604.1 596.8 667 596.8 714.4Z" fill="#FFC600"/>
<path id="boerdi-beak-lower" d="M568.7 693.9C548.3 702.1 523.6 752.6 496.2 752.6C468.7 752.6 444.2 702.1 423.8 693.9C403.4 685.7 395.5 714.4 395.5 714.4H395.2C395.2 763 481 831.8 496 831.8C511 831.8 596.8 763 596.8 714.4V714C595.3 712.1 587.1 686.6 568.7 693.9Z" fill="#E79800"/>
<path d="M568.7 569.7C564 569.7 559.3 568.3 555.3 565.6C551.4 563 548.3 559.2 546.4 554.8C544.6 550.3 544.1 545.5 545.1 540.8C546 536.1 548.3 531.8 551.7 528.4C555 525 559.3 522.7 564 521.8C568.7 520.9 573.6 521.4 578 523.2C582.4 525 586.1 528.1 588.8 532.1C591.4 536.1 592.9 540.7 592.9 545.5C592.9 551.9 590.3 558.1 585.8 562.6C581.3 567.1 575.1 569.7 568.7 569.7V569.7Z" fill="white"/>
<path d="M415.6 305.2H575.9C575.9 305.2 564.5 290.3 569 265.5C572.5 246.5 586.3 227.5 586.3 227.5C586.3 227.5 557 227.5 543.2 244.8C538.1 251.4 534.4 258.9 532.1 267C532.1 267 522.1 224.8 501.8 199.9C481.5 175 444.9 168.8 444.9 168.8C444.9 168.8 466.4 198.9 467.4 227.5C468.3 256.2 462.2 267 462.2 267C459.7 252.9 452.4 240.2 441.5 231C430.9 222.1 417.4 217.2 403.6 217.2C403.6 217.2 420.8 241.3 420.8 269C420.8 296.6 415.6 305.2 415.6 305.2Z" fill="#3E6EA8"/>
</svg>`;

/**
 * Same SVG as a Data-URL — use as `<img src="...">` value when CSP forbids
 * inline SVG via `[innerHTML]`, or when you want simple `<img>` semantics.
 */
export const BOERDI_LOGO_DATA_URL = (() => {
  const compact = BOERDI_LOGO_SVG.replace(/\s+/g, ' ').trim();
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(compact)}`;
})();

/**
 * Build an absolute backend URL for the logo asset (master colors, no
 * currentColor — for print/email where CSS color inheritance isn't usable).
 *
 * Falls back to a relative path if `apiUrl` is empty.
 */
export function boerdiLogoUrl(apiUrl?: string): string {
  const base = (apiUrl || '').replace(/\/+$/, '');
  return `${base}/api/static/boerdi.svg`;
}
