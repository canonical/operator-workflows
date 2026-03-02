// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.
Object.defineProperty(exports, "__esModule", { value: true });
exports.run = run;
const tslib_1 = require("tslib");
const core = tslib_1.__importStar(require("@actions/core"));
const exec = tslib_1.__importStar(require("@actions/exec"));
const glob = tslib_1.__importStar(require("@actions/glob"));
const cache = tslib_1.__importStar(require("@actions/cache"));
const github = tslib_1.__importStar(require("@actions/github"));
const artifact_1 = require("@actions/artifact");
const fs_1 = tslib_1.__importDefault(require("fs"));
const path_1 = tslib_1.__importDefault(require("path"));
const os_1 = tslib_1.__importDefault(require("os"));
async function installSnapcraft() {
    const snapcraftInfo = (await exec.getExecOutput('snap', ['info', 'snapcraft'])).stdout;
    if (snapcraftInfo.includes('installed')) {
        return;
    }
    await exec.exec('sudo', ['snap', 'install', 'snapcraft', '--classic']);
}
async function gitTreeId(p) {
    const gitPath = path_1.default.resolve(p) == path_1.default.resolve(process.cwd()) ? '' : p;
    const tree = (await exec.getExecOutput('git', ['rev-parse', `HEAD:${gitPath}`])).stdout.trim();
    if (!tree) {
        throw new Error(`failed to get git tree id for path: ${p}`);
    }
    return tree;
}
async function buildCharm(params) {
    if (params.charmcraftChannel) {
        await exec.exec('sudo', [
            'snap',
            'install',
            'charmcraft',
            '--channel',
            params.charmcraftChannel,
            '--classic'
        ]);
    }
    else {
        await exec.exec('sudo', ['snap', 'install', 'charmcraft', '--classic']);
    }
    core.startGroup('charmcraft pack');
    const charmcraftBin = core.getBooleanInput('charmcraftcache')
        ? 'ccc'
        : 'charmcraft';
    await exec.exec(charmcraftBin, ['pack', '--verbosity', 'trace'], {
        cwd: params.plan.source_directory,
        env: { ...process.env, CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS: 'true' }
    });
    core.endGroup();
    const charmFiles = await (await glob.create(path_1.default.join(params.plan.source_directory, '*.charm'))).glob();
    const artifact = new artifact_1.DefaultArtifactClient();
    const manifestFile = path_1.default.join(params.plan.source_directory, 'manifest.json');
    fs_1.default.writeFileSync(manifestFile, JSON.stringify({ name: params.plan.name, files: charmFiles.map(f => path_1.default.basename(f)) }, null, 2));
    await artifact.uploadArtifact(params.plan.output, [...charmFiles, manifestFile], params.plan.source_directory);
}
async function buildFileResource(plan) {
    core.startGroup(`Build resource ${plan.name}`);
    if (!plan.build_target) {
        throw new Error('build_target is required for file resources');
    }
    await exec.exec(`./${plan.source_file}`, [plan.build_target], {
        cwd: plan.source_directory
    });
    core.endGroup();
    const resourceFiles = await (await glob.create(path_1.default.join(plan.source_directory, plan.build_target))).glob();
    const artifact = new artifact_1.DefaultArtifactClient();
    const manifestFile = path_1.default.join(plan.source_directory, 'manifest.json');
    fs_1.default.writeFileSync(manifestFile, JSON.stringify({ name: plan.name, files: resourceFiles.map(f => path_1.default.basename(f)) }, null, 2));
    await artifact.uploadArtifact(plan.output, [...resourceFiles, manifestFile], plan.source_directory);
}
async function buildDockerImage({ plan, user, token }) {
    const tag = await gitTreeId(plan.source_directory);
    const imageName = `${plan.name}:${tag}`;
    await exec.exec('docker', [
        'build',
        '-t',
        imageName,
        '-f',
        path_1.default.relative(plan.source_directory, plan.source_file),
        '.'
    ], { cwd: plan.source_directory });
    const artifact = new artifact_1.DefaultArtifactClient();
    const manifest = path_1.default.join(plan.source_directory, 'manifest.json');
    if (plan.output_type == 'file') {
        const file = `${plan.name}-${tag}.tar`;
        fs_1.default.writeFileSync(manifest, JSON.stringify({ name: plan.name, files: [file] }, null, 2));
        await exec.exec('docker', ['save', '-o', file, imageName], {
            cwd: plan.source_directory
        });
        await artifact.uploadArtifact(plan.output, [manifest, path_1.default.join(plan.source_directory, file)], plan.source_directory);
    }
    if (plan.output_type == 'registry') {
        await exec.exec(`docker`, ['login', '-u', user, '--password-stdin', 'ghcr.io'], { input: Buffer.from(`${token}\n`, 'utf-8') });
        const registryImageName = `ghcr.io/${github.context.repo.owner}/${imageName}`;
        await exec.exec(`docker`, ['image', 'tag', imageName, registryImageName]);
        await exec.exec('docker', ['push', registryImageName]);
        fs_1.default.writeFileSync(manifest, JSON.stringify({ name: plan.name, images: [registryImageName] }, null, 2));
        await artifact.uploadArtifact(plan.output, [manifest], plan.source_directory);
    }
}
async function buildInstallRockcraft(repository, ref) {
    const workingDir = '/opt/operator-workflows/rockcraft';
    await exec.exec('sudo', ['mkdir', workingDir, '-p']);
    await exec.exec('sudo', ['chown', os_1.default.userInfo().username, workingDir]);
    await exec.exec('git', [
        'clone',
        `https://github.com/${repository}.git`,
        '--branch',
        ref,
        workingDir
    ]);
    const rockcraftSha = (await exec.getExecOutput('git', ['rev-parse', 'HEAD'], { cwd: workingDir })).stdout.trim();
    const cacheKey = `rockcraft-${rockcraftSha}`;
    const rockcraftGlob = path_1.default.join(workingDir, 'rockcraft*.snap');
    const restored = await cache.restoreCache([rockcraftGlob], cacheKey);
    if (!restored) {
        await installSnapcraft();
        core.startGroup('snapcraft pack (rockcraft)');
        await exec.exec('snapcraft', ['--use-lxd', '--verbosity', 'trace'], {
            cwd: workingDir
        });
        core.endGroup();
    }
    const rockcraftSnaps = await (await glob.create(rockcraftGlob)).glob();
    if (rockcraftSnaps.length == 0) {
        throw new Error("can't find rockcraft snap");
    }
    await exec.exec('sudo', [
        'snap',
        'install',
        rockcraftSnaps[0],
        '--classic',
        '--dangerous'
    ]);
    if (!restored) {
        await cache.saveCache([rockcraftGlob], cacheKey);
    }
}
async function buildRock({ plan, rockcraftChannel, rockcraftRepository, rockcraftRef, user, token }) {
    if (rockcraftRepository && rockcraftRef) {
        await buildInstallRockcraft(rockcraftRepository, rockcraftRef);
    }
    else if (rockcraftChannel) {
        await exec.exec('sudo', [
            'snap',
            'install',
            'rockcraft',
            '--channel',
            rockcraftChannel,
            '--classic'
        ]);
    }
    else {
        await exec.exec('sudo', ['snap', 'install', 'rockcraft', '--classic']);
    }
    if (path_1.default.basename(plan.source_file) != 'rockcraft.yaml') {
        const rockcraftYamlFile = path_1.default.join(path_1.default.dirname(plan.source_file), 'rockcraft.yaml');
        core.info(`rename ${plan.source_file} to ${rockcraftYamlFile}`);
        fs_1.default.renameSync(plan.source_file, rockcraftYamlFile);
    }
    core.startGroup('rockcraft pack');
    await exec.exec('rockcraft', ['pack', '--verbosity', 'trace'], {
        cwd: plan.source_directory,
        env: { ...process.env, ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS: 'true' }
    });
    core.endGroup();
    const rocks = await (await glob.create(path_1.default.join(plan.source_directory, '*.rock'))).glob();
    const manifestFile = path_1.default.join(plan.source_directory, 'manifest.json');
    const artifact = new artifact_1.DefaultArtifactClient();
    if (plan.output_type === 'file') {
        fs_1.default.writeFileSync(manifestFile, JSON.stringify({
            name: plan.name,
            files: rocks.map(f => path_1.default.basename(f))
        }, null, 2));
        await artifact.uploadArtifact(plan.output, [...rocks, manifestFile], plan.source_directory);
    }
    else {
        const tree = await gitTreeId(plan.source_directory);
        const images = await Promise.all(rocks.map(async (f) => {
            const base = path_1.default
                .basename(f)
                .substring(plan.name.length)
                .replace(/\.rock$/, '');
            const image = `ghcr.io/${github.context.repo.owner}/${plan.name}:${tree}-${base}`;
            await exec.exec('/snap/rockcraft/current/bin/skopeo', [
                '--insecure-policy',
                'copy',
                `oci-archive:${path_1.default.basename(f)}`,
                `docker://${image}`,
                '--dest-creds',
                `${user}:${token}`
            ], { cwd: plan.source_directory });
            return image;
        }));
        fs_1.default.writeFileSync(manifestFile, JSON.stringify({
            name: plan.name,
            images: images
        }, null, 2));
        await artifact.uploadArtifact(plan.output, [manifestFile], plan.source_directory);
    }
}
async function run() {
    try {
        const plan = JSON.parse(core.getInput('build-plan'));
        switch (plan.type) {
            case 'charm':
                await buildCharm({
                    plan,
                    charmcraftChannel: core.getInput('charmcraft-channel')
                });
                break;
            case 'docker-image':
                await buildDockerImage({
                    plan,
                    user: github.context.actor,
                    token: core.getInput('github-token')
                });
                break;
            case 'rock':
                await buildRock({
                    plan,
                    rockcraftChannel: core.getInput('rockcraft-channel'),
                    rockcraftRef: core.getInput('rockcraft-ref'),
                    rockcraftRepository: core.getInput('rockcraft-repository'),
                    user: github.context.actor,
                    token: core.getInput('github-token')
                });
                break;
            case 'file':
                await buildFileResource(plan);
                break;
        }
    }
    catch (error) {
        // Fail the workflow run if an error occurs
        if (error instanceof Error)
            core.setFailed(error.message);
    }
}
run();
//# sourceMappingURL=index.js.map
