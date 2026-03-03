'use strict';

var fs = require('fs');
var path = require('path');
var os = require('os');

// Copyright 2025 Canonical Ltd.
// See LICENSE file for licensing details.
function mkdtemp() {
    return fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-'));
}
function normalizePath(p) {
    return path.normalize(p).replace(/\/+$/, '');
}

exports.mkdtemp = mkdtemp;
exports.normalizePath = normalizePath;
//# sourceMappingURL=index.js.map
