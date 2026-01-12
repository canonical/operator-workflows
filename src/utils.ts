// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import fs from 'fs'
import path from 'path'
import os from 'os'

export function mkdtemp(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-'))
}

export function normalizePath(p: string): string {
  return path.normalize(p).replace(/\/+$/, '')
}
