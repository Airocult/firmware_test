@echo off
rem ===========================================================================
rem VERIFY_JLCPCB.bat - STM32N657 Flight Controller: verify external NOR content
rem
rem Reads back each image region from the NOR through the external loader and
rem compares it byte-for-byte (fc /b) with the shipped file.  This does not
rem depend on the "-v" option semantics of a particular CubeProgrammer version.
rem
rem STATUS : NOT HARDWARE VERIFIED.  Intended procedure only; never executed
rem          on the custom board.  Uses the same loader as PROGRAM_JLCPCB.bat
rem          (external_loader.stldr in this folder, NOT HARDWARE QUALIFIED;
rem          another loader can be passed as the first argument).
rem Environment: FC_CUBEPROG_CLI, FC_CONNECT_OPTS (extra -c options, default "mode=UR").
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
set "RB_FSBL=%TEMP%\fc_readback_fsbl.bin"
set "RB_APP=%TEMP%\fc_readback_app.bin"

echo === STM32N657 Flight Controller Verification (NOT HARDWARE VERIFIED) ===
set "ERR=0"
if not exist "%PROG%"   (echo ERROR: STM32_Programmer_CLI.exe not found ^(set FC_CUBEPROG_CLI^) & set "ERR=1")
if not exist "%LOADER%" (echo ERROR: external loader not found: "%LOADER%" & set "ERR=1")
if not exist "%FSBL%"   (echo ERROR: missing "%FSBL%" & set "ERR=1")
if not exist "%APP%"    (echo ERROR: missing "%APP%" & set "ERR=1")
if not "%ERR%"=="0" exit /b 2

for %%F in ("%FSBL%") do set "FSBL_SIZE=%%~zF"
for %%F in ("%APP%") do set "APP_SIZE=%%~zF"

echo Step 1: Connecting via SWD...
"%PROG%" -c port=SWD %FC_CONNECT_OPTS%
if errorlevel 1 (echo FAIL: no SWD connection & exit /b 10)

echo Step 2: Reading back FSBL region (%FSBL_SIZE% bytes at %FSBL_ADDR%)...
if exist "%RB_FSBL%" del /f /q "%RB_FSBL%"
"%PROG%" -c port=SWD %FC_CONNECT_OPTS% --extload "%LOADER%" -u %FSBL_ADDR% %FSBL_SIZE% "%RB_FSBL%"
if not exist "%RB_FSBL%" (echo FAIL: FSBL read-back produced no file & exit /b 11)
fc /b "%FSBL%" "%RB_FSBL%" >nul
if errorlevel 1 (echo FAIL: FSBL region differs from FC_FSBL_LRUN_Trusted.bin & exit /b 12)
echo   FSBL region matches.

echo Step 3: Reading back Application region (%APP_SIZE% bytes at %APP_ADDR%)...
if exist "%RB_APP%" del /f /q "%RB_APP%"
"%PROG%" -c port=SWD %FC_CONNECT_OPTS% --extload "%LOADER%" -u %APP_ADDR% %APP_SIZE% "%RB_APP%"
if not exist "%RB_APP%" (echo FAIL: Application read-back produced no file & exit /b 13)
fc /b "%APP%" "%RB_APP%" >nul
if errorlevel 1 (echo FAIL: Application region differs from FC_Manufacturing_Test_Trusted.bin & exit /b 14)
echo   Application region matches.

echo.
echo === NOR content verified (byte compare) ===
echo This proves the NOR content only.  The board verdict comes from the console
echo report: ..\diagnostics\CHECK_UART_LOG.bat ^(see ..\documentation\JLCPCB_TEST_PROCEDURE.md^)
exit /b 0
