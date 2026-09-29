@echo off
rem ===========================================================================
rem PROGRAM_JLCPCB.bat - STM32N657 Flight Controller: program external NOR
rem
rem Target : STM32N657I0H3Q (flashless) + MX25UM25645G octal NOR on XSPI2
rem Probe  : ST-LINK V2/V3 on J20 (SWD).  See ..\documentation\SWD_CONNECTION_DIAGRAM.svg
rem Images : ..\firmware\FC_FSBL_LRUN_Trusted.bin          -> 0x70000000
rem          ..\firmware\FC_Manufacturing_Test_Trusted.bin -> 0x70100000
rem          (the application image ends below 0x70120000; see
rem           EXTERNAL_LOADER_STATUS.md for the exact programmed ranges)
rem Loader : external_loader.stldr in this folder = board loader
rem          MX25UM25645G_STM32N657_FC built from 07_EXTERNAL_LOADER.
rem
rem STATUS : NOT HARDWARE VERIFIED.  This script is the intended procedure;
rem          it has NOT been executed on the custom board, and the loader is
rem          NOT HARDWARE QUALIFIED.  Before production use the engineering
rem          team must complete the loader qualification procedure in
rem          EXTERNAL_LOADER_STATUS.md on first boards.  A different loader
rem          can be passed as the first argument.
rem
rem SAFETY : No ESC / motor / propeller may be connected while programming.
rem          MOTOR_OE_N is held high by R52 at reset; the firmware drives
rem          MOTOR_ENABLE (PA3) low and never starts TIM1/TIM2; the loader
rem          drives PA3 low as well.
rem Environment: FC_CUBEPROG_CLI (path of STM32_Programmer_CLI.exe),
rem              FC_CONNECT_OPTS (extra -c options, default "mode=UR").
rem ===========================================================================
setlocal EnableExtensions

set "HERE=%~dp0"
set "PROG=C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe"
if defined FC_CUBEPROG_CLI set "PROG=%FC_CUBEPROG_CLI%"
rem Connect under reset by default: the loader runs from the SRAM the FSBL/app
rem also execute from; a hot-plug connect could leave stale I-cache lines
rem (07_EXTERNAL_LOADER/README.md). Qualify on the first board; override with
rem FC_CONNECT_OPTS (e.g. "mode=NORMAL").
if not defined FC_CONNECT_OPTS set "FC_CONNECT_OPTS=mode=UR"

set "LOADER=%HERE%external_loader.stldr"
if not "%~1"=="" set "LOADER=%~1"

set "FSBL=%HERE%..\firmware\FC_FSBL_LRUN_Trusted.bin"
set "APP=%HERE%..\firmware\FC_Manufacturing_Test_Trusted.bin"
set "FSBL_ADDR=0x70000000"
set "APP_ADDR=0x70100000"

echo === STM32N657 Flight Controller Programming (NOT HARDWARE VERIFIED) ===
echo Programmer : "%PROG%"
echo Loader     : "%LOADER%"
echo Connect    : port=SWD %FC_CONNECT_OPTS%
echo.
set "ERR=0"
if not exist "%PROG%"   (echo ERROR: STM32_Programmer_CLI.exe not found - install STM32CubeProgrammer 2.22.0 or newer, or set FC_CUBEPROG_CLI & set "ERR=1")
if not exist "%LOADER%" (echo ERROR: external loader not found: "%LOADER%" - see EXTERNAL_LOADER_STATUS.md & set "ERR=1")
if not exist "%FSBL%"   (echo ERROR: missing "%FSBL%" & set "ERR=1")
if not exist "%APP%"    (echo ERROR: missing "%APP%" & set "ERR=1")
if not "%ERR%"=="0" exit /b 2

echo Step 1: Connecting via SWD...
"%PROG%" -c port=SWD %FC_CONNECT_OPTS%
if errorlevel 1 (echo FAIL: no SWD connection ^(J20 wiring / power / NRST^) & exit /b 10)

echo Step 2: Programming FSBL at %FSBL_ADDR% ...
"%PROG%" -c port=SWD %FC_CONNECT_OPTS% --extload "%LOADER%" -w "%FSBL%" %FSBL_ADDR% -v
if errorlevel 1 (echo FAIL: FSBL programming & exit /b 11)

echo Step 3: Programming Application at %APP_ADDR% ...
"%PROG%" -c port=SWD %FC_CONNECT_OPTS% --extload "%LOADER%" -w "%APP%" %APP_ADDR% -v
if errorlevel 1 (echo FAIL: Application programming & exit /b 12)

echo Step 4: Reset...
"%PROG%" -c port=SWD %FC_CONNECT_OPTS% -rst
if errorlevel 1 (echo WARNING: reset command failed - power-cycle the board & exit /b 13)

echo.
echo === Programming Complete ===
echo Next: run VERIFY_JLCPCB.bat, then follow ..\documentation\JLCPCB_TEST_PROCEDURE.md:
echo capture J4 TELEM1 (115200 8N1) to a file and run ..\diagnostics\CHECK_UART_LOG.bat
echo on it. Only "STATION VERDICT: PASS" (exit code 0) accepts the board.
exit /b 0
