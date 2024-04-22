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
  return path.normalize(p).replace(/\/$/, '')
}

function sanitizeArtifactName(name: string): string {
  return name.replace(/[:\/\\"<>|*?]/, '-')
}

function fromFork(): boolean {
  const context = github.context
  if (context.payload.action == 'pull_request') {
    return false
  }
  // @ts-ignore
  return context.repo.owner !== context.payload.pull_request.head.repo.owner
}

async function planBuildCharm(workingDir: string): Promise<BuildPlan[]> {
  const charmcraftFiles = await (
    await glob.create(path.join(workingDir, '**', 'charmcraft.yaml'))
  ).glob()
  return charmcraftFiles.map((file: string) => {
    const charmcraft = yaml.load(fs.readFileSync(file, { encoding: 'utf-8' }))
    // @ts-ignore
    const name = charmcraft['name']
    return {
      type: 'charm',
      name,
      source_file: file,
      source_directory: path.dirname(file),
      output_type: 'file',
      output: `${workingDir}__build__output__charm__${name}`
    }
  })
}

async function planBuildRock(workingDir: string): Promise<BuildPlan[]> {
  const rockcraftFiles = await (
    await glob.create(path.join(workingDir, '**', 'rockcraft.yaml'))
  ).glob()
  return rockcraftFiles.map((file: string) => {
    const rockcraft = yaml.load(fs.readFileSync(file, { encoding: 'utf-8' }))
    // @ts-ignore
    const name = rockcraft['name']
    return {
      type: 'rock',
      name,
      source_file: file,
      source_directory: path.dirname(file),
      output_type: fromFork() ? 'file' : 'registry',
      output: `${workingDir}__build__output__rock__${name}`
    }
  })
}

async function planBuildDockerImage(workingDir: string): Promise<BuildPlan[]> {
  const dockerFiles = await (
    await glob.create(path.join(workingDir, '**', '*.Dockerfile'))
  ).glob()
  return dockerFiles.map((file: string) => {
    const name = path.basename(file).replace(/.Dockerfile$/, '')
    return {
      type: 'docker-image',
      name,
      source_file: file,
      source_directory: path.dirname(file),
      output_type: fromFork() ? 'file' : 'registry',
      output: `${workingDir}__build__output__docker-image__${name}`
    }
  })
}

async function planBuild(workingDir: string): Promise<BuildPlan[]> {
  return [
    ...(await planBuildCharm(workingDir)),
    ...(await planBuildRock(workingDir)),
    ...(await planBuildDockerImage(workingDir))
  ]
}

export async function run(): Promise<void> {
  try {
    const workingDir: string = normalizePath(core.getInput('working-directory'))
    const buildPlans = await planBuild(workingDir)
    const plan: Plan = {
      working_directory: workingDir,
      build: buildPlans
    }
    core.info(`generate workflow plan: ${JSON.stringify(plan, null, 2)}`)
    const artifact = new DefaultArtifactClient()
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'plan-'))
    fs.writeFileSync(path.join(tmp, 'plan.json'), JSON.stringify(plan, null, 2))
    await artifact.uploadArtifact(`${workingDir}__plan`, ['plan.json'], tmp)
  } catch (error) {
    // Fail the workflow run if an error occurs
    if (error instanceof Error) core.setFailed(error.message)
  }
}

// eslint-disable-next-line @typescript-eslint/no-floating-promises
run()
