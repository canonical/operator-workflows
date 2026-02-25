import pytest
from pathlib import Path

from supercharm.files import copy_context_to_temp, charm_name_from_yaml, copy_charm_files


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

        assert (dest / "charmcraft.yaml").read_text() == "name: my-charm\n"

    def test_skips_charmcraft_yaml_when_absent(self, tmp_path):
        context = tmp_path / "context"
        context.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()

        copy_context_to_temp(context, dest, tmp_path / "charmcraft.yaml")

        assert not (dest / "charmcraft.yaml").exists()


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
