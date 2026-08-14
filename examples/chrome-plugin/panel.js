/**
 * Die Verdrahtung der Seitenleiste: Steuerung → Widget → Ergebnis.
 *
 * Der ganze Umgang mit dem Chat besteht aus vier Zeilen der öffentlichen API
 * (`replaceContext`, `startTask`) plus einem Zuhörer auf `boerdi:agent-result`.
 * Alles andere hier ist Formular.
 *
 * **Warum das Bündel aus `vendor/` kommt.** Manifest V3 verbietet nachgeladenen
 * Code; `<script src="https://backend/widget/…">` ist auf einer
 * Erweiterungs-Seite gesperrt. Das Bündel muss also im Ordner liegen —
 * `node scripts/fetch-widget.mjs <backend>` holt es.
 */
import { baueKontext } from './context.js';
import { GEMERKTE_FELDER, ladeEinstellungen, merkeEinstellungen } from './einstellungen.js';
import { VORLAGEN, vorlage } from './schemas.js';

const $ = (id) => document.getElementById(id);

/** Was der letzte „Aus dem Tab übernehmen"-Klick ergeben hat. */
let tab = { url: '', titel: '', text: '' };
let chat = null;

// ── Widget laden ───────────────────────────────────────────────────

/** Wie lange auf die Element-Definition gewartet wird, bevor die Leiste es
 *  sagt. Ein Bündel, das lädt aber nichts definiert, hinge sonst ewig — und
 *  ein ewiges Warten sieht aus wie ein langsames Netz, nicht wie ein Fehler. */
const DEFINITIONS_FRIST_MS = 10000;

/** Das Bündel einhängen. Fehlt es, sagt die Leiste es — statt ein leeres
 *  `<boerdi-chat>` zu zeigen, das nie etwas tut.
 *
 *  **Ein gewöhnlicher `<script>`-Tag, kein `import()`.** Das Bündel ist ein
 *  klassisches Skript (so binden es die Demo-Seiten und jede Gastseite ein,
 *  `<script src="/widget/boerdi-widget.js" defer>`); als ES-Modul geladen
 *  gälten andere Regeln. `onerror` erkennt zugleich die fehlende Datei — ein
 *  Mechanismus statt zweier. */
function ladeBuendel() {
  const scheitern = (grund) => {
    console.error('Widget-Bündel:', grund);
    $('bundleFehlt').hidden = false;
    $('starten').disabled = true;
    return false;
  };
  return new Promise((fertig) => {
    const s = document.createElement('script');
    s.src = chrome.runtime.getURL('vendor/boerdi-widget.js');
    s.onerror = () => fertig(scheitern('vendor/boerdi-widget.js nicht ladbar'));
    s.onload = () => {
      const frist = new Promise((_, ab) =>
        setTimeout(() => ab(new Error('kein <boerdi-chat> definiert')), DEFINITIONS_FRIST_MS));
      Promise.race([customElements.whenDefined('boerdi-chat'), frist])
        .then(() => fertig(true))
        .catch((err) => fertig(scheitern(err.message)));
    };
    document.head.append(s);
  });
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

/** Das Schema, oder `null`. Zeigt an, was es geworden ist — ein kaputtes
 *  Schema soll man SEHEN, bevor man startet, nicht erst am ausbleibenden
 *  Ergebnis merken. */
function aktuellesSchema() {
  const roh = $('schema').value.trim();
  const status = $('schemaStatus');
  status.classList.remove('fehler');
  if (!roh) {
    status.textContent = 'Kein Schema — der Chat läuft ohne strukturiertes Ergebnis.';
    return null;
  }
  let wert;
  try {
    wert = JSON.parse(roh);
  } catch (err) {
    status.textContent = `Kein gültiges JSON: ${err.message}`;
    status.classList.add('fehler');
    return null;
  }
  if (!wert || typeof wert !== 'object' || Array.isArray(wert)) {
    status.textContent = 'Ein JSON-Schema muss ein Objekt sein (kein Array, keine Zahl).';
    status.classList.add('fehler');
    return null;
  }
  const laenge = JSON.stringify(wert).length;
  if (laenge > 10000) {
    status.textContent = `${laenge} Zeichen — das Backend lehnt über 10 000 mit 422 ab.`;
    status.classList.add('fehler');
    return null;
  }
  status.textContent = `Gültig, ${laenge} Zeichen.`;
  return wert;
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
  aktuellesSchema();
}

// ── Tab auslesen ───────────────────────────────────────────────────

/** Adresse, Titel und (auf Wunsch) Text des aktiven Tabs holen.
 *
 *  Der Text wird bei 20 000 Zeichen gekappt — dieselbe Grenze, die der
 *  Agent-Endpunkt für `instruction` setzt. Ungekappt wäre der häufigste Grund
 *  für ein 422, und ein abgewiesener Zug sagt weniger als ein gekürzter. */
async function tabLesen() {
  const knopf = $('tabLesen');
  knopf.disabled = true;
  try {
    const [aktiv] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!aktiv) throw new Error('kein aktiver Tab');
    tab = { url: aktiv.url || '', titel: aktiv.title || '', text: '' };

    if ($('textMit').checked && aktiv.id != null) {
      const [treffer] = await chrome.scripting.executeScript({
        target: { tabId: aktiv.id },
        func: () => document.body?.innerText || '',
      });
      tab.text = String(treffer?.result || '').slice(0, 20000);
    }

    $('tabAnzeige').textContent = tab.url
      ? `${tab.titel || '(ohne Titel)'} — ${tab.url}`
      : 'Der Tab gibt keine Adresse her.';
    $('textLaenge').textContent = tab.text ? `${tab.text.length} Zeichen gelesen` : '';
  } catch (err) {
    // Bei internen Seiten (chrome://, Web Store) verweigert Chrome das Einspritzen.
    // Das ist kein Fehler des Beispiels, aber man muss es sehen.
    $('tabAnzeige').textContent = `Tab nicht lesbar: ${err.message}`;
    $('tabAnzeige').classList.add('fehler');
  } finally {
    knopf.disabled = false;
    zeichneNeu();
  }
}

// ── Ergebnis anzeigen ──────────────────────────────────────────────

let zaehler = 0;

function zeigeErgebnis({ result, stop_reason: grund }) {
  $('ergebnisLeer').hidden = true;
  const li = document.createElement('li');

  const kopf = document.createElement('div');
  kopf.className = 'kopf';
  const marke = document.createElement('span');
  marke.className = `marke ${result ? 'gut' : 'leer'}`;
  marke.textContent = grund || '—';
  kopf.append(marke, `Zug ${++zaehler}`);

  const pre = document.createElement('pre');
  pre.textContent = result
    ? JSON.stringify(result, null, 2)
    : 'kein Ergebnis in diesem Zug — der Grund steht links';

  li.append(kopf, pre);
  $('ergebnisListe').prepend(li);   // neuestes oben, ohne Scrollen
}

// ── Starten ────────────────────────────────────────────────────────

/** Das Element neu aufbauen. Attribute wie `result-schema` liest die Hülle
 *  zwar auch zur Laufzeit, aber `api-url` und die Sitzung nicht — und ein
 *  Versuchsaufbau, bei dem der halbe Zustand von vorhin überlebt, misst das
 *  Falsche. */
function baueChat(schema) {
  $('chatHalter').replaceChildren();
  chat = document.createElement('boerdi-chat');
  chat.setAttribute('api-url', $('apiUrl').value.trim());
  chat.setAttribute('embed-mode', 'frameless');
  chat.setAttribute('engine', 'agent');
  chat.setAttribute('theme', 'auto');
  // Die eigene Erkennung hat in einer Seitenleiste nichts zu erkennen: die
  // Adresse ist `chrome-extension://…` und ändert sich nie. Wir geben den
  // Kontext selbst mit.
  chat.setAttribute('auto-context', 'false');
  if (schema) chat.setAttribute('result-schema', JSON.stringify(schema));
  $('chatHalter').append(chat);
  return chat;
}

async function starten() {
  const schema = aktuellesSchema();
  const auftrag = $('auftrag').value.trim();
  const knopf = $('starten');
  knopf.disabled = true;
  try {
    baueChat(schema);
    await customElements.whenDefined('boerdi-chat');
    await new Promise(requestAnimationFrame);   // eine Runde für das Aufwerten

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
  for (const id of GEMERKTE_FELDER) {
    $(id).addEventListener('input', () => { zeichneNeu(); merke(); });
  }
  $('art').addEventListener('change', () => { zeichneNeu(); merke(); });
  $('textMit').addEventListener('change', () => { zeichneNeu(); merke(); });
  $('vorlage').addEventListener('change', uebernimmVorlage);
  $('tabLesen').addEventListener('click', tabLesen);
  $('starten').addEventListener('click', starten);

  // Neu zuerst; auf `badboerdi:agent-result` NICHT hören, sonst zählt jeder
  // Zug doppelt (der Doppelversand läuft, solange der ALTE Chatbot lebt).
  window.addEventListener('boerdi:agent-result', (e) => zeigeErgebnis(e.detail));

  zeichneNeu();
  await ladeBuendel();
}

start().catch((err) => {
  console.error('Seitenleiste nicht gestartet:', err);
  $('bundleFehlt').hidden = false;
});
