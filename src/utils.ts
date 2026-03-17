// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import fs from 'fs'
import path from 'path'
import os from 'os'
import { Plan } from './model.js'

export function mkdtemp(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-'))
}

export function normalizePath(p: string): string {
  return path.normalize(p).replace(/\/+$/, '')
}

/**
 * Merge charm build entries from an additional plan into the target plan,
 * deduplicating by charm name so that identical charms built across multiple
 * integration test runs are only included once.
 */
export function mergeCharmBuilds(target: Plan, source: Plan): void {
  const existingCharms = new Set(
    target.build.filter(b => b.type === 'charm').map(b => b.name)
  )
  for (const build of source.build) {
    if (build.type === 'charm' && !existingCharms.has(build.name)) {
      target.build.push(build)
      existingCharms.add(build.name)
    }
  }
}
