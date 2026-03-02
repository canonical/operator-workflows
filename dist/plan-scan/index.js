// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.
Object.defineProperty(exports, "__esModule", { value: true });
exports.run = run;
const tslib_1 = require("tslib");
const core = tslib_1.__importStar(require("@actions/core"));
const artifact_1 = require("@actions/artifact");
const fs_1 = tslib_1.__importDefault(require("fs"));
async function run() {
    try {
        const plan = JSON.parse(core.getInput('plan'));
        const artifact = new artifact_1.DefaultArtifactClient();
        let scans = [];
        for (const build of plan.build) {
            if (['charm', 'file'].includes(build.type)) {
                core.info(`Skipping ${build.type} build`);
                continue;
            }
            fs_1.default.readdirSync('.').forEach(file => fs_1.default.rmSync(file, { force: true, recursive: true }));
            await artifact.downloadArtifact((await artifact.getArtifact(build.output)).artifact.id);
            const manifest = JSON.parse(fs_1.default.readFileSync('manifest.json', { encoding: 'utf-8' }));
            if ('files' in manifest) {
                const files = manifest.files;
                scans = scans.concat(files.map(f => ({
                    artifact: build.output,
                    file: f,
                    image: ''
                })));
            }
            if ('images' in manifest) {
                const images = manifest.images;
                scans = scans.concat(images.map(i => ({
                    artifact: '',
                    file: `${i.replaceAll(/[/:]/g, '-')}.tar`,
                    image: i
                })));
            }
        }
        core.setOutput('scans', JSON.stringify(scans, null, 2));
    }
    catch (error) {
        // Fail the workflow run if an error occurs
        if (error instanceof Error)
            core.setFailed(error.message);
    }
}
run();
//# sourceMappingURL=index.js.map
