// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'
import * as glob from '@actions/glob'
import * as path from 'path'
import * as yaml from 'js-yaml'
import * as fs from 'fs'
import * as github from '@actions/github'
import { Plan, BuildPlan, CharmResource } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import * as os from 'os'

function normalizePath(p: string): string {
  return path.normalize(p).replace(/\/+$/, '')
}

function sanitizeArtifactName(name: string): string {
  return name.replaceAll(/[\t\n:\/\\"<>|*?]/g, '-')
}

function fromFork(): boolean {
  const context = github.context
  if (context.eventName !== 'pull_request') {
    return false
  }
  return (
    // @ts-expect-error: GitHub context payload uses narrow typing
    context.repo.owner !== context.payload.pull_request.head.repo.owner.login
  )
}

async function planBuildCharm(
  workingDir: string,
  id: string
): Promise<BuildPlan[]> {
  const allCharmcraftFiles = await (
    await glob.create(path.join(workingDir, '**', 'charmcraft.yaml'))
  ).glob()
  const charmcraftFiles = allCharmcraftFiles.filter(
    file =>
      !path.normalize(path.relative(workingDir, file)).startsWith('tests/')
  )
  return charmcraftFiles.map((charmcraftFile: string) => {
    const file = path.join(
      workingDir,
      path.relative(workingDir, charmcraftFile)
    )
    const charmcraft = yaml.load(
      fs.readFileSync(charmcraftFile, { encoding: 'utf-8' })
    ) as object
    // @ts-expect-error: charmcraft YAML is untyped
    let name: string
    if ('name' in charmcraft) {
      name = charmcraft['name'] as string
    } else {
      const metadataFile = path.join(
        path.dirname(charmcraftFile),
        'metadata.yaml'
      )
      const metadata = yaml.load(
        fs.readFileSync(metadataFile, { encoding: 'utf-8' })
      ) as object
      if (!('name' in metadata)) {
        throw new Error(`unknown charm name (${workingDir})`)
      }
      name = metadata['name'] as string
    }
    return {
      type: 'charm',
      name,
      source_file: file,
      source_directory: path.dirname(file),
      build_target: undefined,
      output_type: 'file',
      output: sanitizeArtifactName(`${id}__build__output__charm__${name}`)
    }
  })
}

async function planBuildRock(
  workingDir: string,
  id: string,
  outputType: 'file' | 'registry'
): Promise<BuildPlan[]> {
  const rockcraftFiles = await (
    await glob.create(path.join(workingDir, '**', '*rockcraft.yaml'))
  ).glob()
  return rockcraftFiles.map((rockcraftFile: string) => {
    const file = path.join(workingDir, path.relative(workingDir, rockcraftFile))
    const rockcraft = yaml.load(
      fs.readFileSync(rockcraftFile, { encoding: 'utf-8' })
    )
    // @ts-expect-error: rockcraft YAML is untyped
    const name = rockcraft['name']
    return {
      type: 'rock',
      name,
      source_file: file,
      source_directory: path.dirname(file),
      build_target: undefined,
      output_type: outputType,
      output: sanitizeArtifactName(`${id}__build__output__rock__${name}`)
    }
  })
}

async function planBuildDockerImage(
  workingDir: string,
  id: string,
  outputType: 'file' | 'registry'
): Promise<BuildPlan[]> {
  const dockerFiles = await (
    await glob.create(path.join(workingDir, '**', '*.Dockerfile'))
  ).glob()
  return dockerFiles.map((dockerFile: string) => {
    const file = path.join(workingDir, path.relative(workingDir, dockerFile))
    const name = path.basename(file).replace(/.Dockerfile$/, '')
    return {
      type: 'docker-image',
      name,
      source_file: file,
      source_directory: path.dirname(file),
      build_target: undefined,
      output_type: outputType,
      output: sanitizeArtifactName(
        `${id}__build__output__docker-image__${name}`
      )
    }
  })
}

async function planBuildFileResource(
  workingDir: string,
  id: string
): Promise<BuildPlan[]> {
  const allCharmcraftFiles = await (
    await glob.create(path.join(workingDir, '**', 'charmcraft.yaml'))
  ).glob()
  const charmcraftFiles = allCharmcraftFiles.filter(
    file =>
      !path.normalize(path.relative(workingDir, file)).startsWith('tests/')
  )
  return charmcraftFiles.flatMap((charmcraftFile: string) => {
    const file = path.join(
      workingDir,
      path.relative(workingDir, charmcraftFile)
    )
    const charmcraft = yaml.load(
      fs.readFileSync(charmcraftFile, { encoding: 'utf-8' })
    ) as object
    const metadataFile = path.join(
      path.dirname(charmcraftFile),
      'metadata.yaml'
    )
    const metadataExists = fs.existsSync(metadataFile)
    const metadata = metadataExists
      ? (yaml.load(
          fs.readFileSync(metadataFile, { encoding: 'utf-8' })
        ) as object)
      : {}

    let charmName: string = ''
    if ('name' in charmcraft) {
      charmName = charmcraft['name'] as string
    } else if ('name' in metadata) {
      charmName = metadata.name as string
    } else {
      throw new Error(`unknown charm name (${workingDir})`)
    }

    let resources: Map<string, CharmResource> = new Map()
    if ('resources' in charmcraft) {
      resources = charmcraft['resources'] as Map<string, CharmResource>
    }
    if ('resources' in metadata) {
      resources = metadata['resources'] as Map<string, CharmResource>
    }

    return Object.entries(resources).reduce(
      (acc, [resourceName, resource]: [string, CharmResource]) => {
        if (resource.type === 'file' && resource.filename) {
          let parent = path.dirname(file)
          if (resource.description?.trim().startsWith('(local)')) {
            return acc
          }
          acc.push({
            type: 'file',
            name: resourceName,
            source_file: `build-${resourceName}.sh`,
            build_target: resource.filename,
            source_directory: parent,
            output_type: 'file',
            output: sanitizeArtifactName(
              `${id}__build__output__file__${charmName}__${resourceName}`
            )
          })
        }
        return acc
      },
      [] as BuildPlan[]
    )
  })
}

async function planBuild(
  workingDir: string,
  id: string,
  imageOutputType: 'file' | 'registry'
): Promise<BuildPlan[]> {
  return [
    ...(await planBuildCharm(workingDir, id)),
    ...(await planBuildRock(workingDir, id, imageOutputType)),
    ...(await planBuildDockerImage(workingDir, id, imageOutputType)),
    ...(await planBuildFileResource(workingDir, id))
  ]
}

export async function run(): Promise<void> {
  try {
    let id = `${new Date().toISOString().replaceAll(':', '-').replace(/\..+/, '')}-${crypto.randomUUID().split('-')[3]}`
    const identity = core.getInput('identifier')
    if (identity.includes('__')) {
      core.setFailed('identifier can not contain "__"')
      return
    }
    if (identity) {
      id = `${id}__${identity}`
    }
    const workingDir: string = normalizePath(core.getInput('working-directory'))
    let imageOutputType: 'file' | 'registry'
    const uploadImage = core.getInput('upload-image')
    switch (uploadImage) {
      case '':
        imageOutputType = fromFork() ? 'file' : 'registry'
        break
      case 'artifact':
        imageOutputType = 'file'
        break
      case 'registry':
        imageOutputType = 'registry'
        break
      default:
        core.setFailed(`unknown upload-image input: ${uploadImage}`)
        return
    }
    const buildPlans = await planBuild(workingDir, id, imageOutputType)
    const plan: Plan = {
      working_directory: workingDir,
      build: buildPlans
    }
    core.info(`Generated workflow plan: ${JSON.stringify(plan, null, 2)}`)
    const artifact = new DefaultArtifactClient()
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'plan-'))
    const pathFile = path.join(tmp, 'plan.json')
    const planJson = JSON.stringify(plan, null, 2)
    fs.writeFileSync(pathFile, planJson)
    await artifact.uploadArtifact(
      sanitizeArtifactName(`${id}__plan`),
      [pathFile],
      tmp,
      {}
    )
    core.setOutput('plan', planJson)
  } catch (error) {
    // Fail the workflow run if an error occurs
    if (error instanceof Error) core.setFailed(error.message)
  }
}

run()
