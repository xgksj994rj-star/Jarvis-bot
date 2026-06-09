@echo off
REM Launch Jarvis using the bundled venv and current repository path.
SETLOCAL enabledelayedexpansion
PUSHD "%~dp0"
IF EXIST "venv-py312\Scripts\activate.bat" (
    call "venv-py312\Scripts\activate.bat"
) ELSE (
    echo ERROR: venv-py312 not found. Please create or install dependencies first.
    POPD
    EXIT /B 1
)
python main.py
POPD
