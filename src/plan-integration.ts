// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'
import { Plan } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import path from 'path'
import os from 'os'
import * as exec from '@actions/exec'

import * as github from '@actions/github'

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function waitBuild(githubToken: string, jobId: number): Promise<void> {
  const octokit = github.getOctokit(githubToken)
  const deadline = Date.now() + 3 * 3600 * 1000
  while (Date.now() <= deadline) {
    await sleep(5000)
    const jobs = await octokit.paginate(
      octokit.rest.actions.listJobsForWorkflowRunAttempt,
      {
        owner: github.context.repo.owner,
        repo: github.context.repo.repo,
        run_id: github.context.runId,
        attempt_number: github.context.runAttempt,
        per_page: 100
      }
    )
    const thisJob = jobs.find(job => job.id === jobId)!
    const jobPrefix = thisJob.name.split(' / ')[0]
    core.info(`looking for build jobs under ${jobPrefix}`)
    const targetJobs = jobs.filter(
      j =>
        (j.name || '').startsWith(`${jobPrefix}`) &&
        (j.name || '').includes(' / Build')
    )
    if (targetJobs.length === 0) {
      core.info('no build jobs')
      return
    }
    let successes = 0
    core.info('waiting for build jobs:')
    for (const job of targetJobs) {
      if (job.status === 'completed') {
        if (job.conclusion === 'success') {
          core.info(`[SUCCESS] ${job.name}`)
          successes++
        } else if (job.conclusion === 'skipped') {
          core.info(`[SKIPPED] ${job.name}`)
          successes++
        } else {
          throw new Error(
            `build job ${job.name} failed with conclusion: ${job.conclusion}`
          )
        }
      } else {
        core.info(`[${job.status.toUpperCase()}] ${job.name}`)
      }
    }
    if (targetJobs.length === successes) {
      return
    } else {
      // newline to increase readability
      core.info('')
    }
  }
  throw new Error('timeout waiting for build jobs')
}

async function downloadArtifact(
  artifact: DefaultArtifactClient,
  id: number
): Promise<string> {
  // When build jobs have just finished, the artifacts might not be fully available yet.
  // Retry downloading artifacts for up to 1 minute instead of immediately erroring out.
  let artifactError: any
  for (let i = 0; i < 6; i++) {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-'))
    try {
      await artifact.downloadArtifact(id, { path: tmp })
      return tmp
    } catch (error) {
      artifactError = error
      if (error instanceof Error) {
        core.error(
          `failed to download artifact: ${error.message}, retries: ${i}`
        )
      }
      await sleep(5000)
    }
  }
  throw artifactError
}

export async function run(): Promise<void> {
  try {
    const plan: Plan = JSON.parse(core.getInput('plan'))
    await waitBuild(
      core.getInput('github-token'),
      Number(core.getInput('check-run-id'))
    )
    const artifact = new DefaultArtifactClient()
    let args: string[] = []
    for (const build of plan.build) {
      const tmp = await downloadArtifact(
        artifact,
        (await artifact.getArtifact(build.output)).artifact.id
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
