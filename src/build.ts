import * as core from '@actions/core'
import * as exec from '@actions/exec'
import * as glob from '@actions/glob'
import * as cache from '@actions/cache'

import { BuildPlan, Plan } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import path from 'path'
import os from 'os'

async function installSnapcraft(): Promise<void> {
  const versionCheck = await exec.exec('snapcraft', ['--version'], {
    ignoreReturnCode: true
  })
  if (versionCheck === 0) {
    return
  }
  await exec.exec('sudo', ['snap', 'install', 'snapcraft'])
}

async function buildInstallCharmcraft(
  repository: string,
  ref: string
): Promise<void> {
  const workingDir = '/opt/operator-workflows/charmcraft'
  await exec.exec('sudo', ['mkdir', workingDir, '-p'])
  await exec.exec('sudo', ['chown', os.userInfo().username, workingDir])
  await exec.exec('git', [
    'clone',
    `https://github.com/${repository}.git`,
    '--branch',
    ref,
    workingDir
  ])
  const charmcraftSha = (
    await exec.getExecOutput('git', ['rev-parse', 'HEAD'])
  ).stdout.trim()
  const cacheKey = `charmcraft-${charmcraftSha}`
  const charmcraftGlob = path.join(workingDir, 'charmcraft*.snap')
  const restored = await cache.restoreCache([charmcraftGlob], cacheKey)
  if (!restored) {
    await installSnapcraft()
    await exec.exec('snapcraft', ['--use-lxd', '--verbosity', 'trace'], {
      cwd: workingDir
    })
  }
  const charmcraftSnaps = await (await glob.create(charmcraftGlob)).glob()
  if (charmcraftSnaps.length == 0) {
    throw new Error('can\'t find charmcraft snap')
  }
  await exec.exec('sudo', [
    'snap',
    'install',
    charmcraftSnaps[0],
    '--classic',
    '--dangerous'
  ])
  if (!restored) {
    await cache.saveCache([charmcraftGlob], cacheKey)
  }
}

interface BuildCharmParams {
  plan: BuildPlan
  charmcraftChannel: string
  charmcraftRepository: string
  charmcraftRef: string
}

async function buildCharm(params: BuildCharmParams): Promise<void> {
  if (params.charmcraftChannel) {
    await exec.exec('sudo', [
      'snap',
      'install',
      'charmcraft',
      '--channel',
      params.charmcraftChannel,
      '--classic'
    ])
  } else if (params.charmcraftRepository && params.charmcraftRef) {
    await buildInstallCharmcraft(
      params.charmcraftRepository,
      params.charmcraftRef
    )
  } else {
    await exec.exec('sudo', ['snap', 'install', 'charmcraft', '--classic'])
  }
  await exec.exec('charmcraft', ['pack', '--verbosity', 'trace'], { cwd: params.plan.source_directory })
  const charmFiles = await (await glob.create(path.join(params.plan.source_directory, '*.charm'))).glob()
  const artifact = new DefaultArtifactClient()
  const manifestFile = path.join(params.plan.source_directory, 'manifest.json')
  fs.writeFileSync(
    manifestFile,
    JSON.stringify({ name: params.plan.name, files: charmFiles }, null, 2)
  )
  await artifact.uploadArtifact(
    params.plan.output,
    [...charmFiles, manifestFile],
    params.plan.source_directory
  )
}

export async function run(): Promise<void> {
  try {
    const plan: BuildPlan = JSON.parse(core.getInput('plan'))
    const charmcraftRepository = core.getInput('charmcraft-repository')
    const charmcraftRef = core.getInput('charmcraft-ref')
    const charmcraftChannel = core.getInput('charmcraft-channel')
    switch (plan.type) {
      case 'charm':
        await buildCharm({
          plan,
          charmcraftChannel,
          charmcraftRef,
          charmcraftRepository
        })
    }
  } catch (error) {
    // Fail the workflow run if an error occurs
    if (error instanceof Error) core.setFailed(error.message)
  }
}

// eslint-disable-next-line @typescript-eslint/no-floating-promises
run()
