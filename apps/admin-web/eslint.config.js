// ESLint for the admin app. Run with `npm run lint` (CI runs it through `make lint-web`).
import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'coverage'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Colours come from the Liana design tokens (src/styles/tokens.css), not from code.
      'no-restricted-syntax': [
        'error',
        {
          selector: 'Literal[value=/^#[0-9a-fA-F]{3,8}$/]',
          message: 'Use a design token from src/styles/tokens.css (var(--color-...)) instead of a hex colour.',
        },
        {
          selector: 'Literal[value=/rgba?\\(/]',
          message: 'Use a design token from src/styles/tokens.css instead of an rgb()/rgba() colour.',
        },
      ],
    },
  },
  {
    // Vitest globals (test, expect, vi) in test files.
    files: ['**/*.test.{ts,tsx}', 'src/test/**'],
    languageOptions: { globals: { ...globals.browser, ...globals.node, vi: 'readonly', test: 'readonly', expect: 'readonly', beforeEach: 'readonly', afterEach: 'readonly', describe: 'readonly', it: 'readonly' } },
  },
);
