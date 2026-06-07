// @ts-check
const eslint = require('@eslint/js');
const { defineConfig } = require('eslint/config');
const tseslint = require('typescript-eslint');
const angular = require('angular-eslint');

module.exports = defineConfig([
  {
    files: ['**/*.ts'],
    extends: [
      eslint.configs.recommended,
      tseslint.configs.recommended,
      tseslint.configs.stylistic,
      angular.configs.tsRecommended,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      // Non-a11y stylistic rules downgraded to keep this a11y-focused pass minimal.
      // prefer-inject would require refactoring every service/component constructor to
      // the inject() function (a large, behavior-neutral churn) — out of scope here.
      '@angular-eslint/prefer-inject': 'off',
      // Empty functions are overwhelmingly intentional in this codebase: test-double
      // stubs (e.g. mock navigate/setToken) and deliberate no-op RxJS error callbacks.
      '@typescript-eslint/no-empty-function': 'off',
      '@angular-eslint/directive-selector': [
        'error',
        {
          type: 'attribute',
          prefix: 'app',
          style: 'camelCase',
        },
      ],
      '@angular-eslint/component-selector': [
        'error',
        {
          type: 'element',
          prefix: 'app',
          style: 'kebab-case',
        },
      ],
    },
  },
  {
    files: ['**/*.html'],
    extends: [angular.configs.templateRecommended, angular.configs.templateAccessibility],
    rules: {},
  },
]);
