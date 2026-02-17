// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.

import * as core from '@actions/core'

import * as github from '@actions/github'
import { mkdtemp, normalizePath } from './utils'
import { Plan } from './model'
import { DefaultArtifactClient } from '@actions/artifact'
import fs from 'fs'
import path from 'path'

export class GetPlan {
  private token: string
  private octokit
  private workflowFile: string
  private artifact
  private workingDir: string
  private workflowRunId: string
  private identifier: string

  constructor() {
    this.token = core.getInput('github-token')
    this.octokit = github.getOctokit(this.token)
    this.workflowFile = core.getInput('workflow-file')
    this.workingDir = core.getInput('working-directory')
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
      const tmp = mkdtemp()
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
        normalizePath(this.workingDir) ===
        normalizePath(plan.working_directory) ||
        normalizePath(this.workingDir).startsWith(
          normalizePath(plan.working_directory) + '/'
        )
      ) {
        return plan
      }
    }
    throw new Error(`can't find plan artifact for workflow run ${runId}`)
  }

  async run() {
    try {
      core.startGroup('retrieve image info')
      const runId = await this.findWorkflowRunId()
      const plan = await this.getPlan(runId)
      core.endGroup()
      core.setOutput('plan', JSON.stringify(plan))
      core.setOutput('run-id', String(runId))
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
new GetPlan().run()
