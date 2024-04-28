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
    const runIter = this.octokit.paginate.iterator(
      this.octokit.rest.actions.listWorkflowRuns,
      {
        owner,
        repo,
        workflow_id: workflowResp.data.id,
        status: 'success',
        created: `>${new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)}`
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
      `failed to find integration workflow run with tree id (${tree})`
    )
  }

  async run() {
    try {
      core.startGroup('retrieve image info')
      const images = await this.getImages()
      core.endGroup()
      core.startGroup('retrieve charm info')
      const {
        name: charmName,
        dir: charmDir,
        files: charms
      } = await this.getCharms()
      core.endGroup()
      core.info(
        `start uploading image resources: ${JSON.stringify(Object.fromEntries([...images]))}`
      )
      for (const resource of images.keys()) {
        core.info(`upload resource ${resource}`)
        const imageId = (
          await exec.getExecOutput('docker', [
            'images',
            images.get(resource) as string,
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
          { env: { CHARMCRAFT_AUTH: this.charmhubToken } }
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

  mkdtemp(): string {
    return fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-'))
  }

  async getPlan(runId: number): Promise<Plan> {
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
      .sort()
    if (artifacts.length === 0) {
      throw new Error(`can't find plan artifact for workflow run ${runId}`)
    }
    const artifact = artifacts[artifacts.length - 1]
    const tmp = this.mkdtemp()
    await this.artifact.downloadArtifact(artifact.id, { path: tmp })
    return JSON.parse(
      fs.readFileSync(path.join(tmp, 'plan.json'), { encoding: 'utf-8' })
    ) as Plan
  }

  async getImageResources(): Promise<string[]> {
    interface Metadata {
      resources?: {
        [name: string]: {
          type: string
        }
      }
    }

    let metadata = yaml.load(
      (
        await exec.getExecOutput('charmcraft', ['expand-extensions'], {
          cwd: this.workingDir
        })
      ).stdout
    ) as Metadata
    if (
      metadata.resources === undefined ||
      Object.keys(metadata.resources).length === 0
    ) {
      metadata = yaml.load(
        fs.readFileSync(path.join(this.workingDir, 'metadata.yaml'), {
          encoding: 'utf-8'
        })
      ) as Metadata
    }
    const resources = metadata.resources
    if (resources === undefined) {
      return []
    }
    return Object.keys(resources).filter(k => resources[k].type === 'oci-image')
  }

  async getImages(): Promise<Map<string, string>> {
    const resources = await this.getImageResources()
    core.info(`required resources: ${resources}`)
    const upload: Map<string, string> = new Map()
    if (resources.length === 0) {
      return upload
    }
    const runId = await this.findWorkflowRunId()
    const plan = await this.getPlan(runId)
    for (const build of plan.build) {
      if (build.type === 'charm') {
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
        await exec.exec('skopeo', [
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

  async getCharms(): Promise<{ name: string; dir: string; files: string[] }> {
    const runId = await this.findWorkflowRunId()
    const plan = await this.getPlan(runId)
    const charms = plan.build.filter(b => b.type === 'charm')
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
}

// eslint-disable-next-line @typescript-eslint/no-floating-promises
new Publish().run()
