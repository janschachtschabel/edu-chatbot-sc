/**
 * Feldtexte (ST-1) der Seite „Material-Formate": Material-Typen, Aliase,
 * Auslöser und Vorrang je Persona (`05-canvas/*`).
 *
 * Schlüsselschema wie in allen `fields-*.ts` (siehe `fields-layer-doc.ts`).
 * Erzeugt wird Material nur in der Muster-Engine, über den Erstell-Schnellweg
 * nach Intent I05 (`services/canvas_fast_path.py`); die Agent-Schleife schaltet
 * ihn ab (`graph/nodes/route.py`). Nicht ausgewertet werden die Auslöser zum
 * Erstellen und Überarbeiten, die Such-Verben und die Ressourcentyp-Zuordnung:
 * ihre Leser in `domain/canvas/intent.py` und `domain/canvas/types.py` ruft
 * außer den Tests niemand auf, den für die Such-Verben gibt es gar nicht mehr.
 * Die Hilfetexte sagen das, auch wo die Seed-Kommentare noch anderes erzählen.
 */
import type { CataloguePart } from './catalogue-part';

export const FIELDS_MATERIAL: CataloguePart = {
  de: {
    // ── Material-Typen ──────────────────────────────────────────────
    'feld.CanvasMaterialTypesArea.material_types.label': 'Material-Typen',
    'feld.CanvasMaterialTypesArea.material_types.hint':
      'Die Formate, die Boerdi auf Wunsch erzeugt, etwa Arbeitsblatt oder Quiz. Nur '
      + 'Muster-Engine: die Agent-Schleife nutzt den Erstell-Weg nicht. Leer: eingebaute Liste.',
    'feld.MaterialType.id.label': 'Kennung',
    'feld.MaterialType.id.hint':
      'Etwa arbeitsblatt. Aliase zeigen auf sie; auto muss es geben, darauf fällt ein nicht '
      + 'gelisteter Wunsch zurück. Bei arbeitsblatt, quiz und uebung ergänzt der Code einen '
      + 'Lösungs-Platzhalter, falls Lösungen fehlen.',
    'feld.MaterialType.label.label': 'Name (deutsch)',
    'feld.MaterialType.label.hint':
      'Etwa Arbeitsblatt: im Typ-Chip, in der Fertig-Meldung und im Erstell-Prompt. Ein Klick '
      + 'schickt den Chip-Text zurück, darum braucht er einen gleichlautenden Alias. Leer: die '
      + 'Kennung.',
    'feld.MaterialType.label_en.label': 'Name (englisch)',
    'feld.MaterialType.label_en.hint':
      'Name für Chip und Fertig-Meldung, wenn das Widget auf Englisch läuft. Leer heißt nicht '
      + 'gepflegt: dann erscheint der deutsche Name. Auch er braucht einen gleichlautenden Alias.',
    'feld.MaterialType.emoji.label': 'Symbol',
    'feld.MaterialType.emoji.hint':
      'Emoji vor dem Namen im Typ-Chip und im Erstell-Prompt, etwa 📝. Leer: 📄.',
    'feld.MaterialType.category.label': 'Kategorie',
    'feld.MaterialType.category.hint':
      'didaktisch oder analytisch. analytisch schaltet den Erstell-Prompt auf sachliche '
      + 'Vorlagen (siezend, Zahlen nur belegt) und zeigt den Typ analytischen Personas zuerst. '
      + 'Sonst gilt didaktisch.',
    'feld.MaterialType.structure.label': 'Gliederungsvorgabe',
    'feld.MaterialType.structure.hint':
      'Gliederung in Markdown, die das Modell beim Erstellen als „Vorgaben" bekommt, etwa '
      + 'Überschrift, Zahl der Aufgaben, Lösungsteil. Leer: keine Vorgabe.',

    // ── Aliase ──────────────────────────────────────────────────────
    'feld.CanvasTypeAliasesArea.aliases.label': 'Aliase',
    'feld.CanvasTypeAliasesArea.aliases.hint':
      'Wörter, an denen Boerdi den gewünschten Typ erkennt: Schlüssel = Wort, Wert = '
      + 'Typ-Kennung, etwa test → quiz. Ergänzt die eingebaute Liste. Wörter unter sechs '
      + 'Zeichen greifen mitten im Satz nur als erlaubtes Kurzwort.',
    'feld.CanvasTypeAliasesArea.short_whitelist.label': 'Erlaubte Kurzwörter',
    'feld.CanvasTypeAliasesArea.short_whitelist.hint':
      'Aliase unter sechs Zeichen, die auch mitten im Satz als ganzes Wort zählen, etwa quiz. '
      + 'Nur eindeutige Wörter. Eine gefüllte Liste ersetzt die Vorgabe quiz, test, kpi, pm.',
    'feld.CanvasTypeAliasesArea.lrt_to_type.label': 'Ressourcentyp-Zuordnung',
    'feld.CanvasTypeAliasesArea.lrt_to_type.hint':
      'Ordnet WLO-Ressourcentypen einem Material-Typ zu, gedacht für das Umarbeiten '
      + 'vorhandener Inhalte. Wird derzeit nicht ausgewertet.',

    // ── Auslöser ────────────────────────────────────────────────────
    'feld.CanvasCreateTriggersArea.create_triggers.label': 'Erstell-Auslöser',
    'feld.CanvasCreateTriggersArea.create_triggers.hint':
      'Wendungen wie „erstelle" oder „generiere", die einen Erstell-Auftrag anzeigen sollen. '
      + 'Wird derzeit nicht ausgewertet: ob erstellt wird, entscheidet der Klassifikator (I05).',
    'feld.CanvasCreateTriggersArea.search_verbs.label': 'Such-Verben',
    'feld.CanvasCreateTriggersArea.search_verbs.hint':
      'Verben wie „zeig" oder „suche", die eine Suche statt eines Erstell-Auftrags anzeigen '
      + 'sollten. Wird derzeit nicht ausgewertet.',
    'feld.CanvasEditTriggersArea.edit_triggers.label': 'Überarbeitungs-Auslöser',
    'feld.CanvasEditTriggersArea.edit_triggers.hint':
      'Wendungen wie „mach es einfacher" oder „kürzer", die ein bestehendes Material '
      + 'überarbeiten sollen. Wird derzeit nicht ausgewertet: das erkennt der Klassifikator (I06).',
    'feld.CanvasEditTriggersArea.explicit_create_overrides.label': 'Vorrang: neu erstellen',
    'feld.CanvasEditTriggersArea.explicit_create_overrides.hint':
      'Wendungen wie „neues Quiz" oder „anderes Thema", die trotz laufender Überarbeitung '
      + 'einen Neuanfang verlangen sollen. Wird derzeit nicht ausgewertet.',

    // ── Vorrang je Persona ──────────────────────────────────────────
    'feld.CanvasPersonaPrioritiesArea.analytical_personas.label': 'Analytische Personas',
    'feld.CanvasPersonaPrioritiesArea.analytical_personas.hint':
      'Persona-Kennungen, denen Boerdi bei der Frage nach dem Typ analytische Formate (Bericht, '
      + 'Factsheet …) zuerst anbietet; sie bekommen auch analytische Quick-Replies. Leer: '
      + 'P-ENT und P-RED.',
  },
  en: {
    // ── Material types ──────────────────────────────────────────────
    'feld.CanvasMaterialTypesArea.material_types.label': 'Material types',
    'feld.CanvasMaterialTypesArea.material_types.hint':
      'The formats Boerdi produces on request, such as worksheet or quiz. Pattern engine only: '
      + 'the agent loop does not use the creation path. Empty: built-in list.',
    'feld.MaterialType.id.label': 'Identifier',
    'feld.MaterialType.id.hint':
      'Such as arbeitsblatt. Aliases point to it; auto must exist, an unlisted request falls '
      + 'back to it. For arbeitsblatt, quiz and uebung the code adds a solutions placeholder '
      + 'if solutions are missing.',
    'feld.MaterialType.label.label': 'Name (German)',
    'feld.MaterialType.label.hint':
      'Such as Arbeitsblatt: in the type chip, in the completion message and in the creation '
      + 'prompt. A click sends the chip text back, so it needs a matching alias. Empty: the '
      + 'identifier.',
    'feld.MaterialType.label_en.label': 'Name (English)',
    'feld.MaterialType.label_en.hint':
      'Name for the chip and the completion message when the widget runs in English. Empty '
      + 'means not maintained: the German name appears instead. It also needs a matching alias.',
    'feld.MaterialType.emoji.label': 'Emoji',
    'feld.MaterialType.emoji.hint':
      'Emoji before the name in the type chip and in the creation prompt, such as 📝. Empty: 📄.',
    'feld.MaterialType.category.label': 'Category',
    'feld.MaterialType.category.hint':
      'didaktisch or analytisch. analytisch switches the creation prompt to factual documents '
      + '(formal address, figures only when backed) and shows the type first to analytical '
      + 'personas. Anything else counts as didaktisch.',
    'feld.MaterialType.structure.label': 'Structure template',
    'feld.MaterialType.structure.hint':
      'Outline in Markdown that the model receives as "Vorgaben" when creating, such as '
      + 'heading, number of tasks, solutions section. Empty: no template.',

    // ── Aliases ─────────────────────────────────────────────────────
    'feld.CanvasTypeAliasesArea.aliases.label': 'Aliases',
    'feld.CanvasTypeAliasesArea.aliases.hint':
      'Words by which Boerdi recognises the requested type: key = word, value = type '
      + 'identifier, such as test → quiz. Extends the built-in list. Words under six characters '
      + 'only match within a sentence as allowed short words.',
    'feld.CanvasTypeAliasesArea.short_whitelist.label': 'Allowed short words',
    'feld.CanvasTypeAliasesArea.short_whitelist.hint':
      'Aliases under six characters that also count as a whole word within a sentence, such as '
      + 'quiz. Only unambiguous words. A filled list replaces the default quiz, test, kpi, pm.',
    'feld.CanvasTypeAliasesArea.lrt_to_type.label': 'Resource type mapping',
    'feld.CanvasTypeAliasesArea.lrt_to_type.hint':
      'Maps WLO resource types to a material type, intended for reworking existing content. '
      + 'Currently not evaluated.',

    // ── Triggers ────────────────────────────────────────────────────
    'feld.CanvasCreateTriggersArea.create_triggers.label': 'Create triggers',
    'feld.CanvasCreateTriggersArea.create_triggers.hint':
      'Phrases such as "erstelle" or "generiere" meant to signal an order to create. Currently '
      + 'not evaluated: whether to create is decided by the classifier (I05).',
    'feld.CanvasCreateTriggersArea.search_verbs.label': 'Search verbs',
    'feld.CanvasCreateTriggersArea.search_verbs.hint':
      'Verbs such as "zeig" or "suche" that were meant to mark a search instead of an order to '
      + 'create. Currently not evaluated.',
    'feld.CanvasEditTriggersArea.edit_triggers.label': 'Edit triggers',
    'feld.CanvasEditTriggersArea.edit_triggers.hint':
      'Phrases such as "make it simpler" or "shorter" meant to revise an existing material. '
      + 'Currently not evaluated: the classifier recognises revisions (I06).',
    'feld.CanvasEditTriggersArea.explicit_create_overrides.label': 'Override: create new',
    'feld.CanvasEditTriggersArea.explicit_create_overrides.hint':
      'Phrases such as "neues Quiz" or "anderes Thema" meant to force a fresh start despite an '
      + 'ongoing revision. Currently not evaluated.',

    // ── Priority per persona ────────────────────────────────────────
    'feld.CanvasPersonaPrioritiesArea.analytical_personas.label': 'Analytical personas',
    'feld.CanvasPersonaPrioritiesArea.analytical_personas.hint':
      'Persona identifiers to whom Boerdi offers analytical formats (report, factsheet …) first '
      + 'when asking for the type; they also get analytical quick replies. Empty: P-ENT and '
      + 'P-RED.',
  },
};
