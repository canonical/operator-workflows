# Contributing to supercharm

Thank you for considering a contribution! This document explains how to set up a development
environment, run the tests, and submit changes.

## Development setup

1. **Clone the repository** and navigate to the `supercharm` directory:

   ```bash
   git clone <repo-url>
   cd operator-workflows/supercharm
   ```

2. **Create and activate a virtual environment**:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install the package in editable mode** together with the test dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

   If there is no `[dev]` extra yet, install `pytest` manually:

   ```bash
   pip install -e . pytest
   ```

## Running the tests

```bash
python -m pytest
```

All test files live under `tests/`. pytest is configured in `pyproject.toml`.

## Making changes

- Keep changes focused and minimal.
- Add or update tests for any logic you change.
- Make sure the full test suite passes before opening a pull request.
- Follow the existing code style (no linter is enforced yet, but consistency is appreciated).

## Submitting a pull request

1. Fork the repository and create a feature branch:

   ```bash
   git checkout -b my-feature
   ```

2. Commit your changes with a clear message:

   ```bash
   git commit -m "Short description of the change"
   ```

3. Push the branch and open a pull request against `main`.
4. Describe **what** you changed and **why** in the pull request description.

## Reporting issues

Please open a GitHub issue with:

- A clear description of the problem.
- Steps to reproduce it.
- The output of `supercharm version` (or `charmcraft version`).
- Your OS and Python version.
