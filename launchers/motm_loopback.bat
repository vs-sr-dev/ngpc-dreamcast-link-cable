@echo off
REM Retail capture: MOTM in loopback, no peer. Every comms call is logged (LINK_LOGS must be set). Use it to record what MOTM emits on Olympic > Send to DC.
call "%~dp0_common.bat" || exit /b 1
set NGPC_LINK_ROLE=
set NGPC_LINK_HOST=127.0.0.1
set NGPC_LINK_PORT=42424
set NGPC_LINK_MMIO=0
"%RETROARCH%" -L "%NGPC_CORE%" "%MOTM_ROM%"
