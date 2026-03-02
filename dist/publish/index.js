// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const core = tslib_1.__importStar(require("@actions/core"));
const exec = tslib_1.__importStar(require("@actions/exec"));
const yaml = tslib_1.__importStar(require("js-yaml"));
const github = tslib_1.__importStar(require("@actions/github"));
const utils_1 = require("./utils");
const artifact_1 = require("@actions/artifact");
const fs_1 = tslib_1.__importDefault(require("fs"));
const path_1 = tslib_1.__importDefault(require("path"));
class Publish {
    token;
    charmhubToken;
    artifact;
    workingDir;
    resourceMapping;
    constructor() {
        this.token = core.getInput('github-token');
        this.charmhubToken = core.getInput('charmhub-token');
        this.workingDir = core.getInput('working-directory');
        this.resourceMapping = JSON.parse(core.getInput('resource-mapping'));
        this.artifact = new artifact_1.DefaultArtifactClient();
    }
    async getCharmResources() {
        let cwd = this.workingDir;
        // FIXME: search current working directory and the ./charm directory for charm directory
        if (!fs_1.default.existsSync(path_1.default.join(this.workingDir, 'charmcraft.yaml'))) {
            cwd = path_1.default.join(this.workingDir, 'charm');
        }
        let metadata = yaml.load((await exec.getExecOutput('charmcraft', ['expand-extensions'], {
            cwd,
            env: {
                CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS: 'true',
                ...process.env
            }
        })).stdout);
        if ((metadata.resources === undefined ||
            Object.keys(metadata.resources).length === 0) &&
            fs_1.default.existsSync(path_1.default.join(cwd, 'metadata.yaml'))) {
            metadata = yaml.load(fs_1.default.readFileSync(path_1.default.join(cwd, 'metadata.yaml'), {
                encoding: 'utf-8'
            }));
        }
        const resources = metadata.resources;
        if (resources === undefined) {
            return [[], []];
        }
        const images = Object.keys(resources).filter(k => resources[k].type === 'oci-image' && !resources[k]['upstream-source']);
        const files = Object.keys(resources).filter(k => resources[k].type === 'file');
        return [images, files];
    }
    async getFiles(plan, runId) {
        const [, resources] = await this.getCharmResources();
        core.info(`required resources: ${resources}`);
        const upload = new Map();
        if (resources.length === 0) {
            return upload;
        }
        for (const build of plan.build) {
            if (build.type === 'file') {
                const resourceName = this.resourceMapping[build.name];
                if (!resources.includes(resourceName)) {
                    core.info(`skip uploading file: ${build.name}`);
                    continue;
                }
                const tmp = (0, utils_1.mkdtemp)();
                const artifact = await this.artifact.getArtifact(build.output, {
                    findBy: {
                        token: this.token,
                        repositoryOwner: github.context.repo.owner,
                        repositoryName: github.context.repo.repo,
                        workflowRunId: runId
                    }
                });
                await this.artifact.downloadArtifact(artifact.artifact.id, {
                    path: tmp,
                    findBy: {
                        token: this.token,
                        repositoryOwner: github.context.repo.owner,
                        repositoryName: github.context.repo.repo,
                        workflowRunId: runId
                    }
                });
                const manifest = JSON.parse(fs_1.default.readFileSync(path_1.default.join(tmp, 'manifest.json'), {
                    encoding: 'utf-8'
                }));
                const files = manifest.files;
                if (files.length !== 1) {
                    throw new Error(`file resource ${build.name} contain multiple candidates: ${files}`);
                }
                const file = files[0];
                upload.set(resourceName, file);
            }
        }
        return upload;
    }
    async getImages(plan, runId) {
        const [resources] = await this.getCharmResources();
        core.info(`required resources: ${resources}`);
        const upload = new Map();
        if (resources.length === 0) {
            return upload;
        }
        let dockerLogin = false;
        for (const build of plan.build) {
            if (build.type === 'charm' || build.type === 'file') {
                continue;
            }
            const resourceName = Object.prototype.hasOwnProperty.call(this.resourceMapping, build.name)
                ? this.resourceMapping[build.name]
                : `${build.name}-image`;
            if (!resources.includes(resourceName)) {
                core.info(`skip uploading image: ${build.name}`);
                continue;
            }
            const tmp = (0, utils_1.mkdtemp)();
            const artifact = await this.artifact.getArtifact(build.output, {
                findBy: {
                    token: this.token,
                    repositoryOwner: github.context.repo.owner,
                    repositoryName: github.context.repo.repo,
                    workflowRunId: runId
                }
            });
            await this.artifact.downloadArtifact(artifact.artifact.id, {
                path: tmp,
                findBy: {
                    token: this.token,
                    repositoryOwner: github.context.repo.owner,
                    repositoryName: github.context.repo.repo,
                    workflowRunId: runId
                }
            });
            const manifest = JSON.parse(fs_1.default.readFileSync(path_1.default.join(tmp, 'manifest.json'), { encoding: 'utf-8' }));
            if (build.output_type === 'registry') {
                if (!dockerLogin) {
                    await exec.exec(`docker`, [
                        'login',
                        '-u',
                        github.context.actor,
                        '--password-stdin',
                        'ghcr.io'
                    ], { input: Buffer.from(`${this.token}\n`, 'utf-8') });
                    dockerLogin = true;
                }
                const images = manifest.images;
                if (images.length !== 1) {
                    throw new Error(`image resource ${build.name} contain multiple candidates: ${images}`);
                }
                const image = images[0];
                await exec.exec('docker', ['pull', image]);
                upload.set(resourceName, image);
            }
            if (build.output_type === 'file') {
                const files = manifest.files;
                if (files.length !== 1) {
                    throw new Error(`image resource ${build.name} contain multiple candidates: ${files}`);
                }
                const file = files[0];
                const image = `${build.name}:${file}`;
                const archiveType = file.endsWith('.rock')
                    ? 'oci-archive'
                    : 'docker-archive';
                await exec.exec('/snap/rockcraft/current/bin/skopeo', [
                    'copy',
                    '--insecure-policy',
                    `${archiveType}:${path_1.default.join(tmp, file)}`,
                    `docker-daemon:${image}`
                ]);
                upload.set(resourceName, image);
            }
        }
        if (upload.size != resources.length) {
            const missing = resources.filter(r => !upload.has(r));
            throw new Error(`can't find required resources: ${missing}`);
        }
        return upload;
    }
    async getCharms(plan, runId) {
        // FIXME: a workaround for paas app charms
        let charmDir = this.workingDir;
        if (fs_1.default.existsSync(path_1.default.join(charmDir, 'charm', 'charmcraft.yaml'))) {
            charmDir = path_1.default.join(charmDir, 'charm');
        }
        const charms = plan.build.filter(b => b.type === 'charm' &&
            (0, utils_1.normalizePath)(b.source_directory) === (0, utils_1.normalizePath)(charmDir));
        if (charms.length === 0) {
            throw new Error('no charm to upload');
        }
        if (charms.length > 1) {
            throw new Error(`more than one charm to upload: ${charms.map(c => c.name)}`);
        }
        const charm = charms[0];
        const tmp = (0, utils_1.mkdtemp)();
        core.info(`download charm artifact from integration workflow (run id: ${runId})`);
        const artifact = (await this.artifact.getArtifact(charm.output, {
            findBy: {
                token: this.token,
                repositoryOwner: github.context.repo.owner,
                repositoryName: github.context.repo.repo,
                workflowRunId: runId
            }
        })).artifact;
        await this.artifact.downloadArtifact(artifact.id, {
            path: tmp,
            findBy: {
                token: this.token,
                repositoryOwner: github.context.repo.owner,
                repositoryName: github.context.repo.repo,
                workflowRunId: runId
            }
        });
        const manifest = JSON.parse(fs_1.default.readFileSync(path_1.default.join(tmp, 'manifest.json'), { encoding: 'utf-8' }));
        return {
            name: manifest.name,
            dir: charm.source_directory,
            files: manifest.files.map(f => path_1.default.join(tmp, f))
        };
    }
    async run() {
        try {
            core.startGroup('retrieve image info');
            const plan = JSON.parse(core.getInput('plan'));
            const runId = +core.getInput('run-id');
            const imageResources = await this.getImages(plan, runId);
            const fileResources = await this.getFiles(plan, runId);
            core.endGroup();
            core.startGroup('retrieve charm info');
            const { name: charmName, dir: charmDir, files: charms } = await this.getCharms(plan, runId);
            core.endGroup();
            if (fileResources.size !== 0) {
                core.info(`start uploading file resources: ${JSON.stringify(Object.fromEntries([...fileResources]))}`);
            }
            for (const [resource, filePath] of fileResources) {
                core.info(`upload resource ${resource}`);
                await exec.exec('charmcraft', [
                    'upload-resource',
                    charmName,
                    resource,
                    `--filepath=${filePath}`,
                    '--verbosity=brief'
                ], { env: { ...process.env, CHARMCRAFT_AUTH: this.charmhubToken } });
            }
            if (imageResources.size !== 0) {
                core.info(`start uploading image resources: ${JSON.stringify(Object.fromEntries([...imageResources]))}`);
            }
            for (const [resource, image] of imageResources) {
                core.info(`upload resource ${resource}`);
                const imageId = (await exec.getExecOutput('docker', [
                    'images',
                    image,
                    '--format',
                    '{{.ID}}'
                ])).stdout.trim();
                await exec.exec('charmcraft', [
                    'upload-resource',
                    charmName,
                    resource,
                    `--image=${imageId}`,
                    '--verbosity=brief'
                ], { env: { ...process.env, CHARMCRAFT_AUTH: this.charmhubToken } });
            }
            core.setOutput('charms', charms.join(','));
            core.setOutput('charm-directory', charmDir);
        }
        catch (error) {
            // Fail the workflow run if an error occurs
            if (error instanceof Error) {
                core.error(`${error.message}\n${error.stack}`);
                core.setFailed(error.message);
            }
        }
    }
}
new Publish().run();
//# sourceMappingURL=index.js.map
