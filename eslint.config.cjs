// ESLint v9 flat config (CommonJS)
const js = require('@eslint/js')
const tsParser = require('@typescript-eslint/parser')
const tsPlugin = require('@typescript-eslint/eslint-plugin')
const prettierPlugin = require('eslint-plugin-prettier')
const jsoncPlugin = require('eslint-plugin-jsonc')
const jestPlugin = require('eslint-plugin-jest')

module.exports = [
  // Migrate from .eslintignore
  {
    ignores: ['lib/', 'dist/', 'node_modules/', 'coverage/', '**/*.json']
  },

  // Base JS recommended rules
  js.configs.recommended,

  // TypeScript files
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: 2023,
      sourceType: 'module',
      globals: {
        process: 'readonly',
        Buffer: 'readonly',
        setTimeout: 'readonly',
        crypto: 'readonly'
      }
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      prettier: prettierPlugin,
      jest: jestPlugin
    },
    rules: {
      // Prefer TS-aware rules
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_' }
      ],
      '@typescript-eslint/ban-ts-comment': 'warn',
      'prettier/prettier': 'error'
    }
  },

  // Jest test files
  {
    files: ['**/*.test.ts', 'tests/**/*.ts'],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: 2023,
      sourceType: 'module'
    },
    plugins: {
      jest: jestPlugin,
      '@typescript-eslint': tsPlugin
    },
    rules: {
      'jest/expect-expect': 'warn'
    }
  },

  // JSON files with jsonc plugin
  {
    files: ['**/*.json'],
    plugins: {
      jsonc: jsoncPlugin,
      prettier: prettierPlugin
    },
    rules: {
      'prettier/prettier': 'error'
    }
  }
]
