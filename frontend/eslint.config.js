// @ts-check
/**
 * Flat ESLint config for the Angular workspace (spec §0 rule 1: CI runs
 * ruff/eslint). Scope is deliberately narrow — the rule sets that catch real
 * defects, not a style sweep over a finished fidelity port:
 *
 *   - typescript-eslint `recommended`: unsound TS (floating promises are not
 *     in this set, but `no-explicit-any` etc. are — see the overrides below).
 *   - angular-eslint `tsRecommended`: lifecycle/DI/output-naming mistakes.
 *   - angular-eslint `templateRecommended` + `templateAccessibility`: the
 *     template half, including the a11y rules that 8-6 audited by hand.
 *
 * `stylistic` is NOT enabled: it would rewrite a byte-near port for taste.
 */
const eslint = require('@eslint/js');
const tseslint = require('typescript-eslint');
const angular = require('angular-eslint');

module.exports = tseslint.config(
  {
    ignores: ['dist/**', '.angular/**', 'coverage/**', 'test-results/**', 'playwright-report/**'],
  },
  {
    files: ['**/*.ts', '**/*.js', '**/*.mjs'],
    extends: [
      eslint.configs.recommended,
      ...tseslint.configs.recommended,
      ...angular.configs.tsRecommended,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      // Der Port trägt ALTs `any` an den Backend-Grenzen (ChatResponse-Felder,
      // `environment`, debug_json). Sie zu typisieren wäre eine Re-Architektur,
      // nicht ein Lint-Fix — und würde die Fidelity-Zusage brechen.
      '@typescript-eslint/no-explicit-any': 'off',
      // KEIN `allowEmptyCatch`: `no-empty` erlaubt kommentierte Blöcke bereits,
      // und alle bewussten Leer-Catches hier tragen einen Kommentar (geprüft:
      // 0 unkommentierte `catch {}` im Baum). Die Option würde nur künftige,
      // wirklich stille Fehler-Schlucker durchlassen.
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      // Wir prefixen absichtlich private Felder mit `_` (ALT-Konvention).
      '@typescript-eslint/naming-convention': 'off',
    },
  },
  {
    files: ['**/*.html'],
    extends: [
      ...angular.configs.templateRecommended,
      ...angular.configs.templateAccessibility,
    ],
    rules: {},
  },
  {
    // MUSS nach dem TS-Block stehen: in der Flat-Config gewinnt das spätere
    // Objekt. Diese Datei ist selbst CommonJS (so lädt ESLint Flat-Configs,
    // solange das Paket kein `"type": "module"` hat) — `require` ist hier
    // korrekt und nicht veraltet.
    files: ['eslint.config.js'],
    rules: { '@typescript-eslint/no-require-imports': 'off' },
  },
);
