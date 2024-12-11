// Copyright 2024 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'
import * as exec from '@actions/exec'
import * as yaml from 'js-yaml'

import * as github from '@actions/github'
import { Plan } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import path from 'path'
import os from 'os'

class Publish {
  private token: string
  private charmhubToken: string
  private octokit
  private workflowFile: string
  private artifact
  private workingDir: string
  private resourceMapping: { [key: string]: string }
  private workflowRunId: string
  private identifier: string

  constructor() {
    this.token = core.getInput('github-token')
    this.charmhubToken = core.getInput('charmhub-token')
    this.octokit = github.getOctokit(this.token)
    this.workflowFile = core.getInput('workflow-file')
    this.workingDir = core.getInput('working-directory')
    this.resourceMapping = JSON.parse(core.getInput('resource-mapping'))
    this.workflowRunId = core.getInput('workflow-run-id')
    this.identifier = core.getInput('identifier')
    this.artifact = new DefaultArtifactClient()
  }

  mkdtemp(): string {
    return fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-'))
  }

  async findWorkflowRunId(): Promise<number> {
    if (this.workflowRunId !== '') {
      return parseInt(this.workflowRunId)
    }
    const owner = github.context.repo.owner
    const repo = github.context.repo.repo
    const commit = await this.octokit.rest.git.getCommit({
      owner,
      repo,
      commit_sha: github.context.sha
    })
    const tree = commit.data.tree.sha
    core.info(`current git tree id: ${tree}`)
    core.info(`lookup integration test workflow: ${this.workflowFile}`)
    const workflowResp = await this.octokit.rest.actions.getWorkflow({
      owner,
      repo,
      workflow_id: this.workflowFile
    })
    if (workflowResp.status !== 200) {
      throw new Error(
        `failed to find integration workflow (${this.workflowFile}): status ${workflowResp.status}`
      )
    }
    core.info(`integration test workflow id: ${workflowResp.data.id}`)
    const runIter = this.octokit.paginate.iterator(
      this.octokit.rest.actions.listWorkflowRuns,
      {
        owner,
        repo,
        workflow_id: workflowResp.data.id,
        status: 'success',
        created: `>${new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)}`
      }
    )
    for await (const resp of runIter) {
      if (resp.status !== 200) {
        throw new Error(
          `failed to find integration workflow run: status ${resp.status}`
        )
      }
      for (const run of resp.data) {
        if (run?.head_commit?.tree_id === tree) {
          return run.id
        }
      }
    }
    throw new Error(
      `Failed to find integration test workflow run on tree id (${tree}).` +
        "Consider enabling the 'Require branches to be up to date before merging' setting to ensure that the integration tests are executed on the merged commit"
    )
  }

  async getPlan(runId: number): Promise<Plan> {
    core.info(`search plan artifact from workflow run: ${runId}`)
    const artifacts = (
      await this.octokit.paginate(
        this.octokit.rest.actions.listWorkflowRunArtifacts,
        {
          owner: github.context.repo.owner,
          repo: github.context.repo.repo,
          run_id: runId
        }
      )
    )
      .filter(a =>
        a.name.endsWith(
          `${this.identifier ? '__' : ''}${this.identifier}__plan`
        )
      )
      .sort((a, b) => {
        if (a.name < b.name) {
          return 1
        }
        if (a.name > b.name) {
          return -1
        }
        return 0
      })
    for (const artifact of artifacts) {
      const tmp = this.mkdtemp()
      await this.artifact.downloadArtifact(artifact.id, {
        path: tmp,
        findBy: {
          token: this.token,
          repositoryOwner: github.context.repo.owner,
          repositoryName: github.context.repo.repo,
          workflowRunId: runId
        }
      })
      const plan = JSON.parse(
        fs.readFileSync(path.join(tmp, 'plan.json'), { encoding: 'utf-8' })
      ) as Plan
      if (
        plan.working_directory === '.' ||
        this.normalizePath(this.workingDir) ===
          this.normalizePath(plan.working_directory) ||
        this.normalizePath(this.workingDir).startsWith(
          this.normalizePath(plan.working_directory) + '/'
        )
      ) {
        return plan
      }
    }
    throw new Error(`can't find plan artifact for workflow run ${runId}`)
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

  async getFiles(): Promise<Map<string, string>> {
    const [, resources] = await this.getCharmResources()
    core.info(`required resources: ${resources}`)
    const upload: Map<string, string> = new Map()
    if (resources.length === 0) {
      return upload
    }
    const runId = await this.findWorkflowRunId()
    const plan = await this.getPlan(runId)
    for (const build of plan.build) {
      if (build.type === 'file') {
        const resourceName = this.resourceMapping[build.name]
        if (!resources.includes(resourceName)) {
          core.info(`skip uploading file: ${build.name}`)
          continue
        }
        const tmp = this.mkdtemp()
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

  async getImages(): Promise<Map<string, string>> {
    const [resources] = await this.getCharmResources()
    core.info(`required resources: ${resources}`)
    const upload: Map<string, string> = new Map()
    if (resources.length === 0) {
      return upload
    }
    const runId = await this.findWorkflowRunId()
    const plan = await this.getPlan(runId)
    let dockerLogin = false
    for (const build of plan.build) {
      if (build.type === 'charm' || build.type === 'file') {
        continue
      }
      const resourceName = this.resourceMapping.hasOwnProperty(build.name)
        ? this.resourceMapping[build.name]
        : `${build.name}-image`
      if (!resources.includes(resourceName)) {
        core.info(`skip uploading image: ${build.name}`)
        continue
      }
      const tmp = this.mkdtemp()
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

  normalizePath(p: string): string {
    return path.normalize(p).replace(/\/+$/, '')
  }

  async getCharms(): Promise<{ name: string; dir: string; files: string[] }> {
    const runId = await this.findWorkflowRunId()
    const plan = await this.getPlan(runId)
    // FIXME: a workaround for paas app charms
    let charmDir = this.workingDir
    if (fs.existsSync(path.join(charmDir, 'charm', 'charmcraft.yaml'))) {
      charmDir = path.join(charmDir, 'charm')
    }
    const charms = plan.build.filter(
      b =>
        b.type === 'charm' &&
        this.normalizePath(b.source_directory) === this.normalizePath(charmDir)
    )
    if (charms.length === 0) {
      throw new Error('no charm to upload')
    }
    if (charms.length > 1) {
      throw new Error(
        `more than one charm to upload: ${charms.map(c => c.name)}`
      )
    }
    const charm = charms[0]
    const tmp = this.mkdtemp()
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
      const imageResources = await this.getImages()
      const fileResources = await this.getFiles()
      core.endGroup()
      core.startGroup('retrieve charm info')
      const {
        name: charmName,
        dir: charmDir,
        files: charms
      } = await this.getCharms()
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
      core.setOutput('charms', charms.join(','))
      core.setOutput('charm-directory', charmDir)
    } catch (error) {
      // Fail the workflow run if an error occurs
      if (error instanceof Error) {
        core.error(`${error.message}\n${error.stack}`)
        core.setFailed(error.message)
      }
    }
  }
}

// eslint-disable-next-line @typescript-eslint/no-floating-promises
new Publish().run()
