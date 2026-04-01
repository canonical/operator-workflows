# charmbuild

`charmbuild` is a thin Python wrapper around [charmcraft](https://juju.is/docs/sdk/charmcraft).
It ensures `charmcraft` is installed on the machine and transparently forwards all arguments to it,
with one extra convenience: a `--build-context` option that lets you supply an external directory
of source files to include in the build without modifying your project tree.

## Features

- Auto-installs the latest `charmcraft` via `snap` if it is not already present.
- Accepts an optional `--build-context <dir>` argument (see below).
- All other arguments and flags are passed through to `charmcraft` unchanged.
- After the build, any `.charm` files whose name matches the `name` key in `charmcraft.yaml`
  are copied back to the current working directory automatically.

## Requirements

- Python 3.8+
- `snap` (for automatic `charmcraft` installation)
- `pyyaml` (installed automatically as a dependency)

## Installation

```bash
pip install ./charmbuild
```

Or, for development:

```bash
pip install -e ./charmbuild
```

## Usage

```
charmbuild [--build-context <dir>] <charmcraft command and args>
```

### Without `--build-context`

`charmbuild` behaves exactly like calling `charmcraft` directly:

```bash
charmbuild pack
charmbuild version
charmbuild upload my-charm_ubuntu-22.04-amd64.charm
```

### With `--build-context`

Provide a directory whose contents will be merged with the `charmcraft.yaml` from the current
working directory into a temporary build directory. This is useful when your source files live
separately from your charm metadata.

```bash
charmbuild --build-context ./src pack
```

What happens internally:

1. A temporary directory is created.
2. `charmcraft.yaml` from the **current working directory** (if present) is copied in.
3. All files and subdirectories from `--build-context` are copied in alongside it.
4. `charmcraft` is executed with the remaining arguments inside that temporary directory.
5. Any resulting `.charm` files whose filename starts with the charm `name` are copied back
   to the current working directory.
6. The temporary directory is cleaned up.

If `--build-context` is omitted, the current working directory is used as the context.
