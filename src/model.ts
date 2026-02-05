// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

export interface Plan {
  working_directory: string
  build: BuildPlan[]
}

export interface BuildPlan {
  type: 'charm' | 'rock' | 'docker-image' | 'file'
  name: string
  source_file: string
  source_directory: string
  build_target: string | undefined
  output_type: 'file' | 'registry'
  output: string
  dir: string
}

export interface CharmResource {
  type: 'file' | 'oci-image'
  description?: string
  filename?: string
  'upstream-source'?: string
}
