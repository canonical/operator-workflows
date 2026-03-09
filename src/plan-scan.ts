// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'
import { Plan } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import { parseManifest } from './manifest'

interface Scan {
  artifact: string
  file: string
  image: string
}

export async function run(): Promise<void> {
  try {
    const plan: Plan = JSON.parse(core.getInput('plan'))
    const artifact = new DefaultArtifactClient()
    let scans: Scan[] = []
    for (const build of plan.build) {
      if (['charm', 'file'].includes(build.type)) {
        core.info(`Skipping ${build.type} build`)
        continue
      }
      fs.readdirSync('.').forEach(file =>
        fs.rmSync(file, { force: true, recursive: true })
      )
      await artifact.downloadArtifact(
        (await artifact.getArtifact(build.output)).artifact.id
      )
      const manifest = parseManifest(
        JSON.parse(fs.readFileSync('manifest.json', { encoding: 'utf-8' }))
      )
      if (manifest.files) {
        scans = scans.concat(
          manifest.files.map(f => ({
            artifact: build.output,
            file: f,
            image: ''
          }))
        )
      }
      if (manifest.images) {
        scans = scans.concat(
          manifest.images.map(i => ({
            artifact: '',
            file: `${i.replaceAll(/[/:]/g, '-')}.tar`,
            image: i
          }))
        )
      }
    }
    core.setOutput('scans', JSON.stringify(scans, null, 2))
  } catch (error) {
    // Fail the workflow run if an error occurs
    if (error instanceof Error) core.setFailed(error.message)
  }
}

run()
