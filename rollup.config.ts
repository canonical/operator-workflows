/*
 * Copyright 2026 Canonical Ltd.
 * See LICENSE file for licensing details.
 */

import commonjs from '@rollup/plugin-commonjs'
import nodeResolve from '@rollup/plugin-node-resolve'
import typescript from '@rollup/plugin-typescript'

const entryPoints = [
    'build',
    'get-plan',
    'model',
    'plan-integration',
    'plan-scan',
    'plan',
    'publish',
    'utils'
]

const configs = entryPoints.map(entry => ({
    input: `src/${entry}.ts`,
    output: {
        esModule: true,
        file: `dist/${entry}/index.js`,
        format: 'es',
        sourcemap: true
    },
    plugins: [
        typescript(),
        nodeResolve({ preferBuiltins: true }),
        commonjs()
    ]
}))

export default configs
