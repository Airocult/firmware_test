@echo off
rem ===========================================================================
rem READ_DIAG_LOG.bat - SWD FALLBACK result path of the STM32N657 FC
rem manufacturing test (the PRIMARY path is the UART capture, see
rem CHECK_UART_LOG.bat and ..\documentation\JLCPCB_TEST_PROCEDURE.md).
rem
rem Self-contained: everything it needs is in THIS folder
rem   App_diag_addr.txt     address of fc_diag_log in the released firmware
rem   EXPECTED_BUILD_ID.txt build id of the released firmware
rem   decode_diag_log.py + fc_station_common.py   (Python 3, standard library)
rem
rem Usage:
rem   READ_DIAG_LOG.bat start   invalidate the old log (write 0 to its magic
rem                             word over SWD) and reset the board so a fresh
rem                             run starts; a log that is never rewritten can
rem                             then never be mistaken for a result
rem   READ_DIAG_LOG.bat read    hot-plug connect (no reset, no halt), read the
rem                             16512-byte log, decode it, print STATION VERDICT
rem Exit code of "read" = decoder verdict: 0 PASS, 1 FAIL, 2 INCOMPLETE,
rem 3 ABORTED, 4 INVALID, 10 SWD/read problem.  ONLY 0 accepts the board;
rem a log that merely decodes is not a PASS.
rem
rem Coherency: the firmware keeps the log in MPU non-cacheable SRAM, so an
rem SWD read always returns current data (no cache maintenance needed).
rem Environment: FC_CUBEPROG_CLI (path of STM32_Programmer_CLI.exe),
rem FC_CONNECT_OPTS (extra -c options, default for "read": mode=HOTPLUG).
rem STATUS: NOT HARDWARE VERIFIED (CubeProgrammer 2.22 syntax; the HOTPLUG
rem read and the SWD access to SRAM during a stalled test must be confirmed
rem on the first board, JLCPCB_TEST_PROCEDURE.md).
rem ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion

set "HERE=%~dp0"
set "PROG=C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe"
if defined FC_CUBEPROG_CLI set "PROG=%FC_CUBEPROG_CLI%"
set "ADDR_FILE=%HERE%App_diag_addr.txt"
set "ID_FILE=%HERE%EXPECTED_BUILD_ID.txt"
set "OUT=%HERE%diag_log.bin"
set "DIAG_SIZE=16512"

if not exist "%PROG%" (echo ERROR: STM32_Programmer_CLI.exe not found: "%PROG%" ^(set FC_CUBEPROG_CLI^) & exit /b 10)
if not exist "%ADDR_FILE%" (echo ERROR: "%ADDR_FILE%" missing - incomplete package & exit /b 10)
if not exist "%ID_FILE%" (echo ERROR: "%ID_FILE%" missing - incomplete package & exit /b 10)
set "ADDR="
for /f "usebackq tokens=1 delims= " %%a in ("%ADDR_FILE%") do if not defined ADDR set "ADDR=%%a"
set "BUILD_ID="
for /f "usebackq tokens=1 delims= " %%a in ("%ID_FILE%") do if not defined BUILD_ID set "BUILD_ID=%%a"
if not defined ADDR (echo ERROR: App_diag_addr.txt is empty & exit /b 10)
if /i not "%ADDR:~0,2%"=="0x" (echo ERROR: address "%ADDR%" is not 0x-prefixed & exit /b 10)

set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"

if /i "%~1"=="start" goto :start
if /i "%~1"=="read" goto :read
echo usage: READ_DIAG_LOG.bat start ^| read
exit /b 10

:start
echo Invalidating the diagnostic log at %ADDR% and resetting the board...
"%PROG%" -c port=SWD %FC_CONNECT_OPTS% -w32 %ADDR% 0x00000000 -rst
if errorlevel 1 (echo FAIL: SWD write/reset failed - check J20 wiring and power & exit /b 10)
echo Board reset: the test is running. Wait for the station time-out
echo ^(see JLCPCB_TEST_PROCEDURE.md^) or the LED heartbeat, then run: READ_DIAG_LOG.bat read
exit /b 0

:read
if not defined PY (echo ERROR: Python 3 not found on PATH - install it or use the UART procedure & exit /b 10)
set "CONN=%FC_CONNECT_OPTS%"
if not defined CONN set "CONN=mode=HOTPLUG"
if exist "%OUT%" del /f /q "%OUT%" >nul 2>&1
echo Reading fc_diag_log at %ADDR%, %DIAG_SIZE% bytes (expected build %BUILD_ID%)...
"%PROG%" -c port=SWD %CONN% -u %ADDR% %DIAG_SIZE% "%OUT%"
if not exist "%OUT%" (echo FAIL: no data read ^(SWD connection? address?^) & exit /b 10)
!PY! "%HERE%decode_diag_log.py" "%OUT%" --expect-build-id %BUILD_ID%
exit /b %ERRORLEVEL%
