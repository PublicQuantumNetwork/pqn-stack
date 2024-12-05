# Public Quantum Network

Software for Public Quantum Network nodes.

## Development Instructions

1. Install [uv](https://docs.astral.sh/uv/), which will handle project management

1. Clone and navigate into this repository

1. Install the dependencies and set up the virtual environment 🏗️

   ```sh
   uv sync
   ```

1. Run the code 🚀

   ```sh
   uv run pqn
   ```

### Project Management

A few of the most useful uv commands are shown below.
See the [uv project guide](https://docs.astral.sh/uv/guides/projects) for more information about working on projects with uv.

- `uv add` -- Add dependencies to the project
- `uv remove` -- Remove dependencies from the project
- `uv sync` -- Update the project's environment
- `uv run` -- Run a command or script

> [!IMPORTANT]
> Instead of `pip install <package>`, use `uv add <package>`.

### Scripts

To run your code, or a command that is aware of your project environment, use the following command:

- `uv run` -- Run a command or script

See the [script documentation](https://docs.astral.sh/uv/guides/scripts/) for more information.

### Linting and Formatting

Use [Ruff](https://docs.astral.sh/ruff/) to lint and format your code.
It is already specified as a development dependency in this template's `pyproject.toml`, and is automatically installed when you run `uv sync`.

You can run the linter with `uv run ruff check` (use the `--fix` flag to apply fixes), and the formatter with `uv run ruff format`.
There are many options available to customize which linting rules are applied.
All rules are enabled by default, and I have disabled a few redundant ones as a starting point in the `pyproject.toml`.
Feel free to modify the list as needed for your project.
See the [documentation](https://docs.astral.sh/ruff/tutorial/) or command help output for additional information.

### Type Checking

Use [mypy](https://www.mypy-lang.org/) for type checking: `uv run mypy`.

### Testing

Use [pytest](https://docs.pytest.org/en/stable/) to run tests:

- `uv run pytest`
- Use `uv run pytest --cov` to check code coverage.

### Alternate Manual Setup

If it is not possible to use uv for installation, there is a workaround using `virtualenv` and `pip`.

> [!IMPORTANT]
> This method is intended as a workaround **only** for situations where uv is not available, and **only for local installations** rather than for active project development.

From the root directory of the repository:

1. Create the virtual environment

   ```sh
   virtualenv .venv
   ```

1. Activate the virtual environment

   ```sh
   source .venv/bin/activate
   ```

1. Install the project dependencies

   ```sh
   pip install -e .
   ```

1. Run the code

   ```sh
   pqn
   ```

### Possible Problems

What to try if things don't seem to be working:

- Remove the `.venv/` directory and try again ♻️
