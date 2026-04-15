// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'
import * as exec from '@actions/exec'
import * as yaml from 'js-yaml'

import * as github from '@actions/github'
import { mkdtemp, normalizePath } from './utils'
import { Plan } from './model'
import { parseManifest } from './manifest'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import path from 'path'

class Publish {
  private token: string
  private charmhubToken: string
  private artifact
  private workingDir: string
  private resourceMapping: { [key: string]: string }

  constructor() {
    this.token = core.getInput('github-token')
    this.charmhubToken = core.getInput('charmhub-token')
    this.workingDir = core.getInput('working-directory')
    this.resourceMapping = JSON.parse(core.getInput('resource-mapping'))
    this.artifact = new DefaultArtifactClient()
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
    const images = Object.keys(resources).filter(
      k => resources[k].type === 'oci-image' && !resources[k]['upstream-source']
    )
    const files = Object.keys(resources).filter(
      k => resources[k].type === 'file'
    )
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
        const manifest = parseManifest(
          JSON.parse(
            fs.readFileSync(path.join(tmp, 'manifest.json'), {
              encoding: 'utf-8'
            })
          )
        )
        if (!manifest.files) {
          throw new Error(
            `file resource ${build.name} missing files in manifest`
          )
        }
        const files = manifest.files
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
      const manifest = parseManifest(
        JSON.parse(
          fs.readFileSync(path.join(tmp, 'manifest.json'), {
            encoding: 'utf-8'
          })
        )
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
        if (!manifest.images) {
          throw new Error(
            `image resource ${build.name} missing images in manifest`
          )
        }
        const images = manifest.images
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
        if (!manifest.files) {
          throw new Error(
            `image resource ${build.name} missing files in manifest`
          )
        }
        const files = manifest.files
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
        await exec.exec('rockcraft.skopeo', [
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
      b =>
        b.type === 'charm' &&
        normalizePath(b.source_directory) === normalizePath(charmDir)
    )
    if (charms.length === 0) {
      throw new Error('no charm to upload')
    }
    let charmName: string | undefined
    let charmSourceDir: string | undefined
    const allFiles: string[] = []
    for (const charm of charms) {
      const tmp = mkdtemp()
      core.info(
        `download charm artifact "${charm.output}" from integration workflow (run id: ${runId})`
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
      const manifest = parseManifest(
        JSON.parse(
          fs.readFileSync(path.join(tmp, 'manifest.json'), {
            encoding: 'utf-8'
          })
        )
      )
      if (!manifest.files) {
        throw new Error(`charm ${charm.name} missing files in manifest`)
      }
      if (!charmName) {
        charmName = manifest.name
        charmSourceDir = charm.source_directory
      }
      allFiles.push(...manifest.files.map(f => path.join(tmp, f)))
    }
    // Deduplicate by charm name and base/platform (e.g., jenkins-agent_ubuntu@22.04-amd64.charm)
    // Each unique charm+base combination should be preserved
    const uniqueCharms = new Map<string, string>()
    for (const file of allFiles) {
      const basename = path.basename(file)
      // Use basename as key to deduplicate identical charm files
      // Charm filename format: {name}_{base}@{version}-{arch}.charm
      // e.g., jenkins-agent_ubuntu@22.04-amd64.charm
      if (!uniqueCharms.has(basename)) {
        uniqueCharms.set(basename, file)
      }
    }
    const uniqueFiles = Array.from(uniqueCharms.values())
    return {
      name: charmName!,
      dir: charmSourceDir!,
      files: uniqueFiles
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
        files: charms
      } = await this.getCharms(plan, runId)
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

new Publish().run()
