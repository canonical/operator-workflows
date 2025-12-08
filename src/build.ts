// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'
import * as exec from '@actions/exec'
import * as glob from '@actions/glob'
import * as cache from '@actions/cache'
import * as github from '@actions/github'

import { BuildPlan } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import path from 'path'
import os from 'os'

async function installSnapcraft(): Promise<void> {
  const snapcraftInfo = (
    await exec.getExecOutput('snap', ['info', 'snapcraft'])
  ).stdout
  if (snapcraftInfo.includes('installed')) {
    return
  }
  await exec.exec('sudo', ['snap', 'install', 'snapcraft', '--classic'])
}

interface BuildCharmParams {
  plan: BuildPlan
  charmcraftChannel: string
}

async function gitTreeId(p: string): Promise<string> {
  const gitPath = path.resolve(p) == path.resolve(process.cwd()) ? '' : p
  const tree = (
    await exec.getExecOutput('git', ['rev-parse', `HEAD:${gitPath}`])
  ).stdout.trim()
  if (!tree) {
    throw new Error(`failed to get git tree id for path: ${p}`)
  }
  return tree
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
  } else {
    await exec.exec('sudo', ['snap', 'install', 'charmcraft', '--classic'])
  }
  core.startGroup('charmcraft pack')
  const charmcraftBin = core.getBooleanInput('charmcraftcache')
    ? 'ccc'
    : 'charmcraft'
  await exec.exec(charmcraftBin, ['pack', '--verbosity', 'trace'], {
    cwd: params.plan.source_directory,
    env: { ...process.env, CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS: 'true' }
  })
  core.endGroup()
  const charmFiles = await (
    await glob.create(path.join(params.plan.source_directory, '*.charm'))
  ).glob()
  const artifact = new DefaultArtifactClient()
  const manifestFile = path.join(params.plan.source_directory, 'manifest.json')
  fs.writeFileSync(
    manifestFile,
    JSON.stringify(
      { name: params.plan.name, files: charmFiles.map(f => path.basename(f)) },
      null,
      2
    )
  )
  await artifact.uploadArtifact(
    params.plan.output,
    [...charmFiles, manifestFile],
    params.plan.source_directory
  )
}

interface BuildDockerImageParams {
  plan: BuildPlan
  user: string
  token: string
}

async function buildFileResource(plan: BuildPlan): Promise<void> {
  core.startGroup(`Build resource ${plan.name}`)
  if (!plan.build_target) {
    throw new Error('build_target is required for file resources')
  }
  await exec.exec(`./${plan.source_file}`, [plan.build_target], {
    cwd: plan.source_directory
  })
  core.endGroup()
  const resourceFiles = await (
    await glob.create(path.join(plan.source_directory, plan.build_target))
  ).glob()
  const artifact = new DefaultArtifactClient()
  const manifestFile = path.join(plan.source_directory, 'manifest.json')
  fs.writeFileSync(
    manifestFile,
    JSON.stringify(
      { name: plan.name, files: resourceFiles.map(f => path.basename(f)) },
      null,
      2
    )
  )
  await artifact.uploadArtifact(
    plan.output,
    [...resourceFiles, manifestFile],
    plan.source_directory
  )
}

async function buildDockerImage({
  plan,
  user,
  token
}: BuildDockerImageParams): Promise<void> {
  const tag = await gitTreeId(plan.source_directory)
  const imageName = `${plan.name}:${tag}`
  await exec.exec(
    'docker',
    [
      'build',
      '-t',
      imageName,
      '-f',
      path.relative(plan.source_directory, plan.source_file),
      '.'
    ],
    { cwd: plan.source_directory }
  )
  const artifact = new DefaultArtifactClient()
  const manifest = path.join(plan.source_directory, 'manifest.json')
  if (plan.output_type == 'file') {
    const file = `${plan.name}-${tag}.tar`
    fs.writeFileSync(
      manifest,
      JSON.stringify({ name: plan.name, files: [file] }, null, 2)
    )
    await exec.exec('docker', ['save', '-o', file, imageName], {
      cwd: plan.source_directory
    })
    await artifact.uploadArtifact(
      plan.output,
      [manifest, path.join(plan.source_directory, file)],
      plan.source_directory
    )
  }
  if (plan.output_type == 'registry') {
    await exec.exec(
      `docker`,
      ['login', '-u', user, '--password-stdin', 'ghcr.io'],
      { input: Buffer.from(`${token}\n`, 'utf-8') }
    )
    const registryImageName = `ghcr.io/${github.context.repo.owner}/${imageName}`
    await exec.exec(`docker`, ['image', 'tag', imageName, registryImageName])
    await exec.exec('docker', ['push', registryImageName])
    fs.writeFileSync(
      manifest,
      JSON.stringify({ name: plan.name, images: [registryImageName] }, null, 2)
    )
    await artifact.uploadArtifact(
      plan.output,
      [manifest],
      plan.source_directory
    )
  }
}

async function buildInstallRockcraft(
  repository: string,
  ref: string
): Promise<void> {
  const workingDir = '/opt/operator-workflows/rockcraft'
  await exec.exec('sudo', ['mkdir', workingDir, '-p'])
  await exec.exec('sudo', ['chown', os.userInfo().username, workingDir])
  await exec.exec('git', [
    'clone',
    `https://github.com/${repository}.git`,
    '--branch',
    ref,
    workingDir
  ])
  const rockcraftSha = (
    await exec.getExecOutput('git', ['rev-parse', 'HEAD'], { cwd: workingDir })
  ).stdout.trim()
  const cacheKey = `rockcraft-${rockcraftSha}`
  const rockcraftGlob = path.join(workingDir, 'rockcraft*.snap')
  const restored = await cache.restoreCache([rockcraftGlob], cacheKey)
  if (!restored) {
    await installSnapcraft()
    core.startGroup('snapcraft pack (rockcraft)')
    await exec.exec('snapcraft', ['--use-lxd', '--verbosity', 'trace'], {
      cwd: workingDir
    })
    core.endGroup()
  }
  const rockcraftSnaps = await (await glob.create(rockcraftGlob)).glob()
  if (rockcraftSnaps.length == 0) {
    throw new Error("can't find rockcraft snap")
  }
  await exec.exec('sudo', [
    'snap',
    'install',
    rockcraftSnaps[0],
    '--classic',
    '--dangerous'
  ])
  if (!restored) {
    await cache.saveCache([rockcraftGlob], cacheKey)
  }
}

interface BuildRockParams {
  plan: BuildPlan
  rockcraftChannel: string
  rockcraftRepository: string
  rockcraftRef: string
  user: string
  token: string
}

function weekNumber(date: Date): number {
  date = new Date(date.valueOf())
  const dayNumber = (date.getDay() + 6) % 7
  date.setDate(date.getDate() - dayNumber + 3)
  const firstThursday = date.valueOf()
  date.setMonth(0, 1)
  if (date.getDay() !== 4) {
    date.setMonth(0, 1 + ((4 - date.getDay() + 7) % 7))
  }
  return 1 + Math.ceil((firstThursday - date.valueOf()) / 604800000)
}

async function generateRockCacheKey(plan: BuildPlan): Promise<string> {
  const base = 'https://example.com/'
  const url = new URL(
    path.join('operator-workflows/build/rock/', plan.source_file),
    base
  )
  const sp = url.searchParams
  const date = new Date()
  const params: { [key: string]: string } = {
    arch: process.arch,
    version: '1',
    hash: await glob.hashFiles(path.join(plan.source_directory, '**')),
    'used-by': `${date.getFullYear()}-W${String(weekNumber(date)).padStart(2, '0')}`
  }
  Object.keys(params)
    .sort()
    .forEach(k => sp.set(k, params[k]))
  return url.toString().replace(base, '')
}

async function isPaasCharmRock(plan: BuildPlan): Promise<boolean> {
  const patterns = [
    `${plan.source_directory}/**/charmcraft.yaml`,
    `${plan.source_directory}/**/charmcraft.yml`
  ]
  const charmcraftGlob = await glob.create(patterns.join('\n'))
  const charmcraftFiles = await charmcraftGlob.glob()
  return charmcraftFiles.length > 0
}

async function restoreRock(plan: BuildPlan): Promise<boolean> {
  // We don't cache rocks inside 12-factor projects
  // as they change more frequently compared to normal charms.
  // And we only cache registry-typed rocks as they are more common
  // and their cache are smaller.
  if ((await isPaasCharmRock(plan)) || plan.output_type !== 'registry') {
    return false
  }
  const key = await generateRockCacheKey(plan)
  core.info(`looking for rock cache ${key}`)
  const manifestFile = path.join(plan.source_directory, 'manifest.json')
  const restored = await cache.restoreCache([manifestFile], key)
  if (restored) {
    core.info(`restored rock cache from ${key}`)
    const artifact = new DefaultArtifactClient()
    await artifact.uploadArtifact(
      plan.output,
      [manifestFile],
      plan.source_directory
    )
    return true
  }
  return false
}

async function cacheRock(plan: BuildPlan): Promise<void> {
  if ((await isPaasCharmRock(plan)) || plan.output_type !== 'registry') {
    return
  }
  const key = await generateRockCacheKey(plan)
  const manifestFile = path.join(plan.source_directory, 'manifest.json')
  core.info(`caching rock into ${key}`)
  await cache.saveCache([manifestFile], key)
}

async function buildRock({
  plan,
  rockcraftChannel,
  rockcraftRepository,
  rockcraftRef,
  user,
  token
}: BuildRockParams): Promise<void> {
  if (await restoreRock(plan)) {
    return
  }
  if (rockcraftRepository && rockcraftRef) {
    await buildInstallRockcraft(rockcraftRepository, rockcraftRef)
  } else if (rockcraftChannel) {
    await exec.exec('sudo', [
      'snap',
      'install',
      'rockcraft',
      '--channel',
      rockcraftChannel,
      '--classic'
    ])
  } else {
    await exec.exec('sudo', ['snap', 'install', 'rockcraft', '--classic'])
  }
  if (path.basename(plan.source_file) != 'rockcraft.yaml') {
    const rockcraftYamlFile = path.join(
      path.dirname(plan.source_file),
      'rockcraft.yaml'
    )
    core.info(`rename ${plan.source_file} to ${rockcraftYamlFile}`)
    fs.renameSync(plan.source_file, rockcraftYamlFile)
  }
  core.startGroup('rockcraft pack')
  await exec.exec('rockcraft', ['pack', '--verbosity', 'trace'], {
    cwd: plan.source_directory,
    env: { ...process.env, ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS: 'true' }
  })
  core.endGroup()
  const rocks = await (
    await glob.create(path.join(plan.source_directory, '*.rock'))
  ).glob()
  const manifestFile = path.join(plan.source_directory, 'manifest.json')
  const artifact = new DefaultArtifactClient()
  if (plan.output_type === 'file') {
    fs.writeFileSync(
      manifestFile,
      JSON.stringify(
        {
          name: plan.name,
          files: rocks.map(f => path.basename(f))
        },
        null,
        2
      )
    )
    await artifact.uploadArtifact(
      plan.output,
      [...rocks, manifestFile],
      plan.source_directory
    )
  } else {
    const tree = await gitTreeId(plan.source_directory)
    const images = await Promise.all(
      rocks.map(async f => {
        const base = path
          .basename(f)
          .substring(plan.name.length)
          .replace(/\.rock$/, '')
        const image = `ghcr.io/${github.context.repo.owner}/${plan.name}:${tree}-${base}`
        await exec.exec(
          '/snap/rockcraft/current/bin/skopeo',
          [
            '--insecure-policy',
            'copy',
            `oci-archive:${path.basename(f)}`,
            `docker://${image}`,
            '--dest-creds',
            `${user}:${token}`
          ],
          { cwd: plan.source_directory }
        )
        return image
      })
    )
    fs.writeFileSync(
      manifestFile,
      JSON.stringify(
        {
          name: plan.name,
          images: images
        },
        null,
        2
      )
    )
    await cacheRock(plan)
    await artifact.uploadArtifact(
      plan.output,
      [manifestFile],
      plan.source_directory
    )
  }
}

export async function run(): Promise<void> {
  try {
    const plan: BuildPlan = JSON.parse(core.getInput('build-plan'))
    switch (plan.type) {
      case 'charm':
        await buildCharm({
          plan,
          charmcraftChannel: core.getInput('charmcraft-channel')
        })
        break
      case 'docker-image':
        await buildDockerImage({
          plan,
          user: github.context.actor,
          token: core.getInput('github-token')
        })
        break
      case 'rock':
        await buildRock({
          plan,
          rockcraftChannel: core.getInput('rockcraft-channel'),
          rockcraftRef: core.getInput('rockcraft-ref'),
          rockcraftRepository: core.getInput('rockcraft-repository'),
          user: github.context.actor,
          token: core.getInput('github-token')
        })
        break
      case 'file':
        await buildFileResource(plan)
        break
    }
  } catch (error) {
    // Fail the workflow run if an error occurs
    if (error instanceof Error) core.setFailed(error.message)
  }
}

// eslint-disable-next-line @typescript-eslint/no-floating-promises
run()
