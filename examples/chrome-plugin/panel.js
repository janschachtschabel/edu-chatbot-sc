/**
 * Die Verdrahtung der Seitenleiste: Steuerung → Widget → Ergebnis.
 *
 * Der ganze Umgang mit dem Chat besteht aus vier Zeilen der öffentlichen API
 * (`replaceContext`, `startTask`) plus einem Zuhörer auf `boerdi:agent-result`.
 * Alles andere hier ist Formular.
 *
 * Die Module daneben tragen je eine eigene Änderungs-Ursache: `backend.js`
 * (welche Adresse gilt und lebt sie), `buendel.js` (wie das Widget in die
 * Seite kommt), `tab-lesen.js` (was der Nachbar-Tab hergibt und was Chrome
 * dafür verlangt), `schemas.js` (was ein gültiges Struktur-Schema ist),
 * `ergebnisse.js` (wie ein Zug-Ergebnis aussieht), `context.js`,
 * `einstellungen.js`, `tabs.js`.
 *
 * Was hier bleibt, ist die Verdrahtung selbst — Formularfeld lesen, Modul
 * rufen, Ergebnis anzeigen. Die Datei ist deshalb länger als die 300 Zeilen
 * der Hausregel und bleibt es: sie hat EINE Änderungs-Ursache („die
 * Verdrahtung der Leiste ändert sich"), und sie weiter zu zerteilen ergäbe
 * Module, die man nur im Doppelpack lesen kann.
 */
import { basisAusEingabe, pruefeGesundheit } from './backend.js';
import { ladeBuendel } from './buendel.js';
import { baueKontext } from './context.js';
import { GEMERKTE_FELDER, ladeEinstellungen, merkeEinstellungen } from './einstellungen.js';
import { leereErgebnisse, zeigeErgebnis } from './ergebnisse.js';
import { VORLAGEN, pruefeSchema, vorlage } from './schemas.js';
import { erlaubeUndLies, liesTab } from './tab-lesen.js';
import { verdrahteReiter } from './tabs.js';

const $ = (id) => document.getElementById(id);

/**
 * Die geltende API-Basis samt der Frage, ob dabei die eine eindeutige
 * Verwechslung korrigiert wurde (Bündel-Adresse im Backend-Feld).
 *
 * **Schreibt nichts.** Wer den Hinweis zeigt, entscheidet der Aufrufer. Vorher
 * schrieb diese Funktion selbst in `#backendStatus` — und „Verbindung prüfen"
 * löschte ihn zwei Zeilen später wieder, im selben synchronen Block. Die
 * Meldung, die es für den häufigsten Fehler gibt, war auf genau dem Knopf, der
 * dafür gebaut wurde, nie zu sehen (Review 2026-08-14).
 */
function apiBasis() {
  return basisAusEingabe($('apiUrl').value);
}

/** Vorangestellter Satz, wenn die Adresse korrigiert wurde — sonst leer. Eine
 *  Stelle für beide Knöpfe, sonst formulierten sie es verschieden. */
function korrekturVorspann({ basis, korrigiert }) {
  return korrigiert
    ? `Das war die Bündel-Adresse — gerechnet wird mit ${basis}, bitte oben so eintragen. `
    : '';
}

/** Was der letzte „Aus dem Tab übernehmen"-Klick ergeben hat. `tabId` und
 *  `herkunft` reisen mit, weil der Erlauben-Knopf beides braucht und beide
 *  denselben Tab meinen müssen wie die Adresse darüber. */
let tab = { url: '', titel: '', text: '', tabId: null, herkunft: null };
let chat = null;
/** Reiter-Steuerung — gesetzt in `start()`. */
let reiter = null;

// ── Widget laden ───────────────────────────────────────────────────

/** Der Fehlerweg des Bündel-Ladens: Kasten zeigen, Start sperren, und den
 *  Hol-Befehl mit DEM eingetragenen Backend anschreiben — ein Befehl zum
 *  Kopieren, der auf `localhost` zeigt, während oben etwas anderes steht,
 *  schickt genau in die Irre. */
function buendelFehlt() {
  $('holBefehl').textContent =
    `node scripts/fetch-widget.mjs ${apiBasis().basis || 'http://localhost:8000'}`;
  $('bundleFehlt').hidden = false;
  $('starten').disabled = true;
}

// ── Formular ───────────────────────────────────────────────────────

function modus() {
  return document.querySelector('input[name="modus"]:checked').value;
}

/** Der Kontext, wie er gerade eingestellt ist. */
function aktuellerKontext() {
  return baueKontext({
    modus: modus(),
    art: $('art').value,
    collectionId: $('collectionId').value,
    topicSlug: $('topicSlug').value,
    nodeId: $('nodeId').value,
    suche: $('suche').value,
    tabUrl: tab.url,
    tabTitel: tab.titel,
    seitentext: $('textMit').checked ? tab.text : '',
  });
}

/** Den Schema-Stand prüfen UND anzeigen. Das Urteil kommt aus `pruefeSchema`,
 *  damit die Anzeige und die Startsperre dieselbe Aussage machen — vorher
 *  konnten sie auseinanderlaufen. */
function zeigeSchemaStand() {
  const stand = pruefeSchema($('schema').value);
  const status = $('schemaStatus');
  status.textContent = stand.text;
  status.classList.toggle('fehler', !stand.gueltig);
  return stand;
}

/** Sichtbarkeit nachziehen: Betriebsart, die Felder der gewählten Art, Vorschau. */
function zeichneNeu() {
  const m = modus();
  $('autoBlock').hidden = m !== 'auto';
  $('manuellBlock').hidden = m !== 'manuell';
  $('modusHinweis').textContent = {
    auto: 'Aus der Adresse des Tabs. In der Seitenleiste erkennt das Widget selbst '
      + 'nichts — sie zeigt eine fremde Seite an, ohne dorthin zu navigieren.',
    manuell: 'Nur die Felder unten. Der Tab bleibt außen vor.',
    aus: 'Gar kein Kontext. Die ehrliche Vergleichsgröße: so sieht es aus, wenn der '
      + 'Bot nichts über die Seite weiß.',
  }[m];

  const art = $('art').value;
  for (const feld of document.querySelectorAll('#manuellBlock [data-fuer]')) {
    feld.hidden = !feld.dataset.fuer.split(' ').includes(art);
  }

  $('kontextVorschau').textContent = JSON.stringify(aktuellerKontext(), null, 2);
  zeigeSchemaStand();
}

// ── Tab auslesen ───────────────────────────────────────────────────

/** Adresse/Titel/Text des Tabs in die Anzeige holen. Die Berechtigungs-Logik
 *  liegt in `tab-lesen.js`; hier bleibt nur, was daraus sichtbar wird. */
async function tabLesen() {
  const knopf = $('tabLesen');
  const anzeige = $('tabAnzeige');
  knopf.disabled = true;
  anzeige.classList.remove('fehler');
  $('tabErlauben').hidden = true;
  try {
    const gelesen = await liesTab({ textGewuenscht: $('textMit').checked });
    // Alle fünf Felder aus EINEM Lesevorgang: Adresse, Titel und Text müssen
    // vom selben Tab stammen, und `tabId`/`herkunft` sorgen dafür, dass auch
    // ein späterer Erlauben-Klick genau diesen Tab meint.
    tab = {
      url: gelesen.url, titel: gelesen.titel, text: gelesen.text,
      tabId: gelesen.tabId, herkunft: gelesen.herkunft,
    };
    anzeige.textContent = tab.url
      ? `${tab.titel || '(ohne Titel)'} — ${tab.url}`
      : 'Der Tab gibt keine Adresse her.';
    zeigeTextZustand(gelesen);
  } catch (err) {
    anzeige.textContent = `Tab nicht lesbar: ${err.message}`;
    anzeige.classList.add('fehler');
  } finally {
    knopf.disabled = false;
    zeichneNeu();
  }
}

/** Was aus dem Zustand des Textabrufs auf dem Bildschirm wird. */
function zeigeTextZustand({ zustand, text, url }) {
  const laenge = $('textLaenge');
  const erlauben = $('tabErlauben');
  if (zustand === 'gelesen') { laenge.textContent = `${text.length} Zeichen gelesen`; return; }
  if (zustand === 'ohne-text') { laenge.textContent = ''; return; }
  if (zustand === 'intern') {
    laenge.textContent = 'Interne Seite — Chrome lässt hier keinen Zugriff zu.';
    return;
  }
  // braucht-erlaubnis: eigener Knopf, weil `permissions.request` eine eigene
  // Nutzergeste verlangt (Begründung im Kopf von `tab-lesen.js`).
  laenge.textContent = '';
  $('tabAnzeige').textContent += ' — Seitentext braucht noch eine Erlaubnis.';
  erlauben.textContent = `Zugriff auf ${new URL(url).host} erlauben`;
  erlauben.hidden = false;
}

/** Eigene Nutzergeste für `permissions.request`. Herkunft und Tab-Kennung
 *  kommen aus `tab`, nicht aus einem `dataset` am Knopf: eine Quelle für den
 *  Zustand, und der Text landet damit garantiert beim selben Tab wie die
 *  Adresse, die oben steht. */
async function tabErlauben() {
  const knopf = $('tabErlauben');
  knopf.disabled = true;
  try {
    const { text, zustand } = await erlaubeUndLies(tab.herkunft, tab.tabId);
    if (zustand === 'abgelehnt') {
      $('textLaenge').textContent = 'Ohne Erlaubnis kein Seitentext.';
      return;
    }
    tab.text = text;
    knopf.hidden = true;
    $('textLaenge').textContent = `${text.length} Zeichen gelesen`;
  } catch (err) {
    $('textLaenge').textContent = `Seitentext nicht lesbar: ${err.message}`;
  } finally {
    knopf.disabled = false;
    zeichneNeu();
  }
}

// ── Starten ────────────────────────────────────────────────────────

/** Das Element neu aufbauen. Attribute wie `result-schema` liest die Hülle
 *  zwar auch zur Laufzeit, aber `api-url` und die Sitzung nicht — und ein
 *  Versuchsaufbau, bei dem der halbe Zustand von vorhin überlebt, misst das
 *  Falsche.
 *
 *  Aus demselben Grund gehen die Ergebnisse des vorigen Laufs mit: sie standen
 *  sonst unter einem anderen Schema in derselben Liste, und die Zählung lief
 *  weiter („Zug 5" über der ersten Antwort). */
function baueChat(schema) {
  $('chatHalter').replaceChildren();
  leereErgebnisse($);
  chat = document.createElement('boerdi-chat');
  chat.setAttribute('api-url', apiBasis().basis);
  chat.setAttribute('embed-mode', 'frameless');
  chat.setAttribute('engine', 'agent');
  chat.setAttribute('theme', 'auto');
  // Die eigene Erkennung hat in einer Seitenleiste nichts zu erkennen: die
  // Adresse ist `chrome-extension://…` und ändert sich nie. Wir geben den
  // Kontext selbst mit.
  chat.setAttribute('auto-context', 'false');
  // Kein „Hey, schön dass du da bist!" und keine vier Einstiegs-Chips: hier
  // steht der Auftrag schon im Feld nebenan, und der erste Zug geht sofort
  // hinaus. Eine Begrüßung wäre eine Nachricht, die niemand gelesen hat, bevor
  // die Antwort sie wegschiebt.
  chat.setAttribute('show-welcome', 'false');
  if (schema) chat.setAttribute('result-schema', JSON.stringify(schema));
  $('chatHalter').append(chat);
  return chat;
}

/**
 * Zugriff auf das eingetragene Backend sicherstellen.
 *
 * `host_permissions` im Manifest deckt nur `localhost` — jede andere Adresse
 * (ein Staging-Server, eine `nip.io`-Adresse) liefe sonst in einen
 * CORS-Fehler, der in der Konsole der Seitenleiste steht und sonst nirgends.
 * Statt das Manifest auf `<all_urls>` aufzureißen, wird die Erlaubnis für
 * **genau diese eine Herkunft** erfragt.
 *
 * MUSS aus der Nutzergeste heraus laufen: deshalb der erste `await` im
 * Klick-Griff, vor allem anderen.
 *
 * Meldet nichts selbst — der Aufrufer weiß, wohin die Meldung gehört. Vorher
 * schrieb sie in `#schemaStatus` und überschrieb dort das Schema-Urteil, das
 * mit dem Netz nichts zu tun hat.
 *
 * @returns {Promise<boolean>} `true` auch bei unbrauchbarer Adresse: dort ist
 *   nichts zu erlauben, und den Fehler meldet der Gesundheits-Abruf klarer.
 */
async function sichereZugriff(apiUrl) {
  let herkunft;
  try {
    herkunft = `${new URL(apiUrl).origin}/*`;
  } catch {
    return true;
  }
  if (await chrome.permissions.contains({ origins: [herkunft] })) return true;
  return chrome.permissions.request({ origins: [herkunft] });
}

/**
 * „Verbindung prüfen" — `GET {basis}/api/health`, bevor irgendein Zug läuft.
 *
 * Der Grund, aus dem es diesen Knopf gibt (live 2026-08-14): eine falsche
 * Backend-Adresse äußerte sich erst dreißig Sekunden später als „Entschuldigung,
 * es ist ein Fehler aufgetreten" — ein Satz, der über die Ursache nichts sagt.
 * Hier steht sie sofort, samt Repositorium: dass der Bot gegen Produktion statt
 * Staging läuft, merkt man sonst erst am Ziel eines Karten-Links.
 */
async function backendPruefen() {
  const knopf = $('backendPruefen');
  const status = $('backendStatus');
  const eingabe = apiBasis();
  const { basis } = eingabe;
  // Der Korrektur-Hinweis wird dem Ergebnis VORANGESTELLT statt von ihm
  // ersetzt: er ist der eigentliche Befund, das Gesundheits-Ergebnis nur die
  // Folge davon. Ein grünes „ok" allein ließe das falsche Feld stehen.
  const vorspann = korrekturVorspann(eingabe);
  knopf.disabled = true;
  status.classList.toggle('fehler', !!vorspann);
  status.textContent = `${vorspann}Frage ${basis}/api/health …`;
  try {
    if (!await sichereZugriff(basis)) {
      status.textContent = `${vorspann}Kein Zugriff auf ${basis} erteilt.`;
      status.classList.add('fehler');
      return;
    }
    const { ok, text } = await pruefeGesundheit(basis);
    status.textContent = vorspann + text;
    status.classList.toggle('fehler', !ok || !!vorspann);
  } finally {
    knopf.disabled = false;
  }
}

async function starten() {
  const stand = zeigeSchemaStand();
  const auftrag = $('auftrag').value.trim();
  const knopf = $('starten');
  const eingabe = apiBasis();
  knopf.disabled = true;
  try {
    // Ein Tippfehler im Schema darf keinen vollen Agent-Zug kosten (bis 12
    // Runden, 90 s Frist), der garantiert kein Ergebnis liefern kann. Das
    // LEERE Feld ist davon nicht betroffen — es ist ein gültiger Start.
    if (!stand.gueltig) {
      // „Nicht gestartet" ausdrücklich davor: ein Knopfdruck, nach dem sich
      // sichtbar nichts tut, ist sonst nicht von einem hängenden Zug zu
      // unterscheiden.
      $('schemaStatus').textContent = `Nicht gestartet — ${stand.text}`;
      $('schema').focus();
      return;
    }
    if (!await sichereZugriff(eingabe.basis)) {
      $('backendStatus').textContent =
        `Ohne Zugriff auf ${eingabe.basis} kann die Leiste das Backend nicht erreichen.`;
      $('backendStatus').classList.add('fehler');
      return;
    }
    // Wenn die Adresse korrigiert wurde, sagt es die Leiste auch hier — der
    // Zug läuft, aber das Feld oben bleibt sonst falsch stehen.
    if (eingabe.korrigiert) {
      $('backendStatus').textContent = korrekturVorspann(eingabe).trim();
      $('backendStatus').classList.add('fehler');
    }
    baueChat(stand.schema);
    await customElements.whenDefined('boerdi-chat');
    await new Promise(requestAnimationFrame);   // eine Runde für das Aufwerten

    reiter?.zeige(1);   // in den Chat wechseln, sonst laeuft der Zug unsichtbar

    const ctx = aktuellerKontext();
    if (Object.keys(ctx).length) chat.replaceContext(ctx);
    if (auftrag) chat.startTask(auftrag);
  } finally {
    knopf.disabled = false;
  }
}

// ── Aufbau ─────────────────────────────────────────────────────────

/** Kurzform — der Speicher-Weg liegt in `einstellungen.js`. */
const merke = () => merkeEinstellungen($, modus());

/**
 * Tastendruck-getriebene Aktualisierungen bündeln.
 *
 * `zeichneNeu` schreibt in `#schemaStatus`, und das ist ein `role="status"` —
 * ein Live-Bereich. Ohne Entprellung liest ein Screenreader nach JEDEM Zeichen
 * „Kein gültiges JSON: Unexpected end of JSON input" vor, solange man tippt.
 * Eine knappe Ruhepause ist zugleich der Moment, ab dem die Meldung überhaupt
 * stimmt. Klicks und Auswahlen bleiben sofort — dort gibt es keine Zwischen-
 * zustände zu vertonen.
 */
function entprellt(fn, ms = 400) {
  let uhr = null;
  return (...args) => {
    clearTimeout(uhr);
    uhr = setTimeout(() => fn(...args), ms);
  };
}

function fuelleVorlagen() {
  const w = $('vorlage');
  w.append(new Option('— eigene —', ''));
  for (const v of VORLAGEN) w.append(new Option(v.name, v.id));
}

function uebernimmVorlage() {
  const v = vorlage($('vorlage').value);
  if (!v) return;
  $('auftrag').value = v.auftrag;
  $('schema').value = JSON.stringify(v.schema, null, 2);
  zeichneNeu();
  merke();
}

async function start() {
  fuelleVorlagen();
  await ladeEinstellungen($);

  for (const el of document.querySelectorAll('input[name="modus"]')) {
    el.addEventListener('change', () => { zeichneNeu(); merke(); });
  }
  const beimTippen = entprellt(() => { zeichneNeu(); merke(); });
  for (const id of GEMERKTE_FELDER) {
    $(id).addEventListener('input', beimTippen);
  }
  $('art').addEventListener('change', () => { zeichneNeu(); merke(); });
  $('textMit').addEventListener('change', () => { zeichneNeu(); merke(); });
  $('vorlage').addEventListener('change', uebernimmVorlage);
  $('tabLesen').addEventListener('click', tabLesen);
  $('tabErlauben').addEventListener('click', tabErlauben);
  $('starten').addEventListener('click', starten);
  $('backendPruefen').addEventListener('click', backendPruefen);
  // Nach dem Holen noch einmal versuchen, statt die Erweiterung neu zu laden.
  // Ein zweiter <script>-Tag holt die Datei frisch; klappt es weiterhin nicht,
  // sagt der Kasten es wieder — und dann hilft nur „Neu laden".
  $('erneutLaden').addEventListener('click', async () => {
    $('bundleFehlt').hidden = true;
    if (await ladeBuendel(buendelFehlt)) $('starten').disabled = false;
  });

  // Neu zuerst; auf `badboerdi:agent-result` NICHT hören, sonst zählt jeder
  // Zug doppelt (der Doppelversand läuft, solange der ALTE Chatbot lebt).
  window.addEventListener('boerdi:agent-result', (e) => zeigeErgebnis($, e.detail));

  reiter = verdrahteReiter([
    { knopf: $('reiterEinstellungen'), feld: $('feldEinstellungen') },
    { knopf: $('reiterChat'), feld: $('feldChat') },
  ]);

  zeichneNeu();
  await ladeBuendel(buendelFehlt);
}

start().catch((err) => {
  // NICHT den Bündel-Kasten zeigen: hierher führt auch eine kaputte Kennung
  // oder ein blockierter Speicher, und eine falsche Diagnose kostet mehr Zeit
  // als gar keine. Der echte Grund steht dort, wo man ihn sucht.
  console.error('Seitenleiste nicht gestartet:', err);
  const status = $('backendStatus');
  if (status) {
    status.textContent = `Die Leiste ist nicht vollständig gestartet: ${err.message}`;
    status.classList.add('fehler');
  }
});
