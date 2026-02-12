// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'
import * as exec from '@actions/exec'
import * as yaml from 'js-yaml'

import * as github from '@actions/github'
import { mkdtemp, normalizePath } from './utils'
import { Plan, BuildPlan } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import path from 'path'

class Publish {
  private token: string
  private charmhubToken: string
  private artifact
  private workingDir: string
  private resourceMapping: { [key: string]: string }
  private integrationWorkflowFile: string
  private octokit

  constructor() {
    this.token = core.getInput('github-token')
    this.charmhubToken = core.getInput('charmhub-token')
    this.workingDir = core.getInput('working-directory')
    this.resourceMapping = JSON.parse(core.getInput('resource-mapping'))
    // Make workflowId optional: if not provided, skip aggregation.
    this.integrationWorkflowFile = core.getInput('integration-workflow-file')
    this.artifact = new DefaultArtifactClient()
    this.octokit = github.getOctokit(this.token)
  }

  async getCharmResources(): Promise<[string[], string[]]> {
    interface Metadata {
      resources?: {
        [name: string]: {
          type: string
          filename?: string
          'upstream-source'?: string
        }
      }
    }

    let cwd = this.workingDir
    // FIXME: search current working directory and the ./charm directory for charm directory
    if (!fs.existsSync(path.join(this.workingDir, 'charmcraft.yaml'))) {
      cwd = path.join(this.workingDir, 'charm')
    }
    let metadata = yaml.load(
      (
        await exec.getExecOutput('charmcraft', ['expand-extensions'], {
          cwd,
          env: {
            CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS: 'true',
            ...process.env
          }
        })
      ).stdout
    ) as Metadata
    if (
      (metadata.resources === undefined ||
        Object.keys(metadata.resources).length === 0) &&
      fs.existsSync(path.join(cwd, 'metadata.yaml'))
    ) {
      metadata = yaml.load(
        fs.readFileSync(path.join(cwd, 'metadata.yaml'), {
          encoding: 'utf-8'
        })
      ) as Metadata
    }
    const resources = metadata.resources
    if (resources === undefined) {
      return [[], []]
    }
    let images = Object.keys(resources).filter(
      k => resources[k].type === 'oci-image' && !resources[k]['upstream-source']
    )
    let files = Object.keys(resources).filter(k => resources[k].type === 'file')
    return [images, files]
  }

  async getFiles(plan: Plan, runId: number): Promise<Map<string, string>> {
    const [, resources] = await this.getCharmResources()
    core.info(`required resources: ${resources}`)
    const upload: Map<string, string> = new Map()
    if (resources.length === 0) {
      return upload
    }
    for (const build of plan.build) {
      if (build.type === 'file') {
        const resourceName = this.resourceMapping[build.name]
        if (!resources.includes(resourceName)) {
          core.info(`skip uploading file: ${build.name}`)
          continue
        }
        const tmp = mkdtemp()
        const artifact = await this.artifact.getArtifact(build.output, {
          findBy: {
            token: this.token,
            repositoryOwner: github.context.repo.owner,
            repositoryName: github.context.repo.repo,
            workflowRunId: runId
          }
        })
        await this.artifact.downloadArtifact(artifact.artifact.id, {
          path: tmp,
          findBy: {
            token: this.token,
            repositoryOwner: github.context.repo.owner,
            repositoryName: github.context.repo.repo,
            workflowRunId: runId
          }
        })
        const manifest = JSON.parse(
          fs.readFileSync(path.join(tmp, 'manifest.json'), {
            encoding: 'utf-8'
          })
        )
        const files = manifest.files as string[]
        if (files.length !== 1) {
          throw new Error(
            `file resource ${build.name} contain multiple candidates: ${files}`
          )
        }
        const file = files[0]
        upload.set(resourceName, file)
      }
    }
    return upload
  }

  async getImages(plan: Plan, runId: number): Promise<Map<string, string>> {
    const [resources] = await this.getCharmResources()
    core.info(`required resources: ${resources}`)
    const upload: Map<string, string> = new Map()
    if (resources.length === 0) {
      return upload
    }
    let dockerLogin = false
    for (const build of plan.build) {
      if (build.type === 'charm' || build.type === 'file') {
        continue
      }
      const resourceName = Object.prototype.hasOwnProperty.call(
        this.resourceMapping,
        build.name
      )
        ? this.resourceMapping[build.name]
        : `${build.name}-image`
      if (!resources.includes(resourceName)) {
        core.info(`skip uploading image: ${build.name}`)
        continue
      }
      const tmp = mkdtemp()
      const artifact = await this.artifact.getArtifact(build.output, {
        findBy: {
          token: this.token,
          repositoryOwner: github.context.repo.owner,
          repositoryName: github.context.repo.repo,
          workflowRunId: runId
        }
      })
      await this.artifact.downloadArtifact(artifact.artifact.id, {
        path: tmp,
        findBy: {
          token: this.token,
          repositoryOwner: github.context.repo.owner,
          repositoryName: github.context.repo.repo,
          workflowRunId: runId
        }
      })
      const manifest = JSON.parse(
        fs.readFileSync(path.join(tmp, 'manifest.json'), { encoding: 'utf-8' })
      )
      if (build.output_type === 'registry') {
        if (!dockerLogin) {
          await exec.exec(
            `docker`,
            [
              'login',
              '-u',
              github.context.actor,
              '--password-stdin',
              'ghcr.io'
            ],
            { input: Buffer.from(`${this.token}\n`, 'utf-8') }
          )
          dockerLogin = true
        }
        const images = manifest.images as string[]
        if (images.length !== 1) {
          throw new Error(
            `image resource ${build.name} contain multiple candidates: ${images}`
          )
        }
        const image = images[0]
        await exec.exec('docker', ['pull', image])
        upload.set(resourceName, image)
      }
      if (build.output_type === 'file') {
        const files = manifest.files as string[]
        if (files.length !== 1) {
          throw new Error(
            `image resource ${build.name} contain multiple candidates: ${files}`
          )
        }
        const file = files[0]
        const image = `${build.name}:${file}`
        const archiveType = file.endsWith('.rock')
          ? 'oci-archive'
          : 'docker-archive'
        await exec.exec('/snap/rockcraft/current/bin/skopeo', [
          'copy',
          '--insecure-policy',
          `${archiveType}:${path.join(tmp, file)}`,
          `docker-daemon:${image}`
        ])
        upload.set(resourceName, image)
      }
    }
    if (upload.size != resources.length) {
      const missing = resources.filter(r => !upload.has(r))
      throw new Error(`can't find required resources: ${missing}`)
    }
    return upload
  }

  async getCharms(
    plan: Plan,
    runId: number
  ): Promise<{ name: string; dir: string; files: string[] }> {
    // FIXME: a workaround for paas app charms
    let charmDir = this.workingDir
    if (fs.existsSync(path.join(charmDir, 'charm', 'charmcraft.yaml'))) {
      charmDir = path.join(charmDir, 'charm')
    }
    const charms = plan.build.filter(
      (b: BuildPlan) =>
        b.type === 'charm' &&
        normalizePath(b.source_directory) === normalizePath(charmDir)
    )
    if (charms.length === 0) {
      throw new Error('no charm to upload')
    }
    if (charms.length > 1) {
      throw new Error(
        `more than one charm to upload: ${charms.map((c: BuildPlan) => c.name)}`
      )
    }
    const charm = charms[0]
    const tmp = mkdtemp()
    core.info(
      `download charm artifact from integration workflow (run id: ${runId})`
    )
    const artifact = (
      await this.artifact.getArtifact(charm.output, {
        findBy: {
          token: this.token,
          repositoryOwner: github.context.repo.owner,
          repositoryName: github.context.repo.repo,
          workflowRunId: runId
        }
      })
    ).artifact
    await this.artifact.downloadArtifact(artifact.id, {
      path: tmp,
      findBy: {
        token: this.token,
        repositoryOwner: github.context.repo.owner,
        repositoryName: github.context.repo.repo,
        workflowRunId: runId
      }
    })
    const manifest = JSON.parse(
      fs.readFileSync(path.join(tmp, 'manifest.json'), { encoding: 'utf-8' })
    )
    return {
      name: manifest.name as string,
      dir: charm.source_directory,
      files: (manifest.files as string[]).map(f => path.join(tmp, f))
    }
  }

  async run() {
    try {
      core.startGroup('retrieve image info')
      const plan: Plan = JSON.parse(core.getInput('plan'))
      const runId: number = +core.getInput('run-id')
      const imageResources = await this.getImages(plan, runId)
      const fileResources = await this.getFiles(plan, runId)
      core.endGroup()
      core.startGroup('retrieve charm info')
      const {
        name: charmName,
        dir: charmDir,
        files: baseCharms
      } = await this.getCharms(plan, runId)
      // Aggregate charms from all successful integration workflow runs for current commit
      const aggregatedCharms = await this.aggregateCharmsAcrossRuns()
      // Deduplicate by filename
      const seen = new Set<string>()
      const finalCharms: string[] = []
      for (const f of [...baseCharms, ...aggregatedCharms]) {
        const name = path.basename(f)
        if (seen.has(name)) {
          core.info(`skip duplicate charm: ${name}`)
          continue
        }
        seen.add(name)
        finalCharms.push(f)
      }
      core.endGroup()
      if (fileResources.size !== 0) {
        core.info(
          `start uploading file resources: ${JSON.stringify(Object.fromEntries([...fileResources]))}`
        )
      }
      for (const [resource, filePath] of fileResources) {
        core.info(`upload resource ${resource}`)
        await exec.exec(
          'charmcraft',
          [
            'upload-resource',
            charmName,
            resource,
            `--filepath=${filePath}`,
            '--verbosity=brief'
          ],
          { env: { ...process.env, CHARMCRAFT_AUTH: this.charmhubToken } }
        )
      }
      if (imageResources.size !== 0) {
        core.info(
          `start uploading image resources: ${JSON.stringify(Object.fromEntries([...imageResources]))}`
        )
      }
      for (const [resource, image] of imageResources) {
        core.info(`upload resource ${resource}`)
        const imageId = (
          await exec.getExecOutput('docker', [
            'images',
            image,
            '--format',
            '{{.ID}}'
          ])
        ).stdout.trim()
        await exec.exec(
          'charmcraft',
          [
            'upload-resource',
            charmName,
            resource,
            `--image=${imageId}`,
            '--verbosity=brief'
          ],
          { env: { ...process.env, CHARMCRAFT_AUTH: this.charmhubToken } }
        )
      }
      core.setOutput('charms', finalCharms.join(','))
      core.setOutput('charm-directory', charmDir)
    } catch (error) {
      // Fail the workflow run if an error occurs
      if (error instanceof Error) {
        core.error(`${error.message}\n${error.stack}`)
        core.setFailed(error.message)
      }
    }
  }

  private async aggregateCharmsAcrossRuns(): Promise<string[]> {
    try {
      const owner = github.context.repo.owner
      const repo = github.context.repo.repo
      // If no workflow is provided, skip aggregation for backwards compatibility
      if (!this.integrationWorkflowFile) {
        core.info(
          'Integration workflow not provided; skipping charm aggregation'
        )
        return []
      }
      // GitHub API accepts workflow_id as either numeric ID or workflow file name (basename)
      const trimmed = this.integrationWorkflowFile.trim()
      const workflowId: number | string = /^[0-9]+$/.test(trimmed)
        ? Number(trimmed)
        : path.basename(trimmed)
      // List successful runs of the workflow
      const runs = await this.octokit.paginate(
        this.octokit.rest.actions.listWorkflowRuns,
        {
          owner,
          repo,
          workflow_id: workflowId,
          per_page: 100,
          status: 'success'
        }
      )
      const matchingRuns = runs.filter(
        r => r.head_sha === github.context.sha && r.conclusion === 'success'
      )
      if (matchingRuns.length === 0) {
        core.info('No successful integration runs found to aggregate charms')
        return []
      }
      const aggregated: string[] = []
      for (const run of matchingRuns) {
        core.info(`Inspecting artifacts from run ${run.id}`)
        const artifacts = await this.octokit.paginate(
          this.octokit.rest.actions.listWorkflowRunArtifacts,
          { owner, repo, run_id: run.id, per_page: 100 }
        )
        for (const art of artifacts) {
          // Download each artifact and scan for .charm files
          const tmp = mkdtemp()
          try {
            await this.artifact.downloadArtifact(art.id, {
              path: tmp,
              findBy: {
                token: this.token,
                repositoryOwner: owner,
                repositoryName: repo,
                workflowRunId: run.id
              }
            })
            const charms = this.findCharmFiles(tmp)
            for (const c of charms) {
              aggregated.push(c)
              core.info(`Found charm in run ${run.id}: ${path.basename(c)}`)
            }
          } catch (e) {
            core.info(
              `Failed downloading artifact ${art.name} from run ${run.id}: ${String(e)}`
            )
          }
        }
      }
      return aggregated
    } catch (e) {
      core.info(`Charm aggregation failed: ${String(e)}`)
      return []
    }
  }

  private findCharmFiles(root: string): string[] {
    const results: string[] = []
    const stack: string[] = [root]
    while (stack.length) {
      const dir = stack.pop() as string
      const entries = fs.readdirSync(dir, { withFileTypes: true })
      for (const ent of entries) {
        const p = path.join(dir, ent.name)
        if (ent.isDirectory()) {
          stack.push(p)
        } else if (ent.isFile() && ent.name.endsWith('.charm')) {
          results.push(p)
        }
      }
    }
    return results
  }
}

// eslint-disable-next-line @typescript-eslint/no-floating-promises
new Publish().run()
