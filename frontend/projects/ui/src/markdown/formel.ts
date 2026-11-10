/**
 * Formeln im Widget (Plan 2026-11-10, TB-E4, Nutzer-Entscheid N5): LaTeX in `\( … \)`, `\[ … \]`,
 * `$$ … $$` und `$ … $` wird MathML, das der Browser selbst zeichnet.
 *
 * Bewusst eine kleine eigene Umwandlung der häufigen Formen (Potenz, Index, Bruch, Wurzel, Pfeile,
 * Relationen, griechische Buchstaben, Text): fertige Bibliotheken (KaTeX, temml) brächten mehr als
 * das ganze Budget des Bündels mit, KaTeX dazu Schriftdateien. Keine Netzquelle (DSGVO).
 *
 * Sicherheit (Review TB-E4, zwei CRITICAL): jedes Zeichen aus dem LaTeX wird maskiert; Markup
 * entsteht nur aus den festen Tags hier. Eingesetzt wird NACH DOMPurify und **im DOM**, nie per
 * String-Ersatz: :func:`formelnEinsetzen` setzt MathML nur in Textknoten (nicht in `code`/`pre`), in
 * Attributen steht der LaTeX-Quelltext, URL-Attribute mit Platzhalter fallen weg. Der Platzhalter
 * trägt einen Zufallswert je Render — ein vom Modell getippter trifft nie und wird nie geleert
 * (sonst wurde aus `java@@…@@script:` nach DOMPurify ein `javascript:`). DOMPurify bekommt kein
 * MathML-Profil: rohes `<math href=…>` aus dem Modelltext bleibt verboten. Unbekannte Befehle
 * bleiben als Text lesbar (`<mtext>\befehl</mtext>`), kaputte Klammern beenden nur die Gruppe.
 */

export interface Formel {
  readonly tex: string;
  readonly abgesetzt: boolean;
  /** Der ganze Fund samt Begrenzern — steht in Code und in Attributen statt der Formel. */
  readonly quelle: string;
}

/** Ein Zufallswert je Render (Review TB-E4, CRITICAL 1): das Modell kennt ihn nicht. */
export function formelNonce(): string {
  const roh = globalThis.crypto?.randomUUID?.() ?? `${Math.random()}${Date.now()}`;
  return roh.replace(/[^a-z0-9]/gi, '').slice(0, 16);
}

const _platzhalter = (nonce: string, i: number): string => `@@FORMEL-${nonce}-${i}@@`;

// Code zuerst (bleibt unberührt): Zäune ``` und ~~~, Code-Spans mit einem oder mehr Backticks.
// Dann \[…\], $$…$$, \(…\), $…$ — nie über einen Absatz (`\n\n`). Ein `$` gilt nur ohne Leerraum
// direkt daran, ohne folgende Ziffer oder Wortzeichen („$5 und $10“, „$PATH:$HOME“ bleiben Text).
const _MUSTER = new RegExp([
  '(```[\\s\\S]*?```|~~~[\\s\\S]*?~~~|(`+)[^`][\\s\\S]*?\\2)',
  '\\\\\\[((?:(?!\\n\\n)[\\s\\S])+?)\\\\\\]',
  '\\$\\$((?:(?!\\n\\n)[\\s\\S])+?)\\$\\$',
  '\\\\\\(((?:(?!\\n\\n)[\\s\\S])+?)\\\\\\)',
  '\\$(?=\\S)([^$\\n]+?)(?<=\\S)\\$(?![\\w$])',
].join('|'), 'g');

/** Review TB-E4, Befund 5: `\[…\]` ist in Markdown oft nur eine maskierte Klammer („\[1\]“) —
 *  als Formel nur mit LaTeX-typischem Inhalt. */
const _LATEXARTIG = /[\\^_=]/;

/** Formeln aus dem Markdown nehmen; an ihrer Stelle steht ein Platzhalter mit `nonce`. */
export function formelnHerausnehmen(md: string, nonce = formelNonce()
): { text: string; formeln: Formel[] } {
  const formeln: Formel[] = [];
  const text = md.replace(_MUSTER, (ganz, code, _ticks, block, doppel, inline, dollar) => {
    if (code !== undefined) return ganz;
    const tex = (block ?? doppel ?? inline ?? dollar ?? '').trim();
    if (!tex || (block !== undefined && !_LATEXARTIG.test(tex))) return ganz;
    formeln.push({ tex, abgesetzt: block !== undefined || doppel !== undefined, quelle: ganz });
    return _platzhalter(nonce, formeln.length - 1);
  });
  return { text, formeln };
}

/** Attribute, die eine Adresse tragen — mit einem Platzhalter fallen sie ganz weg. */
const _URL_ATTRIBUTE = new Set(['href', 'src', 'xlink:href', 'action', 'formaction', 'srcset',
  'poster', 'cite', 'background', 'data']);

/** Die Formeln im bereinigten HTML einsetzen — im DOM (Review TB-E4, CRITICAL 1–2):
 *  - Textknoten außerhalb von `code`/`pre`: das MathML aus :func:`texZuMathml`;
 *  - Textknoten in `code`/`pre`: der LaTeX-Quelltext;
 *  - Attribute: der Quelltext; URL-Attribute fallen weg.
 *  Ein Platzhalter mit anderem Zufallswert bleibt als Text stehen. */
export function formelnEinsetzen(html: string, formeln: readonly Formel[], nonce: string): string {
  const kennung = `@@FORMEL-${nonce}-`;
  if (!formeln.length || !html.includes(kennung)) return html;
  const muster = new RegExp(`@@FORMEL-${nonce}-(\\d+)@@`, 'g');
  const quelle = (wert: string): string =>
    wert.replace(muster, (m, i: string) => formeln[Number(i)]?.quelle ?? m);
  const tpl = document.createElement('template');
  tpl.innerHTML = html;
  for (const el of Array.from(tpl.content.querySelectorAll('*'))) {
    for (const attr of Array.from(el.attributes)) {
      if (!attr.value.includes(kennung)) continue;
      if (_URL_ATTRIBUTE.has(attr.name.toLowerCase())) el.removeAttribute(attr.name);
      else el.setAttribute(attr.name, quelle(attr.value));
    }
  }
  const gang = document.createTreeWalker(tpl.content, NodeFilter.SHOW_TEXT);
  const texte: Text[] = [];
  while (gang.nextNode()) texte.push(gang.currentNode as Text);
  for (const t of texte) {
    if (!t.data.includes(kennung)) continue;
    if (t.parentElement?.closest('code, pre')) {
      t.data = quelle(t.data);
      continue;
    }
    const stueck = document.createDocumentFragment();
    let pos = 0;
    for (const m of t.data.matchAll(muster)) {
      stueck.append(t.data.slice(pos, m.index));
      const formel = formeln[Number(m[1])];
      if (formel) {
        const mathe = document.createElement('template');
        mathe.innerHTML = texZuMathml(formel.tex, formel.abgesetzt);
        stueck.append(mathe.content);
      } else {
        stueck.append(m[0]);
      }
      pos = (m.index ?? 0) + m[0].length;
    }
    stueck.append(t.data.slice(pos));
    t.replaceWith(stueck);
  }
  return tpl.innerHTML;
}

const _GRIECHISCH: Record<string, string> = {
  alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε', varepsilon: 'ε', zeta: 'ζ',
  eta: 'η', theta: 'θ', vartheta: 'ϑ', iota: 'ι', kappa: 'κ', lambda: 'λ', mu: 'μ', nu: 'ν',
  xi: 'ξ', pi: 'π', rho: 'ρ', sigma: 'σ', tau: 'τ', upsilon: 'υ', phi: 'φ', varphi: 'φ',
  chi: 'χ', psi: 'ψ', omega: 'ω', Gamma: 'Γ', Delta: 'Δ', Theta: 'Θ', Lambda: 'Λ', Xi: 'Ξ',
  Pi: 'Π', Sigma: 'Σ', Phi: 'Φ', Psi: 'Ψ', Omega: 'Ω', infty: '∞', partial: '∂', nabla: '∇',
  emptyset: '∅',
};

const _OPERATOREN: Record<string, string> = {
  cdot: '·', times: '×', div: '÷', pm: '±', mp: '∓', leq: '≤', le: '≤', geq: '≥', ge: '≥',
  neq: '≠', ne: '≠', approx: '≈', equiv: '≡', sim: '∼', propto: '∝', to: '→',
  rightarrow: '→', leftarrow: '←', Rightarrow: '⇒', Leftarrow: '⇐', Leftrightarrow: '⇔',
  leftrightarrow: '↔', mapsto: '↦', sum: '∑', prod: '∏', int: '∫', oint: '∮', cdots: '⋯',
  ldots: '…', dots: '…', in: '∈', notin: '∉', subset: '⊂', subseteq: '⊆', cup: '∪', cap: '∩',
  forall: '∀', exists: '∃', angle: '∠', perp: '⊥', parallel: '∥', circ: '∘', degree: '°',
  ast: '∗', star: '⋆', '%': '%', '{': '{', '}': '}', '|': '‖', '#': '#', '&': '&', $: '$',
  lbrace: '{', rbrace: '}', langle: '⟨', rangle: '⟩', vert: '|',
};

const _FUNKTIONEN = new Set(['sin', 'cos', 'tan', 'cot', 'arcsin', 'arccos', 'arctan', 'sinh',
  'cosh', 'tanh', 'log', 'ln', 'lg', 'exp', 'lim', 'max', 'min', 'sup', 'inf', 'det', 'gcd']);

// `\\` (Zeilenumbruch) wird ein Abstand — sonst stünde es sichtbar da (Review TB-E4, Befund 8).
const _ABSTAENDE = new Set([',', ';', ':', '!', ' ', '\\', 'quad', 'qquad']);
const _TEXTBEFEHLE = new Set(['text', 'mathrm', 'textrm', 'mbox', 'operatorname', 'textit',
  'textbf']);
const _DURCHREICHEN = new Set(['mathbf', 'mathit', 'boldsymbol', 'displaystyle', 'mathbb',
  'mathcal', 'mathsf']);
const _AKZENTE: Record<string, string> = { vec: '→', overline: '‾', bar: '‾', hat: '^',
  tilde: '~', dot: '˙' };

/** Nie mehr als so viele Zeichen und so tief — sonst bleibt das LaTeX als Text. */
const _MAX_ZEICHEN = 2000;
const _MAX_TIEFE = 40;

function _maske(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const _tag = (name: string, inhalt: string): string => `<${name}>${inhalt}</${name}>`;
const _reihe = (teile: string[]): string => (teile.length === 1 ? teile[0] : _tag('mrow', teile.join('')));

/** Ein Lesekopf über dem LaTeX — rekursiver Abstieg mit Tiefenbremse. */
class _Leser {
  private i = 0;
  private tiefe = 0;

  constructor(private readonly s: string) {}

  liste(ende?: string): string[] {
    const teile: string[] = [];
    while (this.i < this.s.length) {
      const c = this.s[this.i];
      if (ende && c === ende) { this.i++; break; }
      if (c === '}' && !ende) { this.i++; continue; }   // überzählige Klammer: übergehen
      if (/\s/.test(c)) { this.i++; continue; }
      if (c === '^' || c === '_') {
        this.i++;
        const basis = teile.pop() ?? '<mrow></mrow>';
        teile.push(this.skript(basis, c));
        continue;
      }
      const atom = this.atom();
      if (atom) teile.push(atom);
    }
    return teile;
  }

  private skript(basis: string, art: string): string {
    const erst = this.argument();
    if (this.s[this.i] === (art === '^' ? '_' : '^')) {
      this.i++;
      const zweit = this.argument();
      const [unten, oben] = art === '_' ? [erst, zweit] : [zweit, erst];
      return _tag('msubsup', basis + unten + oben);
    }
    return _tag(art === '^' ? 'msup' : 'msub', basis + erst);
  }

  /** Ein Argument: eine `{…}`-Gruppe oder ein einzelnes Atom; fehlt es, eine leere Zeile. */
  argument(): string {
    while (this.i < this.s.length && /\s/.test(this.s[this.i])) this.i++;
    if (this.i >= this.s.length) return '<mrow></mrow>';
    if (this.s[this.i] === '{') {
      this.i++;
      return this.gruppe();
    }
    return this.atom() || '<mrow></mrow>';
  }

  private gruppe(): string {
    if (++this.tiefe > _MAX_TIEFE) throw new Error('zu tief');
    const teile = this.liste('}');
    this.tiefe--;
    return teile.length ? _reihe(teile) : '<mrow></mrow>';
  }

  /** Roher Text bis zur passenden `}` (für `\text{…}`). */
  private roh(): string {
    while (this.i < this.s.length && /\s/.test(this.s[this.i])) this.i++;
    if (this.s[this.i] !== '{') return '';
    let tiefe = 0;
    const start = ++this.i;
    while (this.i < this.s.length) {
      const c = this.s[this.i++];
      if (c === '{') tiefe++;
      else if (c === '}' && tiefe-- === 0) return this.s.slice(start, this.i - 1);
    }
    return this.s.slice(start);
  }

  private atom(): string {
    const rest = this.s.slice(this.i);
    const zahl = /^\d+(?:[.,]\d+)?/.exec(rest);
    if (zahl) { this.i += zahl[0].length; return _tag('mn', zahl[0]); }
    // Review TB-E4, Befund 7: ein ganzes Zeichen, auch außerhalb der BMP (𝑥, Emoji)
    const c = String.fromCodePoint(this.s.codePointAt(this.i) ?? 0x20);
    if (c === '{') { this.i++; return this.gruppe(); }
    if (c === '\\') return this.befehl();
    this.i += c.length;
    if (/\p{L}/u.test(c)) return _tag('mi', _maske(c));
    return _tag('mo', _maske(c));
  }

  private befehl(): string {
    const name = /^\\([a-zA-Z]+|.)/.exec(this.s.slice(this.i))?.[1] ?? '';
    this.i += 1 + name.length;
    if (!name || _ABSTAENDE.has(name)) return '';
    if (name === 'frac' || name === 'dfrac' || name === 'tfrac') {
      return _tag('mfrac', this.argument() + this.argument());
    }
    if (name === 'sqrt') {
      if (this.s[this.i] === '[') {
        const ende = this.s.indexOf(']', this.i);
        const index = new _Leser(this.s.slice(this.i + 1, ende < 0 ? undefined : ende)).liste();
        this.i = ende < 0 ? this.s.length : ende + 1;
        return _tag('mroot', this.argument() + _reihe(index.length ? index : ['<mrow></mrow>']));
      }
      return _tag('msqrt', this.argument());
    }
    if (_TEXTBEFEHLE.has(name)) return _tag('mtext', _maske(this.roh()));
    if (_DURCHREICHEN.has(name)) return this.argument();
    if (name in _AKZENTE) {
      return `<mover accent="true">${this.argument()}<mo>${_AKZENTE[name]}</mo></mover>`;
    }
    if (name === 'left' || name === 'right') {
      while (this.i < this.s.length && /\s/.test(this.s[this.i])) this.i++;   // „\left (“
      const zeichen = this.s[this.i] === '\\' ? (this.atom()) : this.s[this.i++] ?? '';
      if (zeichen.startsWith('<')) return zeichen;
      return zeichen === '.' || !zeichen ? '' : _tag('mo', _maske(zeichen));
    }
    if (name in _GRIECHISCH) return _tag('mi', _GRIECHISCH[name]);
    if (name in _OPERATOREN) return _tag('mo', _maske(_OPERATOREN[name]));
    if (_FUNKTIONEN.has(name)) return _tag('mi', name);
    return _tag('mtext', _maske('\\' + name));
  }
}

/** Querschnitts-Review Gruppe E, Befund 5: eine Formel als lesbarer Text (zum Vorlesen) — Brüche
 *  als `a/b`, Wurzel als `√`, bekannte Zeichen aus denselben Tabellen, übrige Befehle beim Namen. */
export function texAlsText(tex: string): string {
  let text = tex;
  for (let i = 0; i < 5 && /\\[dt]?frac\s*\{/.test(text); i++) {
    text = text.replace(/\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, '$1/$2');
  }
  return text
    .replace(/\\sqrt\s*\{([^{}]*)\}/g, '√$1')
    .replace(/\\(?:text|mathrm|textrm|mbox|operatorname)\s*\{([^{}]*)\}/g, '$1')
    .replace(/\\([a-zA-Z]+)/g, (_m, name: string) =>
      _GRIECHISCH[name] ?? (_OPERATOREN[name] ? ` ${_OPERATOREN[name]} ` : undefined)
        ?? (_ABSTAENDE.has(name) ? ' ' : name))
    .replace(/\\[,;:! ]/g, ' ')
    .replace(/[{}]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Formeln in einem Text durch ihre Textfassung ersetzen (Vorlesen; ohne Markup). */
export function formelnAlsText(text: string): string {
  const { text: mitPlatzhaltern, formeln } = formelnHerausnehmen(text, 'text');
  return mitPlatzhaltern.replace(/@@FORMEL-text-(\d+)@@/g,
    (m, i: string) => (formeln[Number(i)] ? texAlsText(formeln[Number(i)].tex) : m));
}

/** LaTeX → `<math>`; misslingt es (zu lang, zu tief), steht das LaTeX als Text da. */
export function texZuMathml(tex: string, abgesetzt: boolean): string {
  const kopf = abgesetzt ? '<math display="block">' : '<math>';
  if (tex.length > _MAX_ZEICHEN) return `${kopf}<mtext>${_maske(tex)}</mtext></math>`;
  try {
    return `${kopf}${new _Leser(tex).liste().join('')}</math>`;
  } catch {
    return `${kopf}<mtext>${_maske(tex)}</mtext></math>`;
  }
}
