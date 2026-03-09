import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from supercharm.main import _install_charmcraft, _parse_build_context, _peek_verbose, main


# ---------------------------------------------------------------------------
# _peek_verbose
# ---------------------------------------------------------------------------

class TestPeekVerbose:
    def test_returns_true_for_long_flag(self):
        assert _peek_verbose(["--verbose", "pack"]) is True

    def test_returns_true_for_short_flag(self):
        assert _peek_verbose(["-v", "pack"]) is True

    def test_returns_false_when_absent(self):
        assert _peek_verbose(["pack"]) is False

    def test_long_flag_remains_in_argv(self):
        argv = ["--verbose", "pack"]
        _peek_verbose(argv)
        assert "--verbose" in argv

    def test_short_flag_remains_in_argv(self):
        argv = ["-v", "pack"]
        _peek_verbose(argv)
        assert "-v" in argv


# ---------------------------------------------------------------------------
# _install_charmcraft
# ---------------------------------------------------------------------------

class TestInstallCharmcraft:
    def test_runs_snap_install(self):
        with patch("supercharm.main.subprocess.run") as mock_run:
            _install_charmcraft()
            mock_run.assert_called_once_with(
                ["sudo", "snap", "install", "charmcraft", "--classic"],
                check=True,
            )


# ---------------------------------------------------------------------------
# _parse_build_context
# ---------------------------------------------------------------------------

class TestParseBuildContext:
    def test_returns_given_build_context_directory(self, tmp_path):
        ctx, _proj, args = _parse_build_context(["--build-context", str(tmp_path), "pack"])
        assert ctx == tmp_path
        assert args == ["pack"]

    def test_defaults_context_to_cwd_when_not_provided(self):
        ctx, _proj, args = _parse_build_context(["pack", "--destructive-mode"])
        assert ctx == Path.cwd()
        assert args == ["pack", "--destructive-mode"]

    def test_remaining_args_exclude_build_context(self, tmp_path):
        _ctx, _proj, args = _parse_build_context(
            ["--build-context", str(tmp_path), "upload", "--release", "edge"]
        )
        assert "--build-context" not in args
        assert str(tmp_path) not in args
        assert args == ["upload", "--release", "edge"]

    def test_empty_argv_returns_cwd_and_no_args(self):
        ctx, _proj, args = _parse_build_context([])
        assert ctx == Path.cwd()
        assert args == []

    def test_project_dir_is_consumed(self):
        _ctx, _proj, args = _parse_build_context(["--project-dir", "my-charm", "pack"])
        assert "--project-dir" not in args
        assert "my-charm" not in args

    def test_project_dir_short_flag_is_consumed(self):
        _ctx, _proj, args = _parse_build_context(["-p", "my-charm", "pack"])
        assert "-p" not in args


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _make_parse_build_context_mock():
    """Return a side_effect that extends _parse_build_context's 3-tuple to 4."""
    def _patched(argv):
        ctx, proj, remaining = _parse_build_context(argv)
        return ctx, proj, Path("."), remaining
    return _patched


class TestMain:
    def _run_main(self, argv, mock_run_returncode=0):
        """Helper that patches all side-effects and runs main() with given argv."""
        result_mock = MagicMock()
        result_mock.returncode = mock_run_returncode

        with (
            patch("supercharm.main.shutil.which", return_value="/usr/bin/charmcraft"),
            patch("supercharm.main._parse_build_context",
                  side_effect=_make_parse_build_context_mock()),
            patch("supercharm.main.subprocess.run", return_value=result_mock) as mock_run,
            patch("supercharm.main.copy_context_to_temp") as mock_copy_ctx,
            patch("supercharm.main.copy_charm_files") as mock_copy_charm,
            patch("supercharm.main.charm_name_from_yaml", return_value="my-charm"),
            patch("supercharm.main.move_generated_lib"),
            patch.object(sys, "argv", ["supercharm"] + argv),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        return exc_info.value.code, mock_run, mock_copy_ctx, mock_copy_charm

    def test_exits_with_charmcraft_returncode(self):
        code, *_ = self._run_main(["pack"], mock_run_returncode=0)
        assert code == 0

    def test_exits_with_nonzero_returncode_on_failure(self):
        code, *_ = self._run_main(["pack"], mock_run_returncode=1)
        assert code == 1

    def test_calls_charmcraft_with_forwarded_args(self):
        _, mock_run, _, _ = self._run_main(["pack", "--destructive-mode"])
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "charmcraft"
        assert "pack" in cmd
        assert "--destructive-mode" in cmd

    def test_build_context_arg_not_forwarded_to_charmcraft(self, tmp_path):
        _, mock_run, _, _ = self._run_main(["--build-context", str(tmp_path), "pack"])
        cmd = mock_run.call_args[0][0]
        assert "--build-context" not in cmd
        assert str(tmp_path) not in cmd

    def test_project_dir_not_forwarded_to_charmcraft(self):
        _, mock_run, _, _ = self._run_main(["--project-dir", "my-charm", "pack"])
        cmd = mock_run.call_args[0][0]
        assert "--project-dir" not in cmd

    def test_verbose_flag_forwarded_to_charmcraft(self):
        _, mock_run, _, _ = self._run_main(["--verbose", "pack"])
        cmd = mock_run.call_args[0][0]
        assert "--verbose" in cmd

    def test_verbose_short_flag_forwarded_to_charmcraft(self):
        _, mock_run, _, _ = self._run_main(["-v", "pack"])
        cmd = mock_run.call_args[0][0]
        assert "-v" in cmd

    def test_installs_charmcraft_when_not_found(self):
        result_mock = MagicMock()
        result_mock.returncode = 0

        with (
            patch("supercharm.main.shutil.which", return_value=None),
            patch("supercharm.main._parse_build_context",
                  side_effect=_make_parse_build_context_mock()),
            patch("supercharm.main.subprocess.run", return_value=result_mock),
            patch("supercharm.main.copy_context_to_temp"),
            patch("supercharm.main.copy_charm_files"),
            patch("supercharm.main.charm_name_from_yaml", return_value=None),
            patch("supercharm.main.move_generated_lib"),
            patch("supercharm.main._install_charmcraft") as mock_install,
            patch.object(sys, "argv", ["supercharm", "pack"]),
            pytest.raises(SystemExit),
        ):
            main()

        mock_install.assert_called_once()

    def test_does_not_install_when_charmcraft_present(self):
        result_mock = MagicMock()
        result_mock.returncode = 0

        with (
            patch("supercharm.main.shutil.which", return_value="/usr/bin/charmcraft"),
            patch("supercharm.main._parse_build_context",
                  side_effect=_make_parse_build_context_mock()),
            patch("supercharm.main.subprocess.run", return_value=result_mock),
            patch("supercharm.main.copy_context_to_temp"),
            patch("supercharm.main.copy_charm_files"),
            patch("supercharm.main.charm_name_from_yaml", return_value=None),
            patch("supercharm.main.move_generated_lib"),
            patch("supercharm.main._install_charmcraft") as mock_install,
            patch.object(sys, "argv", ["supercharm", "pack"]),
            pytest.raises(SystemExit),
        ):
            main()

        mock_install.assert_not_called()

    def test_copy_context_and_charm_files_called(self):
        _, _, mock_copy_ctx, mock_copy_charm = self._run_main(["pack"])
        mock_copy_ctx.assert_called_once()
        mock_copy_charm.assert_called_once()

    def test_charmcraft_runs_inside_temp_directory(self):
        _, mock_run, _, _ = self._run_main(["pack"])
        cwd_used = mock_run.call_args[1]["cwd"]
        assert cwd_used != Path.cwd()
        assert isinstance(cwd_used, Path)

    def test_project_dir_used_for_charm_yaml_path(self, tmp_path):
        charm_dir = tmp_path / "my-charm"
        charm_dir.mkdir()
        (charm_dir / "charmcraft.yaml").write_text("name: my-charm\n")

        with (
            patch("supercharm.main.shutil.which", return_value="/usr/bin/charmcraft"),
            patch("supercharm.main._parse_build_context",
                  return_value=(tmp_path, Path("my-charm"), Path("."), ["pack"])),
            patch("supercharm.main.subprocess.run", return_value=MagicMock(returncode=0)),
            patch("supercharm.main.copy_context_to_temp") as mock_copy_ctx,
            patch("supercharm.main.copy_charm_files"),
            patch("supercharm.main.charm_name_from_yaml", return_value="my-charm"),
            patch("supercharm.main.move_generated_lib"),
            patch("supercharm.main.Path.cwd", return_value=tmp_path),
            patch.object(sys, "argv", ["supercharm", "--project-dir", "my-charm", "pack"]),
            pytest.raises(SystemExit),
        ):
            main()

        charm_yaml_used = mock_copy_ctx.call_args[0][2]
        assert charm_yaml_used == tmp_path / "my-charm" / "charmcraft.yaml"
