/*
 * Copyright 2026 Canonical Ltd.
 * See LICENSE file for licensing details.
 */

import commonjs from '@rollup/plugin-commonjs'
import nodeResolve from '@rollup/plugin-node-resolve'
import typescript from '@rollup/plugin-typescript'
import json from '@rollup/plugin-json'

const entryPoints = [
  'build',
  'get-plan',
  'plan-integration',
  'plan-scan',
  'plan',
  'publish'
]

const configs = entryPoints.map(entry => ({
  input: `src/${entry}.ts`,
  output: {
    file: `dist/${entry}/index.js`,
    format: 'cjs',
    sourcemap: true
  },
  plugins: [
    typescript({
      compilerOptions: {
        module: 'ESNext',
        moduleResolution: 'Bundler'
      }
    }),
    json(),
    nodeResolve({ preferBuiltins: true }),
    commonjs()
  ]
}))

export default configs
