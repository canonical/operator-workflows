import * as core from '@actions/core'
import * as glob from '@actions/glob'
import * as path from 'path'
import * as yaml from 'js-yaml'
import * as fs from 'fs'
import * as github from '@actions/github'
import { Plan, BuildPlan } from './model'
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
  return true
  if (context.payload.action !== 'pull_request') {
    return false
  }
  // @ts-ignore
  return context.repo.owner !== context.payload.pull_request.head.repo.owner
}

async function planBuildCharm(
  workingDir: string,
  id: string
): Promise<BuildPlan[]> {
  const charmcraftFiles = await (
    await glob.create(path.join(workingDir, '**', 'charmcraft.yaml'))
  ).glob()
  return charmcraftFiles.map((charmcraftFile: string) => {
    const file = path.join(
      workingDir,
      path.relative(workingDir, charmcraftFile)
    )
    const charmcraft = yaml.load(
      fs.readFileSync(charmcraftFile, { encoding: 'utf-8' })
    ) as object
    // @ts-ignore
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
      output_type: 'file',
      output: sanitizeArtifactName(`${id}__build__output__charm__${name}`)
    }
  })
}

async function planBuildRock(
  workingDir: string,
  id: string
): Promise<BuildPlan[]> {
  const rockcraftFiles = await (
    await glob.create(path.join(workingDir, '**', 'rockcraft.yaml'))
  ).glob()
  return rockcraftFiles.map((rockcraftFile: string) => {
    const file = path.join(workingDir, path.relative(workingDir, rockcraftFile))
    const rockcraft = yaml.load(
      fs.readFileSync(rockcraftFile, { encoding: 'utf-8' })
    )
    // @ts-ignore
    const name = rockcraft['name']
    return {
      type: 'rock',
      name,
      source_file: file,
      source_directory: path.dirname(file),
      output_type: fromFork() ? 'file' : 'registry',
      output: sanitizeArtifactName(`${id}__build__output__rock__${name}`)
    }
  })
}

async function planBuildDockerImage(
  workingDir: string,
  id: string
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
      output_type: fromFork() ? 'file' : 'registry',
      output: sanitizeArtifactName(
        `${id}__build__output__docker-image__${name}`
      )
    }
  })
}

async function planBuild(workingDir: string, id: string): Promise<BuildPlan[]> {
  return [
    ...(await planBuildCharm(workingDir, id)),
    ...(await planBuildRock(workingDir, id)),
    ...(await planBuildDockerImage(workingDir, id))
  ]
}

export async function run(): Promise<void> {
  try {
    let id = `${new Date().toISOString().replaceAll(':', '-').replace(/\..+/, '')}-${crypto.randomUUID().split('-')[3]}`
    const identity = core.getInput('identity')
    if (identity) {
      id = `${id}-${identity}`
    }
    const workingDir: string = normalizePath(core.getInput('working-directory'))
    const buildPlans = await planBuild(workingDir, id)
    const plan: Plan = {
      working_directory: workingDir,
      build: buildPlans
    }
    core.info(`generate workflow plan: ${JSON.stringify(plan, null, 2)}`)
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

// eslint-disable-next-line @typescript-eslint/no-floating-promises
run()
