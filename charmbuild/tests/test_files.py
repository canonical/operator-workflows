#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import yaml
from pathlib import Path

from charmbuild.files import (
    copy_context_to_temp,
    charm_name_from_yaml,
    compute_patched_yaml,
    copy_charm_files,
    move_generated_lib,
)


class TestComputePatchedYaml:
    def _write_yaml(self, path: Path, uv_working_dir=".", extra_parts=None):
        data = (
            "name: my-charm\n"
            "parts:\n"
            "  charm:\n"
            "    plugin: uv\n"
            "    build-environment:\n"
            f"      - UV_WORKING_DIR: {uv_working_dir}\n"
        )
        if extra_parts:
            for name, plugin in extra_parts.items():
                data += (
                    f"  {name}:\n"
                    f"    plugin: {plugin}\n"
                    "    build-environment:\n"
                    "      - UV_WORKING_DIR: .\n"
                )
        path.write_text(data)

    def test_returns_patched_yaml_string(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        self._write_yaml(charm_yaml)
        result = compute_patched_yaml(charm_yaml, Path("my-charm-operator"))
        assert result is not None
        parsed = yaml.safe_load(result)
        build_env = parsed["parts"]["charm"]["build-environment"]
        assert {"UV_WORKING_DIR": "my-charm-operator"} in build_env

    def test_returns_none_when_uv_working_dir_not_dot(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        self._write_yaml(charm_yaml, uv_working_dir="already-set")
        assert compute_patched_yaml(charm_yaml, Path("sub")) is None

    def test_returns_none_when_no_uv_part(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        charm_yaml.write_text("parts:\n  charm:\n    plugin: charm\n")
        assert compute_patched_yaml(charm_yaml, Path("sub")) is None

    def test_returns_none_when_multiple_uv_parts(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        self._write_yaml(charm_yaml, extra_parts={"extra": "uv"})
        assert compute_patched_yaml(charm_yaml, Path("sub")) is None

    def test_returns_none_when_rel_path_is_dot(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        self._write_yaml(charm_yaml)
        assert compute_patched_yaml(charm_yaml, Path(".")) is None

    def test_returns_none_when_file_absent(self, tmp_path):
        assert compute_patched_yaml(tmp_path / "charmcraft.yaml", Path("sub")) is None

    def test_preserves_other_build_environment_entries(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        charm_yaml.write_text(
            "parts:\n"
            "  charm:\n"
            "    plugin: uv\n"
            "    build-environment:\n"
            "      - SOME_VAR: foo\n"
            "      - UV_WORKING_DIR: .\n"
        )
        result = compute_patched_yaml(charm_yaml, Path("sub"))
        assert result is not None
        parsed = yaml.safe_load(result)
        build_env = parsed["parts"]["charm"]["build-environment"]
        assert {"SOME_VAR": "foo"} in build_env
        assert {"UV_WORKING_DIR": "sub"} in build_env

    def test_returns_none_when_no_build_environment(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        charm_yaml.write_text("parts:\n  charm:\n    plugin: uv\n")
        assert compute_patched_yaml(charm_yaml, Path("sub")) is None


class TestCopyContextToTemp:
    def test_copies_files_from_context_dir(self, tmp_path):
        context = tmp_path / "context"
        context.mkdir()
        (context / "src.py").write_text("print('hi')")
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, tmp_path / "charmcraft.yaml")

        assert (dest / "src.py").read_text() == "print('hi')"

    def test_copies_subdirectory_from_context_dir(self, tmp_path):
        context = tmp_path / "context"
        (context / "subdir").mkdir(parents=True)
        (context / "subdir" / "file.txt").write_text("nested")
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, tmp_path / "charmcraft.yaml")

        assert (dest / "subdir" / "file.txt").read_text() == "nested"

    def test_copies_charmcraft_yaml_when_present(self, tmp_path):
        context = tmp_path / "context"
        context.mkdir()
        charm_yaml = tmp_path / "charmcraft.yaml"
        charm_yaml.write_text("name: my-charm\n")
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, charm_yaml)

        # charm_yaml.parent (tmp_path) is not relative to context_dir (tmp_path/context),
        # so no patching occurs and the file is copied as-is.
        assert (dest / "charmcraft.yaml").read_text() == "name: my-charm\n"

    def test_patches_charmcraft_yaml_when_charm_is_in_subdir(self, tmp_path):
        context = tmp_path / "repo"
        charm_dir = context / "my-charm-operator"
        charm_dir.mkdir(parents=True)
        charm_yaml = charm_dir / "charmcraft.yaml"
        charm_yaml.write_text(
            "name: my-charm\n"
            "parts:\n"
            "  charm:\n"
            "    plugin: uv\n"
            "    build-environment:\n"
            "      - UV_WORKING_DIR: .\n"
        )
        dest = tmp_path / "dest"
        dest.mkdir()
        patched = compute_patched_yaml(charm_yaml, Path("my-charm-operator"))

        copy_context_to_temp(context, dest, charm_yaml, patched)

        data = yaml.safe_load((dest / "charmcraft.yaml").read_text())
        build_env = data["parts"]["charm"]["build-environment"]
        assert {"UV_WORKING_DIR": "my-charm-operator"} in build_env
        assert "override-build" not in data["parts"]["charm"]

    def test_no_patch_when_multiple_uv_plugin_parts(self, tmp_path):
        context = tmp_path / "repo"
        charm_dir = context / "sub"
        charm_dir.mkdir(parents=True)
        charm_yaml = charm_dir / "charmcraft.yaml"
        charm_yaml.write_text(
            "name: my-charm\n"
            "parts:\n"
            "  charm:\n"
            "    plugin: uv\n"
            "    build-environment:\n"
            "      - UV_WORKING_DIR: .\n"
            "  extra:\n"
            "    plugin: uv\n"
            "    build-environment:\n"
            "      - UV_WORKING_DIR: .\n"
        )
        dest = tmp_path / "dest"
        dest.mkdir()
        patched = compute_patched_yaml(charm_yaml, Path("sub"))  # returns None

        copy_context_to_temp(context, dest, charm_yaml, patched)

        data = yaml.safe_load((dest / "charmcraft.yaml").read_text())
        assert {"UV_WORKING_DIR": "."} in data["parts"]["charm"]["build-environment"]
        assert {"UV_WORKING_DIR": "."} in data["parts"]["extra"]["build-environment"]

    def test_no_patch_when_no_uv_plugin_part(self, tmp_path):
        context = tmp_path / "repo"
        charm_dir = context / "sub"
        charm_dir.mkdir(parents=True)
        charm_yaml = charm_dir / "charmcraft.yaml"
        charm_yaml.write_text(
            "name: my-charm\n"
            "parts:\n"
            "  charm:\n"
            "    plugin: charm\n"
            "    build-environment:\n"
            "      - UV_WORKING_DIR: .\n"
        )
        dest = tmp_path / "dest"
        dest.mkdir()
        patched = compute_patched_yaml(charm_yaml, Path("sub"))  # returns None

        copy_context_to_temp(context, dest, charm_yaml, patched)

        data = yaml.safe_load((dest / "charmcraft.yaml").read_text())
        build_env = data["parts"]["charm"]["build-environment"]
        assert {"UV_WORKING_DIR": "."} in build_env

    def test_no_patch_when_uv_working_dir_not_dot(self, tmp_path):
        context = tmp_path / "repo"
        charm_dir = context / "sub"
        charm_dir.mkdir(parents=True)
        charm_yaml = charm_dir / "charmcraft.yaml"
        charm_yaml.write_text(
            "name: my-charm\n"
            "parts:\n"
            "  charm:\n"
            "    plugin: uv\n"
            "    build-environment:\n"
            "      - UV_WORKING_DIR: already-set\n"
        )
        dest = tmp_path / "dest"
        dest.mkdir()
        patched = compute_patched_yaml(charm_yaml, Path("sub"))  # returns None

        copy_context_to_temp(context, dest, charm_yaml, patched)

        data = yaml.safe_load((dest / "charmcraft.yaml").read_text())
        build_env = data["parts"]["charm"]["build-environment"]
        assert {"UV_WORKING_DIR": "already-set"} in build_env

    def test_no_patch_when_charm_yaml_at_context_root(self, tmp_path):
        context = tmp_path / "repo"
        context.mkdir()
        charm_yaml = context / "charmcraft.yaml"
        charm_yaml.write_text("name: my-charm\n")
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, charm_yaml)

        # patched_yaml_content=None (default), yaml copied as-is.
        assert (dest / "charmcraft.yaml").read_text() == "name: my-charm\n"

    def test_patch_preserves_existing_build_environment_entries(self, tmp_path):
        context = tmp_path / "repo"
        charm_dir = context / "sub"
        charm_dir.mkdir(parents=True)
        charm_yaml = charm_dir / "charmcraft.yaml"
        charm_yaml.write_text(
            "name: my-charm\n"
            "parts:\n"
            "  charm:\n"
            "    plugin: uv\n"
            "    build-environment:\n"
            "      - SOME_VAR: foo\n"
            "      - UV_WORKING_DIR: .\n"
        )
        dest = tmp_path / "dest"
        dest.mkdir()
        patched = compute_patched_yaml(charm_yaml, Path("sub"))

        copy_context_to_temp(context, dest, charm_yaml, patched)

        data = yaml.safe_load((dest / "charmcraft.yaml").read_text())
        build_env = data["parts"]["charm"]["build-environment"]
        assert {"SOME_VAR": "foo"} in build_env
        assert {"UV_WORKING_DIR": "sub"} in build_env

    def test_skips_charmcraft_yaml_when_absent(self, tmp_path):
        context = tmp_path / "context"
        context.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, tmp_path / "charmcraft.yaml")

        assert not (dest / "charmcraft.yaml").exists()


class TestMoveGeneratedLib:
    def test_moves_lib_to_uv_working_dir(self, tmp_path):
        charm_dir = tmp_path / "my-charm"
        charm_dir.mkdir()
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "some_lib.py").write_text("# lib")

        move_generated_lib(tmp_path, Path("my-charm"))

        assert not lib_dir.exists()
        assert (charm_dir / "lib" / "some_lib.py").read_text() == "# lib"

    def test_no_op_when_lib_absent(self, tmp_path):
        (tmp_path / "my-charm").mkdir()

        move_generated_lib(tmp_path, Path("my-charm"))

        assert not (tmp_path / "lib").exists()
        assert not (tmp_path / "my-charm" / "lib").exists()

    def test_moves_nested_lib_contents(self, tmp_path):
        charm_dir = tmp_path / "sub" / "charm"
        charm_dir.mkdir(parents=True)
        lib_dir = tmp_path / "lib" / "charms" / "my_charm" / "v0"
        lib_dir.mkdir(parents=True)
        (lib_dir / "api.py").write_text("# api")

        move_generated_lib(tmp_path, Path("sub/charm"))

        assert not (tmp_path / "lib").exists()
        assert (
            charm_dir / "lib" / "charms" / "my_charm" / "v0" / "api.py"
        ).read_text() == "# api"


class TestCharmNameFromYaml:
    def test_returns_name_from_valid_yaml(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        charm_yaml.write_text("name: my-charm\n")

        assert charm_name_from_yaml(charm_yaml) == "my-charm"

    def test_returns_none_when_file_absent(self, tmp_path):
        assert charm_name_from_yaml(tmp_path / "charmcraft.yaml") is None

    def test_returns_none_when_name_key_missing(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        charm_yaml.write_text("type: charm\n")

        assert charm_name_from_yaml(charm_yaml) is None

    def test_returns_none_for_empty_file(self, tmp_path):
        charm_yaml = tmp_path / "charmcraft.yaml"
        charm_yaml.write_text("")

        assert charm_name_from_yaml(charm_yaml) is None


class TestCopyCharmFiles:
    def test_copies_matching_charm_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "my-charm_ubuntu-22.04-amd64.charm").touch()
        dest = tmp_path / "dest"
        dest.mkdir()

        copied = copy_charm_files(src, dest, "my-charm")

        assert (dest / "my-charm_ubuntu-22.04-amd64.charm").exists()
        assert len(copied) == 1

    def test_skips_non_matching_charm_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "other-charm_ubuntu-22.04-amd64.charm").touch()
        dest = tmp_path / "dest"
        dest.mkdir()

        copied = copy_charm_files(src, dest, "my-charm")

        assert not (dest / "other-charm_ubuntu-22.04-amd64.charm").exists()
        assert copied == []

    def test_copies_all_charm_files_when_name_is_none(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "alpha.charm").touch()
        (src / "beta.charm").touch()
        dest = tmp_path / "dest"
        dest.mkdir()

        copied = copy_charm_files(src, dest, None)

        assert len(copied) == 2
        assert (dest / "alpha.charm").exists()
        assert (dest / "beta.charm").exists()

    def test_returns_empty_list_when_no_charm_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        copied = copy_charm_files(src, dest, "my-charm")

        assert copied == []

    def test_copies_multiple_arches_for_same_charm(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "my-charm_ubuntu-22.04-amd64.charm").touch()
        (src / "my-charm_ubuntu-22.04-arm64.charm").touch()
        (src / "other-charm_ubuntu-22.04-amd64.charm").touch()
        dest = tmp_path / "dest"
        dest.mkdir()

        copied = copy_charm_files(src, dest, "my-charm")

        assert len(copied) == 2
        assert not (dest / "other-charm_ubuntu-22.04-amd64.charm").exists()
