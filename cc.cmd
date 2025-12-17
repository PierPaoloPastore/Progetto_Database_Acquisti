@echo off
setlocal EnableExtensions

REM ============================================================
REM cc.cmd - Codex Compound wrapper (robusto su Windows CMD)
REM Usa: codex exec - (prompt da stdin) per evitare problemi di quoting
REM ============================================================

if "%~1"=="" goto :help

set "MODE=%~1"
shift

if /I "%MODE%"=="help" goto :help
if /I "%MODE%"=="/?" goto :help
if /I "%MODE%"=="-h" goto :help
if /I "%MODE%"=="--help" goto :help
if /I "%MODE%"=="docs" goto :docs

set "TASK=%*"
if "%TASK%"=="" goto :help

set "PREFIX=Follow the repo AGENTS.md. Use the Mandatory Compound Workflow definitions in AGENTS.md."
set "SUFFIX="

if /I "%MODE%"=="plan"   goto :mode_plan
if /I "%MODE%"=="do"     goto :mode_do
if /I "%MODE%"=="review" goto :mode_review
if /I "%MODE%"=="verify" goto :mode_verify

echo Unknown mode: %MODE%
echo.
goto :help

:mode_plan
set "SUFFIX=SPEC + PLAN only. STOP after PLAN. Do NOT implement. Ask for confirmation if risky. Task:"
goto :run

:mode_do
set "SUFFIX=SPEC + PLAN + IMPLEMENT + VERIFY. Keep changes minimal and coherent. Task:"
goto :run

:mode_review
set "SUFFIX=Brief SPEC then REVIEW only: risks, regressions, duplication, layer violations, checklist. Do NOT implement unless asked. Task:"
goto :run

:mode_verify
set "SUFFIX=VERIFY only: exact commands, SQL/curl checks if relevant, manual verification checklist. Do NOT implement. Task:"
goto :run

:run
set "PROMPT_TEXT=%PREFIX% %SUFFIX% %TASK%"

set "TMPFILE=%TEMP%\codex_prompt_cc.txt"

REM Scrive il prompt in modo sicuro usando PowerShell (evita problemi con &, |, quotes, ecc.)
powershell -NoProfile -Command ^
  "$p = [Environment]::GetEnvironmentVariable('PROMPT_TEXT');" ^
  "Set-Content -LiteralPath '%TMPFILE%' -Value $p -Encoding UTF8"

type "%TMPFILE%" | codex exec -
exit /b 0

:docs
set "SCRIPT_PY=scripts\generate_codex_context.py"
set "OUT_MD=docs\CODEX_CONTEXT.md"

if exist "%SCRIPT_PY%" (
  echo [cc] Regenerating %OUT_MD% using %SCRIPT_PY% ...
  python "%SCRIPT_PY%"
  if errorlevel 1 (
    echo [cc] ERROR: context generation script failed.
    exit /b 1
  )
  echo [cc] Done.
  exit /b 0
)

echo [cc] No generator found at "%SCRIPT_PY%".
echo [cc] Create it to generate %OUT_MD%, then run: cc docs
exit /b 1

:help
echo Usage:
echo   cc plan   ^<task...^>
echo   cc do     ^<task...^>
echo   cc review ^<task...^>
echo   cc verify ^<task...^>
echo   cc docs
echo.
echo Example:
echo   cc plan Aggiungi nella schermata /documents/ i filtri Intestatario, Numero e Data
exit /b 1
