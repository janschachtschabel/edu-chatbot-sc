// ERZEUGT von `npm run module:register` — nicht von Hand ändern.
// Quelle: die Modul-Ordner unter projects/ui-module/src/ui-*/ (manifest.json + Komponente).
import type { ModulRegister } from './_vertrag/register';
import { UiEntscheidung } from './ui-entscheidung/ui-entscheidung.component';
import { UiInhaltsrahmen } from './ui-inhaltsrahmen/ui-inhaltsrahmen.component';
import { UiLinkbox } from './ui-linkbox/ui-linkbox.component';
import { UiStrukturentwurf } from './ui-strukturentwurf/ui-strukturentwurf.component';
import { UiThemenbaum } from './ui-themenbaum/ui-themenbaum.component';
import { UiTrefferliste } from './ui-trefferliste/ui-trefferliste.component';

export const MODUL_REGISTER: ModulRegister = {
  ui_entscheidung: { manifest: {"name":"ui_entscheidung","version":1,"art":"abfragen","titel":{"de":"Entscheidung","en":"Choice"},"faehigkeiten":["antworten"],"darstellung":{"breit":false}}, komponente: UiEntscheidung },
  ui_inhaltsrahmen: { manifest: {"name":"ui_inhaltsrahmen","version":1,"art":"anzeigen","titel":{"de":"Inhaltsrahmen","en":"Content frame"},"faehigkeiten":["drucken","herunterladen"],"darstellung":{"breit":false}}, komponente: UiInhaltsrahmen },
  ui_linkbox: { manifest: {"name":"ui_linkbox","version":1,"art":"anzeigen","titel":{"de":"Webseiten-Inhalte","en":"Web page contents"},"faehigkeiten":["oeffnen"],"darstellung":{"breit":false,"platz":"unten"}}, komponente: UiLinkbox },
  ui_strukturentwurf: { manifest: {"name":"ui_strukturentwurf","version":1,"art":"abfragen","titel":{"de":"Strukturentwurf","en":"Structure draft"},"faehigkeiten":["antworten","herunterladen"],"darstellung":{"breit":false,"platz":"oben"}}, komponente: UiStrukturentwurf },
  ui_themenbaum: { manifest: {"name":"ui_themenbaum","version":1,"art":"anzeigen","titel":{"de":"Themenbaum","en":"Topic tree"},"faehigkeiten":["oeffnen","nachladen"],"darstellung":{"breit":false,"platz":"oben"}}, komponente: UiThemenbaum },
  ui_trefferliste: { manifest: {"name":"ui_trefferliste","version":1,"art":"anzeigen","titel":{"de":"Trefferliste","en":"Results"},"faehigkeiten":["oeffnen"],"darstellung":{"breit":false,"platz":"unten"}}, komponente: UiTrefferliste },
};
