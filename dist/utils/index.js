// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.
Object.defineProperty(exports, "__esModule", { value: true });
exports.mkdtemp = mkdtemp;
exports.normalizePath = normalizePath;
const tslib_1 = require("tslib");
const fs_1 = tslib_1.__importDefault(require("fs"));
const path_1 = tslib_1.__importDefault(require("path"));
const os_1 = tslib_1.__importDefault(require("os"));
function mkdtemp() {
    return fs_1.default.mkdtempSync(path_1.default.join(os_1.default.tmpdir(), 'artifact-'));
}
function normalizePath(p) {
    return path_1.default.normalize(p).replace(/\/+$/, '');
}
//# sourceMappingURL=index.js.map
