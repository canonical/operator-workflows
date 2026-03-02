// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.
Object.defineProperty(exports, "__esModule", { value: true });
exports.run = run;
const tslib_1 = require("tslib");
const core = tslib_1.__importStar(require("@actions/core"));
const glob = tslib_1.__importStar(require("@actions/glob"));
const path = tslib_1.__importStar(require("path"));
const yaml = tslib_1.__importStar(require("js-yaml"));
const fs = tslib_1.__importStar(require("fs"));
const github = tslib_1.__importStar(require("@actions/github"));
const artifact_1 = require("@actions/artifact");
const os = tslib_1.__importStar(require("os"));
function normalizePath(p) {
    return path.normalize(p).replace(/\/+$/, '');
}
function sanitizeArtifactName(name) {
    return name.replaceAll(/[\t\n:/\\"<>|*?]/g, '-');
}
function fromFork() {
    const context = github.context;
    if (context.eventName !== 'pull_request') {
        return false;
    }
    return (context.repo.owner !==
        context.payload?.pull_request?.head?.repo?.owner?.login);
}
async function planBuildCharm(workingDir, id) {
    const allCharmcraftFiles = await (await glob.create(path.join(workingDir, '**', 'charmcraft.yaml'))).glob();
    const charmcraftFiles = allCharmcraftFiles.filter(file => !path.normalize(path.relative(workingDir, file)).startsWith('tests/'));
    return charmcraftFiles.map((charmcraftFile) => {
        const file = path.join(workingDir, path.relative(workingDir, charmcraftFile));
        const charmcraft = yaml.load(fs.readFileSync(charmcraftFile, { encoding: 'utf-8' }));
        let name;
        if ('name' in charmcraft) {
            name = charmcraft['name'];
        }
        else {
            const metadataFile = path.join(path.dirname(charmcraftFile), 'metadata.yaml');
            const metadata = yaml.load(fs.readFileSync(metadataFile, { encoding: 'utf-8' }));
            if (!('name' in metadata)) {
                throw new Error(`unknown charm name (${workingDir})`);
            }
            name = metadata['name'];
        }
        return {
            type: 'charm',
            name,
            source_file: file,
            source_directory: path.dirname(file),
            build_target: undefined,
            output_type: 'file',
            output: sanitizeArtifactName(`${id}__build__output__charm__${name}`)
        };
    });
}
async function planBuildRock(workingDir, id, outputType) {
    const rockcraftFiles = await (await glob.create(path.join(workingDir, '**', '*rockcraft.yaml'))).glob();
    return rockcraftFiles.map((rockcraftFile) => {
        const file = path.join(workingDir, path.relative(workingDir, rockcraftFile));
        const rockcraft = yaml.load(fs.readFileSync(rockcraftFile, { encoding: 'utf-8' }));
        const name = rockcraft['name'];
        return {
            type: 'rock',
            name,
            source_file: file,
            source_directory: path.dirname(file),
            build_target: undefined,
            output_type: outputType,
            output: sanitizeArtifactName(`${id}__build__output__rock__${name}`)
        };
    });
}
async function planBuildDockerImage(workingDir, id, outputType) {
    const dockerFiles = await (await glob.create(path.join(workingDir, '**', '*.Dockerfile'))).glob();
    return dockerFiles.map((dockerFile) => {
        const file = path.join(workingDir, path.relative(workingDir, dockerFile));
        const name = path.basename(file).replace(/.Dockerfile$/, '');
        return {
            type: 'docker-image',
            name,
            source_file: file,
            source_directory: path.dirname(file),
            build_target: undefined,
            output_type: outputType,
            output: sanitizeArtifactName(`${id}__build__output__docker-image__${name}`)
        };
    });
}
async function planBuildFileResource(workingDir, id) {
    const allCharmcraftFiles = await (await glob.create(path.join(workingDir, '**', 'charmcraft.yaml'))).glob();
    const charmcraftFiles = allCharmcraftFiles.filter(file => !path.normalize(path.relative(workingDir, file)).startsWith('tests/'));
    return charmcraftFiles.flatMap((charmcraftFile) => {
        const file = path.join(workingDir, path.relative(workingDir, charmcraftFile));
        const charmcraft = yaml.load(fs.readFileSync(charmcraftFile, { encoding: 'utf-8' }));
        const metadataFile = path.join(path.dirname(charmcraftFile), 'metadata.yaml');
        const metadataExists = fs.existsSync(metadataFile);
        const metadata = metadataExists
            ? yaml.load(fs.readFileSync(metadataFile, { encoding: 'utf-8' }))
            : {};
        let charmName = '';
        if ('name' in charmcraft) {
            charmName = charmcraft['name'];
        }
        else if ('name' in metadata) {
            charmName = metadata.name;
        }
        else {
            throw new Error(`unknown charm name (${workingDir})`);
        }
        let resources = new Map();
        if ('resources' in charmcraft) {
            resources = charmcraft['resources'];
        }
        if ('resources' in metadata) {
            resources = metadata['resources'];
        }
        return Object.entries(resources).reduce((acc, [resourceName, resource]) => {
            if (resource.type === 'file' && resource.filename) {
                const parent = path.dirname(file);
                if (resource.description?.trim().startsWith('(local)')) {
                    return acc;
                }
                acc.push({
                    type: 'file',
                    name: resourceName,
                    source_file: `build-${resourceName}.sh`,
                    build_target: resource.filename,
                    source_directory: parent,
                    output_type: 'file',
                    output: sanitizeArtifactName(`${id}__build__output__file__${charmName}__${resourceName}`)
                });
            }
            return acc;
        }, []);
    });
}
async function planBuild(workingDir, id, imageOutputType) {
    return [
        ...(await planBuildCharm(workingDir, id)),
        ...(await planBuildRock(workingDir, id, imageOutputType)),
        ...(await planBuildDockerImage(workingDir, id, imageOutputType)),
        ...(await planBuildFileResource(workingDir, id))
    ];
}
async function run() {
    try {
        let id = `${new Date().toISOString().replaceAll(':', '-').replace(/\..+/, '')}-${crypto.randomUUID().split('-')[3]}`;
        const identity = core.getInput('identifier');
        if (identity.includes('__')) {
            core.setFailed('identifier can not contain "__"');
            return;
        }
        if (identity) {
            id = `${id}__${identity}`;
        }
        const workingDir = normalizePath(core.getInput('working-directory'));
        let imageOutputType;
        const uploadImage = core.getInput('upload-image');
        switch (uploadImage) {
            case '':
                imageOutputType = fromFork() ? 'file' : 'registry';
                break;
            case 'artifact':
                imageOutputType = 'file';
                break;
            case 'registry':
                imageOutputType = 'registry';
                break;
            default:
                core.setFailed(`unknown upload-image input: ${uploadImage}`);
                return;
        }
        const buildPlans = await planBuild(workingDir, id, imageOutputType);
        const plan = {
            working_directory: workingDir,
            build: buildPlans
        };
        core.info(`Generated workflow plan: ${JSON.stringify(plan, null, 2)}`);
        const artifact = new artifact_1.DefaultArtifactClient();
        const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'plan-'));
        const pathFile = path.join(tmp, 'plan.json');
        const planJson = JSON.stringify(plan, null, 2);
        fs.writeFileSync(pathFile, planJson);
        await artifact.uploadArtifact(sanitizeArtifactName(`${id}__plan`), [pathFile], tmp, {});
        core.setOutput('plan', planJson);
    }
    catch (error) {
        // Fail the workflow run if an error occurs
        if (error instanceof Error)
            core.setFailed(error.message);
    }
}
run();
//# sourceMappingURL=index.js.map
