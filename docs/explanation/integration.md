# Integration test workflow

The integration test is composed of the follwing steps.

1. [Plan](#1-plan)
2. [Build](#2-build)
3. [Test run](#3-test-run)

This documentation goes over each steps, covering the internal details of how
they work.

## 1. Plan

The [plan workflow](../../internal/plan/action.yml) refers to the 
[plan action](../../src/plan.ts). It is used to plan the build for the following
resources if detected:

* charm
* rock
* docker
* charm resources

The resources are shared between workflows using the local filesystem or the
GitHub container registry, depending on the user specified `upload-image` input.

When the workflow is executed from a fork, the resources are shared via the
filesystem.

### Charm

The workflow will automatically look for any `charmcraft.yaml` file or the 
`metadata.yaml` file within the source repository root by using the following
glob syntax: `**/charmcraft.yaml`. Any `charmcraft.yaml` files within the 
`tests/` directory are ignored.

The plan resource output will be named the following:

`<generated-id>__build__output__charm__<detected-charm-name>`

### Rock

The workflow will automatically look for any `rockcraft.yaml` file within the
source repository root by using the following glob syntax: `**/rockcraft.yaml`.

The plan resource output will be named the following:

`<generated-id>__build__output__rock__<detected-rock-name>`

### Docker

The workflow will automatically look for any `.Dockerfile` file within the
source repository root by using the following glob syntax: `**/*.Dockerfile`.

The plan resource output will be named the following:

`<generated-id>__build__output__docker-image__<*.Dockerfile prefix>`

### Charm Resources

If a charm has [file resources](https://canonical-charmcraft.readthedocs-hosted.com/en/stable/reference/files/charmcraft-yaml-file/#resources) the workflow will assume 
`build-<resourceName>.sh` script to exist which is used to build the resource.

The plan resource output will be named the following:

`<generated-id>__build__output__<charm-name>__<resource-name>`

## 2. Build

### Charm

The charms detected from the [plan step](#1-plan) is built using the
`charmcraft pack` command. The workflow automatically changes the working
directory to where the `charmcraft.yaml` or the `metadata.yaml` file resides.
The built charm output are selected using the `*.charm` glob syntax. The output
artifact is then uploaded to the GitHub.

### Rock

The rocks detected from the [plan step](#1-plan) is built using the
`rockcraft pack` command. The workflow automatically changes the working
directory to where the `rockcraft.yaml` file resides.
The built rock output are selected using the `*.rock` glob syntax. The output
artifact is then uploaded to the GitHub or uploaded to the docker repository.

### Docker

The Dockerfiles detected from the [plan step](#1-plan) is built using the
`docker build` command. The workflow automatically changes the working
directory to where the `*.Dockerfile` file resides.
The built docker images are either:

1. Saved as a tarball and uploaded to GitHub
2. Pushed to the Docker registry

### Charm Resources

The charm resources detected from the [plan step](#1-plan) is built by executing
the `<build-<resourceName>.sh>` script. The workflow automatically changes the
working directory to where the `<build-<resourceName>.sh>` file resides.

The output charm resource will be uploaded to GitHub.

## 3. Test run

The artifacts built from the [build step](#2-build) are automatically unpacked
and used in the `tox` integration test.

The tox arguments are then appended accordingly.

### Charm

Tox argument: `--charm-file=./<charm-build-output-file>.charm`

### Rock

The rocks are pushed to the local microk8s image registry (localhost:32000)
using `skopeo copy --insecure-policy --dest-tls-verify=false ...` command.

Tox argument: `--<rock-name>-image=<local-registry-image-name>`

### Docker

The Docker images are referred to from the image registry that is output from
the build step. It usually uses the GitHub Container Registry (ghcr), unless
specified otherwise in the workflow.

Tox argument: `--<image-name>-image=<image-resource-uri>`

### Charm Resources

The charm resources are unpacked and is referred to via their respective file
paths.

Tox argument: `--<resource-name>-resource=./<path-to-resource>`
