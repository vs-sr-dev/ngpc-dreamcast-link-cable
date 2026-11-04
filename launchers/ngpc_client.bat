@echo off
REM Retail: any NGPC game as TCP client of the bridge.
REM   ngpc_client.bat "C:\path\to\game.ngc"     (default: MOTM_ROM)
REM Retail ROMs must run with NGPC_LINK_MMIO=0: the side-channel corrupts their RAM.
call "%~dp0_common.bat" || exit /b 1
set ROM=%~1
if "%ROM%"=="" set ROM=%MOTM_ROM%
set NGPC_LINK_ROLE=client
set NGPC_LINK_HOST=127.0.0.1
set NGPC_LINK_PORT=42424
set NGPC_LINK_MMIO=0
"%RETROARCH%" -L "%NGPC_CORE%" "%ROM%"
