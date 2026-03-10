#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
import yaml
from pathlib import Path

from superbuild.files import copy_context_to_temp, charm_name_from_yaml, copy_charm_files, move_generated_lib


# ---------------------------------------------------------------------------
# copy_context_to_temp
# ---------------------------------------------------------------------------

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
        charm_yaml.write_text("name: my-charm\nparts:\n  charm:\n    plugin: uv\n")
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, charm_yaml)

        data = yaml.safe_load((dest / "charmcraft.yaml").read_text())
        build_env = data["parts"]["charm"]["build-environment"]
        assert {"UV_WORKING_DIR": "my-charm-operator"} in build_env
        override = data["parts"]["charm"]["override-build"]
        assert "craftctl default" in override
        assert "$CRAFT_PART_BUILD/$UV_WORKING_DIR/src $CRAFT_PART_INSTALL/src" in override
        assert "$CRAFT_PART_BUILD/$UV_WORKING_DIR/lib $CRAFT_PART_INSTALL/lib" in override

    def test_no_patch_when_charm_yaml_at_context_root(self, tmp_path):
        context = tmp_path / "repo"
        context.mkdir()
        charm_yaml = context / "charmcraft.yaml"
        charm_yaml.write_text("name: my-charm\n")
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, charm_yaml)

        # rel_path == Path("."), so no patching.
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
            "    build-environment:\n"
            "      - SOME_VAR: foo\n"
        )
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, charm_yaml)

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


# ---------------------------------------------------------------------------
# move_generated_lib
# ---------------------------------------------------------------------------

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
        assert (charm_dir / "lib" / "charms" / "my_charm" / "v0" / "api.py").read_text() == "# api"


# ---------------------------------------------------------------------------
# charm_name_from_yaml
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# copy_charm_files
# ---------------------------------------------------------------------------

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
