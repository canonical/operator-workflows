// Flat ESLint config for ESLint v10
// Lints TypeScript in src with Prettier integration.

const tseslint = require('@typescript-eslint/eslint-plugin')
const tsParser = require('@typescript-eslint/parser')
const prettierPlugin = require('eslint-plugin-prettier')

module.exports = [
  // Global ignores
  {
    ignores: ['dist/**', 'node_modules/**', 'coverage/**']
  },
  // TypeScript rules for project sources
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: 2022,
      sourceType: 'module'
    },
    plugins: {
      '@typescript-eslint': tseslint,
      prettier: prettierPlugin
    },
    rules: {
      // Recommended rules from @typescript-eslint (non type-checked)
      ...(tseslint.configs && tseslint.configs.recommended
        ? tseslint.configs.recommended.rules
        : {}),
      // Enforce Prettier formatting via ESLint
      'prettier/prettier': 'error'
    }
  }
]
