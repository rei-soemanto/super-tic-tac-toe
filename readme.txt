SUPER TIC-TAC-TOE
=================
Super Tic-Tac-Toe against a search-based AI, as a pygame desktop app.


1. LIBRARIES AND VERSIONS REQUIRED
----------------------------------
Runtime:
  - Python        3.14   (pinned in .python-version; pyproject.toml allows >= 3.12)
  - pygame-ce     2.5.8  (pyproject.toml allows >= 2.5.8)

Development / testing only:
  - pytest        9.1.1
      plus its dependencies: colorama 0.4.6, iniconfig 2.3.1,
      packaging 26.3, pluggy 1.6.0, pygments 2.21.0

Tooling:
  - uv            0.12.13 (package and environment manager; the build
                           backend requires uv_build >= 0.12.13, < 0.13.0)

Exact locked versions are recorded in uv.lock.
The fonts (Archivo, SIL Open Font License) ship inside
super_tic_tac_toe/assets/fonts, so nothing else needs installing.


2. IDE AND VERSION
------------------
  - Visual Studio Code 1.143.1
  - Recommended extension: Python (ms-python.python)

Any editor works; the game is started from a terminal.


3. STEPS TO SET UP AND RUN THE SOURCE CODE
------------------------------------------
Option A: using uv (recommended)

  1. Install uv:
       Windows (PowerShell):
         powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
       macOS / Linux:
         curl -LsSf https://astral.sh/uv/install.sh | sh

  2. Open a terminal in the project folder (the folder holding pyproject.toml):
       cd super-tic-tac-toe

  3. Install Python 3.14 and all dependencies into a local .venv:
       uv sync
     (uv downloads Python 3.14 by itself if it is not installed.)

  4. Run the game:
       uv run super-tic-tac-toe

  5. (Optional) Run the tests:
       uv run pytest

  6. (Optional) Run the AI analysis scripts:
       uv run python -m super_tic_tac_toe.analysis.benchmark [--positions N] [--depth D]
       uv run python -m super_tic_tac_toe.analysis.selfplay [--games N] [--hard-ms MS]


Option B: using plain Python and pip

  1. Install Python 3.14 (or 3.12+) from https://www.python.org/downloads/
     On Windows, tick "Add python.exe to PATH" during installation.

  2. Open a terminal in the project folder and create a virtual environment:
       python -m venv .venv

  3. Activate it:
       Windows (PowerShell):  .venv\Scripts\Activate.ps1
       Windows (cmd):         .venv\Scripts\activate.bat
       macOS / Linux:         source .venv/bin/activate

  4. Install the project and its dependencies:
       pip install -e .
       pip install pytest          (only needed to run the tests)

  5. Run the game:
       super-tic-tac-toe

  6. (Optional) Run the tests:
       pytest


Running from VS Code

  1. File > Open Folder... and choose the project folder.
  2. Run "uv sync" (or Option B steps 2-4) in the integrated terminal.
  3. Ctrl+Shift+P > "Python: Select Interpreter" and pick .venv.
  4. Start the game from the integrated terminal with
       uv run super-tic-tac-toe
     (or "super-tic-tac-toe" with the .venv activated).
