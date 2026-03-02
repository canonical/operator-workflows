// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.
Object.defineProperty(exports, "__esModule", { value: true });
exports.run = run;
const tslib_1 = require("tslib");
const core = tslib_1.__importStar(require("@actions/core"));
const artifact_1 = require("@actions/artifact");
const fs_1 = tslib_1.__importDefault(require("fs"));
const path_1 = tslib_1.__importDefault(require("path"));
const os_1 = tslib_1.__importDefault(require("os"));
const exec = tslib_1.__importStar(require("@actions/exec"));
const github = tslib_1.__importStar(require("@actions/github"));
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
async function waitBuild(githubToken, jobId) {
    const octokit = github.getOctokit(githubToken);
    const deadline = Date.now() + 3 * 3600 * 1000;
    while (Date.now() <= deadline) {
        await sleep(5000);
        const jobs = await octokit.paginate(octokit.rest.actions.listJobsForWorkflowRunAttempt, {
            owner: github.context.repo.owner,
            repo: github.context.repo.repo,
            run_id: github.context.runId,
            attempt_number: github.context.runAttempt,
            per_page: 100
        });
        const thisJob = jobs.find(job => job.id === jobId);
        const jobPrefix = thisJob.name.split(' / ')[0];
        core.info(`looking for build jobs under ${jobPrefix}`);
        const targetJobs = jobs.filter(j => (j.name || '').startsWith(`${jobPrefix}`) &&
            (j.name || '').includes(' / Build'));
        if (targetJobs.length === 0) {
            core.info('no build jobs');
            return;
        }
        let successes = 0;
        core.info('waiting for build jobs:');
        for (const job of targetJobs) {
            if (job.status === 'completed') {
                if (job.conclusion === 'success') {
                    core.info(`[SUCCESS] ${job.name}`);
                    successes++;
                }
                else if (job.conclusion === 'skipped') {
                    core.info(`[SKIPPED] ${job.name}`);
                    successes++;
                }
                else {
                    throw new Error(`build job ${job.name} failed with conclusion: ${job.conclusion}`);
                }
            }
            else {
                core.info(`[${job.status.toUpperCase()}] ${job.name}`);
            }
        }
        if (targetJobs.length === successes) {
            return;
        }
        else {
            // newline to increase readability
            core.info('');
        }
    }
    throw new Error('timeout waiting for build jobs');
}
async function downloadArtifact(artifact, id) {
    // When build jobs have just finished, the artifacts might not be fully available yet.
    // Retry downloading artifacts for up to 1 minute instead of immediately erroring out.
    let artifactError;
    for (let i = 0; i < 6; i++) {
        const tmp = fs_1.default.mkdtempSync(path_1.default.join(os_1.default.tmpdir(), 'artifact-'));
        try {
            await artifact.downloadArtifact(id, { path: tmp });
            return tmp;
        }
        catch (error) {
            artifactError = error;
            if (error instanceof Error) {
                core.error(`failed to download artifact: ${error.message}, retries: ${i}`);
            }
            await sleep(5000);
        }
    }
    throw artifactError;
}
async function run() {
    try {
        const plan = JSON.parse(core.getInput('plan'));
        await waitBuild(core.getInput('github-token'), Number(core.getInput('check-run-id')));
        const artifact = new artifact_1.DefaultArtifactClient();
        let args = [];
        for (const build of plan.build) {
            const tmp = await downloadArtifact(artifact, (await artifact.getArtifact(build.output)).artifact.id);
            const manifest = JSON.parse(fs_1.default.readFileSync(path_1.default.join(tmp, 'manifest.json'), { encoding: 'utf-8' }));
            if (build.type === 'charm' || build.type === 'file') {
                // @ts-ignore
                for (const file of manifest.files) {
                    fs_1.default.renameSync(path_1.default.join(tmp, file), path_1.default.join(plan.working_directory, file));
                    // @ts-ignore
                    const name = manifest.name;
                    let argName = build.type === 'charm' ? 'charm-file' : `${name}-resource`;
                    args.push(`--${argName}=./${file}`);
                }
            }
            else if (build.type === 'rock' || build.type == 'docker-image') {
                // @ts-ignore
                const name = manifest.name;
                if ('files' in manifest) {
                    for (const file of manifest.files) {
                        const image = `localhost:32000/${name}:${file.replace(`${name}_`, '')}`;
                        const archiveType = file.endsWith('.rock')
                            ? 'oci-archive'
                            : 'docker-archive';
                        await exec.exec('skopeo', [
                            'copy',
                            '--insecure-policy',
                            '--dest-tls-verify=false',
                            `${archiveType}:${path_1.default.join(tmp, file)}`,
                            `docker://${image}`
                        ]);
                        args.push(`--${name}-image=${image}`);
                    }
                }
                if ('images' in manifest) {
                    for (const image of manifest.images) {
                        args.push(`--${name}-image=${image}`);
                    }
                }
            }
        }
        core.setOutput('args', args.join(' '));
    }
    catch (error) {
        // Fail the workflow run if an error occurs
        if (error instanceof Error)
            core.setFailed(error.message);
    }
}
// eslint-disable-next-line @typescript-eslint/no-floating-promises
run();
//# sourceMappingURL=index.js.map
