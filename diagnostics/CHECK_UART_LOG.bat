@echo off
rem ===========================================================================
rem CHECK_UART_LOG.bat - PRIMARY result path of the STM32N657 FC manufacturing
rem test: evaluates a USART1 capture (J4 TELEM1, 115200 8N1) saved to a file
rem by the station terminal program.
rem
rem   CHECK_UART_LOG.bat <capture file>
rem
rem Exit code / STATION VERDICT: 0 PASS, 1 FAIL, 2 INCOMPLETE, 3 ABORTED,
rem 4 INVALID (corrupt capture, wrong firmware build, board reset during the
rem test). ONLY 0 accepts the board. Uses parse_station_log.py and
rem fc_station_common.py from this folder and the build id in
rem EXPECTED_BUILD_ID.txt (Python 3, standard library). Without Python apply
rem the manual rules of ..\documentation\PASS_FAIL_CRITERIA.md.
rem STATUS: NOT HARDWARE VERIFIED (validated on PC-generated captures).
rem ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion
set "HERE=%~dp0"
if "%~1"=="" (echo usage: CHECK_UART_LOG.bat ^<capture file^> & exit /b 10)
if not exist "%~1" (echo ERROR: capture file not found: "%~1" & exit /b 2)
set "BUILD_ID="
for /f "usebackq tokens=1 delims= " %%a in ("%HERE%EXPECTED_BUILD_ID.txt") do if not defined BUILD_ID set "BUILD_ID=%%a"
if not defined BUILD_ID (echo ERROR: EXPECTED_BUILD_ID.txt missing or empty - incomplete package & exit /b 10)
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (echo ERROR: Python 3 not found on PATH - use the manual rules in PASS_FAIL_CRITERIA.md & exit /b 10)
!PY! "%HERE%parse_station_log.py" "%~1" --expect-build-id %BUILD_ID%
exit /b %ERRORLEVEL%
