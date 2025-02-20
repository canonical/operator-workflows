# Integration test workflow

The integration test is composed of the following steps.

1. [Plan the workflow](#plan-the-workflow)
2. [Build the artifacts](#build-the-artifacts)
3. [Run the integration test](#run-the-integration-test)

This documentation goes over each of the steps, covering the internal details of
how they work.

## Plan the workflow

The [plan workflow](../../internal/plan/action.yml) refers to the 
[action](../../src/plan.ts). The plan generates the plan for the entire
integration workflow, including the building of the following
resources if detected:

* Charm
* Rock
* Docker
* Charm Resources

The resources are shared between workflows using the GitHub Action artifact or
the GitHub container registry. Image resources' destinations can further be
specified by the user using `upload-image` input.

When the workflow is executed from a fork, the resources are shared via the
filesystem.

### Charm

The workflow will automatically look for any `charmcraft.yaml` file within the
source repository root by using the following glob syntax: `**/charmcraft.yaml`.
`metadata.yaml` file is also used to extract any required charm property if it
is found. Any `charmcraft.yaml` files within the `tests/` directory are ignored.

### Rock

The workflow will automatically look for any `rockcraft.yaml` file within the
source repository root by using the following glob syntax: `**/rockcraft.yaml`.

### Docker

The workflow will automatically look for any `*.Dockerfile` file within the
source repository root by using the following glob syntax: `**/*.Dockerfile`.

### Charm Resources

If a charm has [file resources](https://canonical-charmcraft.readthedocs-hosted.com/en/stable/reference/files/charmcraft-yaml-file/#resources) the workflow will assume 
`build-<resourceName>.sh` script exists which will be used to build the
resource.

## Build the artifacts

The plan resource output from the [plan step](#1-plan) are used to build the
artifacts needed for the integration tests. 

### Charm

The charms detected from the [plan step](#1-plan) are built using the
`charmcraft pack` command. The workflow automatically changes the working
directory to where the `charmcraft.yaml` or the `metadata.yaml` file resides.
The built charm output are selected using the `*.charm` glob syntax. The output
artifact is then uploaded to GitHub.

### Rock

The rocks detected from the [plan step](#1-plan) are built using the
`rockcraft pack` command. The workflow automatically changes the working
directory to where the `rockcraft.yaml` file resides.
The built rock output are selected using the `*.rock` glob syntax. The output
artifact is then uploaded to either the GitHub or the Docker repository.

### Docker

The Dockerfiles detected from the [plan step](#1-plan) are built using the
`docker build` command. The workflow automatically changes the working
directory to where the `*.Dockerfile` file resides.
The built Docker images are either:

1. Saved as a tarball and uploaded to GitHub.
2. Pushed to the Docker registry.

### Charm Resources

The Charm Resources detected from the [plan step](#1-plan) are built by executing
the `<build-<resourceName>.sh>` script. The workflow automatically changes the
working directory to where the `<build-<resourceName>.sh>` file resides.

The output charm resource will be uploaded to GitHub.

## Run the integration test

The artifacts built from the [build step](#2-build) are automatically unpacked
and used in the `tox` integration test.

The tox arguments are then appended accordingly.

### Charm

Tox argument: `--charm-file=./<charm-build-output-file>.charm`

### Rock

The rocks are pushed to the local MicroK8s image registry (localhost:32000)
using `skopeo copy --insecure-policy --dest-tls-verify=false ...` command if the
rock is downloaded as a tarball artifact. By default, the GitHub registry is
used.

Tox argument: `--<rock-name>-image=<local-registry-image-name>`

### Docker

The Docker images are referred to from the image registry that is output from
the build step. The integration test workflow usually uses the GitHub Container
Registry (ghcr), unless specified otherwise in the workflow.

Tox argument: `--<image-name>-image=<image-resource-uri>`

### Charm Resources

The Charm Resources are unpacked and are referred to via their respective file
paths.

Tox argument: `--<resource-name>-resource=./<path-to-resource>`
