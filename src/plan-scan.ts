// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import { DefaultArtifactClient } from '@actions/artifact'
import * as core from '@actions/core'
import fs from 'fs'
import * as os from 'os'
import * as path from 'path'
import { Plan } from './model'

interface Scan {
  artifact: string
  file: string
  image: string
  dir: string
}

const commonIgnorePatterns = `#this is a list of common CVE's
# statsd_exporter - golang
# oauth2
CVE-2025-22868
# crypto
CVE-2025-22869
CVE-2024-45337
# gnupg
CVE-2025-68973
`

function ConcatIgnores(dir: string): string {
  // find the nearest .trivyignore file by walking up from the parent of the given dir
  // and write back the combined content
  const startDir = path.resolve(dir)
  let currentDir = path.dirname(startDir)
  let ignoreFile = path.join(currentDir, '.trivyignore')
  while (!fs.existsSync(ignoreFile)) {
    const parentDir = path.dirname(currentDir)
    if (parentDir === currentDir) {
      break
    }
    core.info(
      `parentDir: ${parentDir}, currentDir: ${currentDir}, ignoreFile: ${ignoreFile}`
    )
    currentDir = parentDir
    ignoreFile = path.join(currentDir, '.trivyignore')
  }
  if (!fs.existsSync(ignoreFile)) {
    ignoreFile = path.join(startDir, '.trivyignore')
  }
  const originalContent = fs.existsSync(ignoreFile)
    ? fs.readFileSync(ignoreFile, { encoding: 'utf-8' })
    : ''
  core.info(`Using .trivyignore at: ${ignoreFile}`)
  core.info(`Original .trivyignore content:\n${originalContent}`)
  let ignoreContent = commonIgnorePatterns
  if (originalContent) {
    ignoreContent = originalContent + os.EOL + commonIgnorePatterns
  }
  core.info(`Final .trivyignore content:\n${ignoreContent}`)
  fs.writeFileSync(ignoreFile, ignoreContent, { encoding: 'utf-8' })
  return ignoreContent
}

export async function run(): Promise<void> {
  try {
    const plan: Plan = JSON.parse(core.getInput('plan'))
    const artifact = new DefaultArtifactClient()
    let scans: Scan[] = []
    for (const build of plan.build) {
      core.info(`Testing!`)
      if (['charm', 'file'].includes(build.type)) {
        core.info(`Skipping ${build.type} build`)
        continue
      }
      core.info(`Processing ${build.type} build`)
      ConcatIgnores(build.dir)
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
