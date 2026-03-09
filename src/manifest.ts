// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

/**
 * Shape of manifest.json produced by build jobs.
 *
 * Every manifest includes `name`. Depending on output type, it contains
 * `files` (file-based artifacts) and/or `images` (registry-pushed images).
 */
export interface ArtifactManifest {
  name: string
  files?: string[]
  images?: string[]
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(v => typeof v === 'string')
}

/**
 * Parse and validate a raw manifest value (typically from JSON.parse) into
 * a strongly typed {@link ArtifactManifest}.
 *
 * Throws if the value is not a valid manifest object.
 */
export function parseManifest(raw: unknown): ArtifactManifest {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    throw new Error('invalid manifest: expected an object')
  }
  const obj = raw as Record<string, unknown>
  if (typeof obj.name !== 'string') {
    throw new Error('invalid manifest: missing or non-string "name"')
  }
  const manifest: ArtifactManifest = { name: obj.name }
  if (obj.files !== undefined) {
    if (!isStringArray(obj.files)) {
      throw new Error('invalid manifest: "files" must be an array of strings')
    }
    manifest.files = obj.files
  }
  if (obj.images !== undefined) {
    if (!isStringArray(obj.images)) {
      throw new Error('invalid manifest: "images" must be an array of strings')
    }
    manifest.images = obj.images
  }
  return manifest
}
