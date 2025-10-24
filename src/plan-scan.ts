// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import { DefaultArtifactClient } from '@actions/artifact'
import * as core from '@actions/core'
import fs from 'fs'
import { Plan } from './model'

interface Scan {
  artifact: string
  file: string
  image: string
  dir: string
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
      const manifest = JSON.parse(
        fs.readFileSync('manifest.json', { encoding: 'utf-8' })
      ) as object
      if ('files' in manifest) {
        const files = manifest.files as string[]
        scans = scans.concat(
          files.map(f => ({
            artifact: build.output,
            file: f,
            image: '',
            dir: build.source_directory
          }))
        )
      }
      if ('images' in manifest) {
        const images = manifest.images as string[]
        core.info(`build target: ${build.build_target}`)
        core.info(`build name: ${build.name}`)
        core.info(`build source directory: ${build.source_directory}`)
        core.info(`build source file: ${build.source_file}`)
        core.info(`build output: ${build.output}`)
        core.info(`build output type: ${build.output_type}`)

        scans = scans.concat(
          images.map(i => ({
            artifact: '',
            file: `${i.replaceAll(/[/:]/g, '-')}.tar`,
            image: i,
            dir: build.source_directory
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

// eslint-disable-next-line @typescript-eslint/no-floating-promises
run()
