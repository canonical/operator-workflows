// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import { DefaultArtifactClient } from '@actions/artifact'
import * as core from '@actions/core'
import fs from 'fs'
import path from 'path'
import { Plan } from './model'

interface Scan {
  artifact: string
  file: string
  image: string
  dir: string
  common_ignores?: string
}

function getCommonIgnorePatterns(): string {
  const candidates = [
    process.env.GITHUB_ACTION_PATH
      ? path.resolve(
          process.env.GITHUB_ACTION_PATH,
          '..',
          '..',
          'common_trivyignores.txt'
        )
      : undefined,
    process.env.GITHUB_ACTION_PATH
      ? path.resolve(
          process.env.GITHUB_ACTION_PATH,
          '..',
          '..',
          'dist',
          'common_trivyignores.txt'
        )
      : undefined,
    path.resolve(process.cwd(), 'common_trivyignores.txt'),
    path.resolve(process.cwd(), 'dist', 'common_trivyignores.txt'),
    path.resolve(__dirname, '..', '..', 'common_trivyignores.txt')
  ].filter((p): p is string => Boolean(p))

  for (const ignoreFilePath of candidates) {
    try {
      return fs.readFileSync(ignoreFilePath, { encoding: 'utf-8' })
    } catch {
      // continue to next candidate
    }
  }

  core.warning(`Failed to read common ignores. Tried: ${candidates.join(', ')}`)
  return ''
}

export async function run(): Promise<void> {
  try {
    const plan: Plan = JSON.parse(core.getInput('plan'))
    const artifact = new DefaultArtifactClient()
    const commonIgnorePatterns = getCommonIgnorePatterns()
    let scans: Scan[] = []
    for (const build of plan.build) {
      if (['charm', 'file'].includes(build.type)) {
        core.info(`Skipping ${build.type} build`)
        continue
      }
      core.info(`Processing ${build.type} build`)
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
            dir: build.source_directory,
            common_ignores: commonIgnorePatterns
          }))
        )
      }
      if ('images' in manifest) {
        const images = manifest.images as string[]
        scans = scans.concat(
          images.map(i => ({
            artifact: '',
            file: `${i.replaceAll(/[/:]/g, '-')}.tar`,
            image: i,
            dir: build.source_directory,
            common_ignores: commonIgnorePatterns
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
