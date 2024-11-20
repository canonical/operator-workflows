// Copyright 2024 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'
import { Plan } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import path from 'path'
import os from 'os'
import * as exec from '@actions/exec'

export async function run(): Promise<void> {
  try {
    const plan: Plan = JSON.parse(core.getInput('plan'))
    const artifact = new DefaultArtifactClient()
    let args: string[] = []
    for (const build of plan.build) {
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-'))
      await artifact.downloadArtifact(
        (await artifact.getArtifact(build.output)).artifact.id,
        { path: tmp }
      )
      const manifest = JSON.parse(
        fs.readFileSync(path.join(tmp, 'manifest.json'), { encoding: 'utf-8' })
      ) as object
      if (build.type === 'charm' || build.type === 'file') {
        // @ts-ignore
        for (const file of manifest.files as string[]) {
          fs.renameSync(
            path.join(tmp, file),
            path.join(plan.working_directory, file)
          )
          // @ts-ignore
          const name = manifest.name as string
          let argName: string =
            build.type === 'charm' ? 'charm-file' : `${name}-resource`
          args.push(`--${argName}=./${file}`)
        }
      } else if (build.type === 'rock' || build.type == 'docker-image') {
        // @ts-ignore
        const name = manifest.name as string
        if ('files' in manifest) {
          for (const file of manifest.files as string[]) {
            const image = `localhost:32000/${name}:${file.replace(`${name}_`, '')}`
            const archiveType = file.endsWith('.rock')
              ? 'oci-archive'
              : 'docker-archive'
            await exec.exec('skopeo', [
              'copy',
              '--insecure-policy',
              '--dest-tls-verify=false',
              `${archiveType}:${path.join(tmp, file)}`,
              `docker://${image}`
            ])
            args.push(`--${name}-image=${image}`)
          }
        }
        if ('images' in manifest) {
          for (const image of manifest.images as string[]) {
            args.push(`--${name}-image=${image}`)
          }
        }
      }
    }
    core.setOutput('args', args.join(' '))
  } catch (error) {
    // Fail the workflow run if an error occurs
    if (error instanceof Error) core.setFailed(error.message)
  }
}

// eslint-disable-next-line @typescript-eslint/no-floating-promises
run()
