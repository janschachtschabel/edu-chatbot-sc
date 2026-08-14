/**
 * Deutscher Katalog — die Standardsprache und zugleich der Rückfall für jede
 * andere. Deshalb ist er **eingebaut** und wird nicht nachgeladen: eine fehlende
 * Netzantwort darf die Oberfläche nie textlos lassen.
 *
 * Schlüssel sind flach und nach Ort benannt (`widget.*` = Hülle des Custom
 * Elements). Sie wachsen mit den Scheiben C1-b2 bis C1-b4; der Entwurf steht in
 * `docs/plans/2026-08-02-c1-i18n.md`.
 *
 * Die Texte sind aus den Templates übernommen, ZEICHENGETREU — inklusive
 * „ (U+201E) mit schlichtem " als Gegenstück, Halbgeviertstrich und
 * Auslassungspunkten. Bestehende Tests prüfen sie wörtlich.
 */
import { Catalogue } from './dictionary';

export const DE: Catalogue = {
  // ── Hülle des Custom Elements (widget.component.html) ──────────────
  // ── EU-AI-Act Art. 50: die Kennzeichnung ────────────────────────────
  // Nutzer müssen erkennen KÖNNEN, dass sie mit einer KI sprechen — nicht nur
  // einmal beim Start, sondern an der Antwort selbst. Deshalb steht der Hinweis
  // unter JEDER Bot-Blase und nicht bloss in der Begrüssung: wer mitten im
  // Verlauf einsteigt oder zurückscrollt, sieht ihn trotzdem.
  'chat.aiGenerated': 'KI-generierte Antwort',
  'widget.open': 'Chat öffnen',
  'widget.close': 'Schließen',
  'widget.restart': 'Neuer Chat',

  /** U2a — der Knopf benennt das ZIEL, nicht den Ist-Zustand: „groß" allein
   *  ließe offen, ob das der aktuelle oder der kommende Zustand ist. */
  'widget.size.larger': 'Chat vergrößern',
  'widget.size.smaller': 'Chat verkleinern',

  /** aria-label des Eulen-Knopfs. NICHT dasselbe wie `TOUR_START_LABEL` —
   *  das ist ein Protokollwert gegen die deutschen Schnellantworten aus der
   *  Backend-Config und bleibt unübersetzt (siehe Entwurf, „Fund"). */
  'widget.tourStart': 'Web-Tour starten',
  'widget.tourHint': 'Klick mich — ich zeig dir die Seite',

  'widget.status.thinking': 'denkt nach …',
  'widget.status.speaking': 'spricht …',

  'widget.speech.on': 'Sprachausgabe an',
  'widget.speech.off': 'Sprachausgabe aus',
  'widget.debug.on': 'Debug an',
  'widget.debug.off': 'Debug aus',

  /** Zugänglicher Name des Sprach-Umschalters (C1-c). Er benennt die ZIEL-
   *  sprache, denn das ist, was der Knopf tut — nicht die aktive, die schon an
   *  der ganzen Oberfläche abzulesen ist. Ein Schlüssel je Ziel statt eines mit
   *  Platzhalter: „Auf Englisch umschalten" beugt im Deutschen den Sprachnamen,
   *  und die Zuordnung Ziel→Schlüssel bleibt eine Erlaubnisliste im Code —
   *  dasselbe Muster wie bei `formatPhaseLabel`. */
  'widget.language.toDe': 'Auf Deutsch umschalten',
  'widget.language.toEn': 'Auf Englisch umschalten',

  /** Lotsen-Banner. Bewusst zwei Schlüssel statt einem mit Platzhalter: das
   *  Ziel steht im Original fett (`<strong>`), und ein Platzhalter-Schlüssel
   *  müsste dafür Markup transportieren — mit einem Wert, der vom Bot kommt.
   *  So bringt außerdem jede Sprache ihre eigenen Anführungszeichen mit. */
  'widget.nav.askBefore': 'Soll ich dich zu „',
  'widget.nav.askAfter': '" bringen?',
  'widget.nav.confirm': 'Bring mich hin',
  'widget.nav.cancel': 'Hier bleiben',

  // ── Chat-Shell: Verlauf, Druckleisten, Eingabe-Footer ──────────────
  'chat.log': 'Chat-Verlauf',
  'chat.speak': 'Vorlesen',
  'chat.speakStop': 'Stop',
  'chat.record.start': 'Spracheingabe starten',
  'chat.record.stop': 'Aufnahme stoppen',
  'chat.send': 'Senden',
  'chat.hostTask': 'Auftrag der Seite',

  'chat.input.label': 'Nachricht an BOERDi',
  'chat.input.placeholder': 'Nachricht eingeben…',
  'chat.input.thinking': 'Boerdi denkt nach…',
  'chat.input.recording': 'Aufnahme läuft… Klicke Stop zum Beenden',

  'chat.print.learningPathTitle': 'Lernpfad als PDF drucken',
  'chat.print.learningPath': 'Lernpfad drucken / als PDF speichern',
  'chat.print.materialTitle': 'Material als PDF drucken',
  /** `{label}` ist der Canvas-Typ aus `print-gates` — dort noch deutsch
   *  hartkodiert, das räumt C1-b3 ab. Als Platzhalter, damit eine andere
   *  Sprache ihn auch woanders im Satz unterbringen kann. */
  'chat.print.canvas': '{label} drucken / als PDF speichern',
  /** Rückfall von `printableCanvasLabel`, wenn der Backend-Sentinel weder Typ
   *  noch Titel trägt. Typ und Titel selbst sind Backend-Daten und bleiben
   *  unübersetzt. */
  'chat.print.canvasFallback': 'Material',

  // ── Flache Card-Liste (card-list.component) ────────────────────────
  'cards.browse': 'Inhalte',
  'cards.learningPath': 'Lernpfad',
  'cards.topicPage': 'Themenseite',
  'cards.topicPageMore': 'Weitere Themenseiten anzeigen',
  'cards.topicTooltip.single': 'Themenseite öffnen',
  'cards.topicTooltip.more': 'Themenseite ({variant}) — weitere verfügbar',
  'cards.showContent': 'Inhalt anzeigen',
  // Skill-Hinweis an der Sammlungskachel. Getrennte Formen statt „1 Skill(s)",
  // wie schon bei ``cards.topicTooltip.*``.
  'cards.skills.one': '1 Skill freigegeben',
  'cards.skills.many': '{count} Skills freigegeben',
  'cards.pagination.count': '{visible} von {total} Ergebnissen',
  'cards.pagination.showMore': 'Mehr anzeigen',
  'cards.pagination.loadMore': 'Weitere laden',
  'cards.pagination.loading': 'Lade…',

  // ── Ergebnis-Boxen (result-groups.component) ───────────────────────
  'groups.topics': 'Themenseiten',
  'groups.collections': 'Sammlungen',
  'groups.materials': 'Ausgewählte Materialien',
  'groups.web': 'Webseiten-Inhalte',
  'groups.showContent': 'Inhalt von {title} im Chat anzeigen',
  'groups.webItem': '{title} (Webseite)',
  'groups.webItemUntitled': 'Webseite',
  'groups.cta.withTerm': 'Treffer zur Suche „{term}"',
  'groups.cta.all': 'Alle Treffer in der Suche',
  'groups.cta.sub': 'Alle passenden Materialien anzeigen',
  /** Tooltip derselben Box (C1-b3). Bewusst ZWEI ganze Sätze statt eines
   *  Präfixes plus angeklebtem Zusatz: eine andere Sprache stellt den Suchbegriff
   *  womöglich voran oder braucht eine andere Fügung. */
  'groups.ctaTooltip.all': 'Alle Treffer in der Suche anzeigen',
  'groups.ctaTooltip.withTerm': 'Alle Treffer in der Suche anzeigen zu „{term}"',

  // ── Themenseiten-Schwimmlinien (swimlanes.component) ───────────────
  'swimlanes.heading': '{heading} (Auszug)',
  'swimlanes.headingFallback': 'Inhalte',
  'swimlanes.cta.title': 'Zur vollständigen Themenseite: {title}',
  'swimlanes.cta.label': 'Zur Themenseite „{title}"',
  'swimlanes.cta.sub': 'Alle Inhalte auf der Themenseite ansehen',

  // ── Inline-Dokument-Box (inline-documents.component) ───────────────
  'inlineDoc.print': 'Als PDF drucken / speichern',

  /** Rückfall-Titel der Box, wenn das Backend keinen `title` liefert. Der
   *  Schlüsselrest ist der Backend-`kind` — so ist die Zuordnung ablesbar. */
  'inlineDoc.kind.lernpfad': 'Lernpfad',
  'inlineDoc.kind.ki_material': 'Material',
  'inlineDoc.kind.edit': 'Bearbeitete Version',
  'inlineDoc.kind.bericht': 'Bericht',
  'inlineDoc.kind.remix': 'Remix',
  'inlineDoc.kind.fallback': 'Inhalt',

  // ── Inhaltstypen (C1-b3) ───────────────────────────────────────────
  /** EIN Satz Schlüssel für zwei Verbraucher, weil beide denselben Begriff
   *  benennen: `card-utils.getContentTypeLabel` (Typzeile der Kachel) und die
   *  `@@ICON:…@@`-Labels des Markdown-Renderers (Tooltip am Inline-Treffer).
   *  Quelle der Namen ist das Backend (`_icon_name_for_card`).
   *
   *  NICHT dasselbe wie `cards.topicPage`/`cards.browse`: das sind Knopf-
   *  Beschriftungen. Gleicher Wortlaut auf Deutsch, aber eine Sprache darf den
   *  Knopf anders benennen als den Typ („Open topic page" vs. „Topic page"). */
  'contentType.topicPage': 'Themenseite',
  'contentType.collection': 'Sammlung',
  'contentType.video': 'Video',
  'contentType.worksheet': 'Arbeitsblatt',
  'contentType.interactive': 'Interaktiver Inhalt',
  'contentType.audio': 'Audio',
  'contentType.quiz': 'Quiz',
  'contentType.presentation': 'Präsentation',
  'contentType.exercise': 'Übung',
  'contentType.course': 'Kurs',
  'contentType.website': 'Webseite',
  'contentType.material': 'Material',
  /** Wenn die Karte gar keinen `learning_resource_type` mitbringt. */
  'contentType.fallback': 'Inhalt',

  // ── Lade-Phasen des Streams (phase-label) ──────────────────────────
  /** Der Schlüsselrest ist der SSE-`step` des Backends. Die Zuordnung bleibt
   *  eine Erlaubnisliste im Code: ein unbekannter Schritt muss `null` ergeben,
   *  sonst stünde der Schlüssel selbst als Ladehinweis in der Bubble. */
  'phase.connected': 'Verbinde …',
  'phase.safety_classify': 'Verstehe deine Anfrage …',
  'phase.context': 'Lade Sitzungs-Kontext …',
  'phase.policy': 'Prüfe Datenschutz …',
  'phase.pattern': 'Wähle die passende Antwort …',
  'phase.wlo_search': 'Durchsuche WLO-Inhalte …',
  'phase.topic_content': 'Lade Themenseiten-Inhalte …',
  'phase.response': 'Formuliere Antwort …',
  'phase.query_meta': 'Suchergebnisse zusammengestellt',
  /** Die beiden Schritte der Agent-Schleife (A6). Sie wechseln sich ab und sind
   *  im Agent-Modus das Einzige, was überhaupt Fortschritt zeigt. Bewusst OHNE
   *  Werkzeugnamen und ohne Richtungsangabe: ein Aufruf kann lesen oder eine
   *  Änderung vorbereiten, und beides zu unterscheiden ginge nur mit einer
   *  zweiten Werkzeugliste hier — die driftete gegen den Katalog des Backends. */
  'phase.agent_iteration': 'Überlege den nächsten Schritt …',
  'phase.agent_tool': 'Arbeite mit WLO-Inhalten …',

  // ── Link-Warnung (trusted-host + markdown-renderer) ────────────────
  /** Ein Schlüssel für beide Erzeuger: `externalLinkWarning` setzt ihn an
   *  Karten- und Themenseiten-Links, der Markdown-Renderer an Bot-Links im
   *  Fließtext. Getrennte Schlüssel hießen: derselbe Tooltip, zwei Wortlaute. */
  'link.external': 'Achtung! Externe URL.',

  // ── Schnellantwort-Chips (C1-b4) ───────────────────────────────────
  /** Rückfall, wenn das Backend im `__guide__|…`-Marker kein Label mitschickt.
   *  Bewusst NICHT mit `widget.nav.confirm` zusammengelegt, obwohl der Wortlaut
   *  gleich ist: dort beantwortet der Knopf eine gestellte Frage („Soll ich
   *  dich zu … bringen?"), hier steht der Chip für sich. Eine andere Sprache
   *  darf die Antwort kürzer fassen als den freistehenden Aufruf. */
  'chips.guideFallback': 'Bring mich hin',

  // ── Fehler-Bubbles des Bots (C1-b4) ────────────────────────────────
  /** `{title}` ist der Sammlungs-/Material-Titel aus der Karte, also
   *  Backend-Inhalt — er wandert unübersetzt durch den Platzhalter. Die
   *  geraden Anführungszeichen sind aus dem Original übernommen; eine andere
   *  Sprache darf hier ihre eigenen setzen. */
  'error.browseCollection': 'Ich konnte die Inhalte von "{title}" leider nicht laden. Versuch es nochmal!',
  'error.contentText': 'Den Inhalt von "{title}" konnte ich leider nicht laden. Versuch es nochmal!',
  'error.learningPath': 'Den Lernpfad für "{title}" konnte ich leider nicht erstellen. Versuch es nochmal!',
  'error.tourStart': 'Entschuldigung, die Tour konnte gerade nicht gestartet werden. Bitte versuch es nochmal.',
  'error.transcription': 'Spracheingabe konnte nicht verarbeitet werden. Bitte tippe deine Nachricht.',
  'error.generic': 'Entschuldigung, es ist ein Fehler aufgetreten. Bitte versuche es erneut.',
  /** B10: der Stream wird 100 s lang nicht fertig. */
  'error.stale': 'Das dauert gerade ungewöhnlich lange — bitte stell deine Frage '
    + 'gleich noch einmal. Falls meine Antwort doch noch fertig '
    + 'geworden ist, findest du sie beim nächsten Öffnen im Verlauf.',

  // ── Begrüßung: NUR der Rückfall (C1-b4) ────────────────────────────
  /** Diese sechs greifen erst, wenn Host bzw. Studio-Config nichts liefern
   *  (`greeting`/`startReplies`). Der Regelfall ist redaktioneller Inhalt aus
   *  `welcome-config.yaml` und bleibt deutsch — die Zweisprachigkeit der
   *  Config ist bewusst vertagt (siehe Entwurf, „Was C1 NICHT umfasst"). */
  'greeting.default': 'Hey, schön dass du da bist! Ich bin Boerdi, die schlaue Eule von '
    + 'WissenLebtOnline.\nIch kann dir zeigen, wie du deine Wissens- oder '
    + 'Lerninhalte ins KI-Zeitalter bringst? Oder ich kann dir helfen '
    + 'vorhandene Inhalte in unserer Datenbasis zu finden.',
  'greeting.reset': 'Hallo! Wie kann ich dir helfen?',
  /** Benannt nach ihrer Bedeutung, nicht nach ihrer Position: eine Sprache
   *  darf die Reihenfolge nicht verschieben, aber ein Umbau der Liste soll
   *  nicht stumm die falschen Texte verschieben. */
  'greeting.reply.aiAge': 'Wie bringe ich meine Inhalte ins KI-Zeitalter?',
  'greeting.reply.search': 'Ich suche Inhalte zu einem Thema.',
  'greeting.reply.tour': 'Führe mich systematisch durch die Webseite.',
  'greeting.reply.about': 'Was ist WissenLebtOnline?',

  // ── Druckfenster (print-utils) ─────────────────────────────────────
  /** Das Druckfenster ist ein zweites Dokument ohne Angular; es baut sein HTML
   *  als String. Deshalb liegen hier auch die beiden Formatwerte: `t` ist der
   *  einzige Kanal, über den die Sprache dort ankommt — ein zweiter (eine
   *  Locale als Extra-Parameter) wäre ein Weg mehr für dieselbe Sache. */
  'print.button': '🖨 Drucken / Als PDF speichern',
  'print.docTitle': '{title} – BadBoerdi',
  'print.learningPath': 'Lernpfad',
  'print.usedContents': 'Verwendete Inhalte ({count})',
  'print.meta': 'BadBoerdi · {date}',
  'print.footer': 'Erstellt mit BadBoerdi · WirLernenOnline.de · {date}',
  'print.popupBlockedMaterial': 'Bitte erlaube Pop-ups für diese Seite, um das Material zu drucken.',
  'print.popupBlockedLearningPath': 'Bitte erlaube Pop-ups für diese Seite, um den Lernpfad zu drucken.',

  // ── WLO-Anmeldung (C5-c2) ──────────────────────────────────────────
  /** Beschriftung des Anmelde-Chips. Sie steht HIER und nicht im Marker, den
   *  das Backend schickt: der Klick löst eine Handlung im Browser aus und
   *  sendet nichts — die Beschriftung ist damit Beiwerk dieser Oberfläche und
   *  folgt dem Sprachumschalter (Begründung in `chips/auth-qr.ts`). */
  'auth.signIn': 'Mit WLO-Konto anmelden',
  /** Die sechs Ausgänge des Vorgangs. Jeder bekommt einen eigenen Satz, weil
   *  sie verschiedene Antworten verlangen: „abgelehnt" ist eine Entscheidung,
   *  „blockiert" ein Hinweis mit Handlungsanweisung, „nicht angeboten" eine
   *  Eigenschaft dieser Installation. Ein gemeinsames „hat nicht geklappt"
   *  wäre für fünf der sechs Fälle schlicht unwahr. */
  'auth.done': 'Du bist mit deinem WLO-Konto angemeldet. Ab jetzt arbeite ich in deinem Namen.',
  'auth.denied': 'Alles klar, ohne Anmeldung. Ich kann weiter suchen und zeigen — in WLO ändern kann ich nichts.',
  'auth.popupBlocked': 'Der Browser hat das Anmeldefenster blockiert. Bitte erlaube Pop-ups für diese Seite und tippe den Chip noch einmal an.',
  'auth.unavailable': 'Diese Installation bietet die WLO-Anmeldung nicht an. Suchen und Zeigen geht trotzdem.',
  'auth.timeout': 'Von der Anmeldung ist nichts zurückgekommen. Du kannst es jederzeit noch einmal versuchen.',
  'auth.failed': 'Die Anmeldung hat nicht geklappt. Bitte versuch es noch einmal.',
  /** Beschriftung des Knopfs im angemeldeten Zustand. Sagt die WIRKUNG mit,
   *  weil daneben ein Neustart-Knopf sitzt: hier endet die Anmeldung, nicht
   *  das Gespräch. */
  'auth.signOut': 'Abmelden — wieder anonym suchen',
  /** Bestätigung nach dem Abmelden. „aus diesem Tab entfernt" ist genau, nicht
   *  ungefähr: `clearAccessBlock` räumt den `sessionStorage`, der Zugang selbst
   *  bleibt gültig, bis er auf der `/auth`-Seite widerrufen wird. */
  'auth.signedOut': 'Abgemeldet. Ich suche wieder anonym — der Zugang ist aus diesem Tab entfernt.',

  // ── Vorbereitete Änderung im Repositorium (E4) ─────────────────────
  /** Die fünf Ausgänge des Ausführers (`session/prepared-write.ts`). Vier davon
   *  sagen dasselbe Wichtigste — es wurde nichts geändert — und haben trotzdem
   *  je einen eigenen Satz: sie verlangen verschiedene nächste Schritte.
   *  `prepared.done` erscheint nur, wenn das Werkzeug drüben keinen eigenen
   *  Satz mitgegeben hat; sonst steht dort dessen genauere Fassung. */
  'prepared.done': 'Erledigt — die Änderung ist im Repositorium gespeichert.',
  'prepared.blocked': 'Diese Änderung darf ich von hier aus nicht ausführen. Es wurde nichts geändert.',
  'prepared.signedOut': 'Im Repositorium bist du gerade nicht angemeldet — deshalb habe ich '
    + 'nichts geändert. Melde dich in diesem Tab an und sag mir noch einmal Bescheid.',
  'prepared.unreachable': 'Ich konnte beim Repositorium nicht klären, wer du bist. '
    + 'Es wurde nichts geändert.',
  'prepared.failed': 'Das Repositorium hat die Änderung abgelehnt. Es wurde nichts geändert.',

  // ── Formatwerte, keine Texte ───────────────────────────────────────
  /** `lang`-Auszeichnung des Druckdokuments (WCAG 3.1.1). */
  'format.htmlLang': 'de',
  /** BCP-47-Tag für `toLocaleDateString` im Druckfenster. Ein Test prüft, dass
   *  jeder Katalogwert hier für `Intl` brauchbar ist. */
  'format.dateLocale': 'de-DE',
};
