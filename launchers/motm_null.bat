@echo off
REM Retail capture: MOTM in null mode, no backend, log only. MOTM sees a dead link exactly like on the stock core, but every comms call is logged.
call "%~dp0_common.bat" || exit /b 1
set NGPC_LINK_ROLE=null
set NGPC_LINK_HOST=127.0.0.1
set NGPC_LINK_PORT=42424
set NGPC_LINK_MMIO=0
"%RETROARCH%" -L "%NGPC_CORE%" "%MOTM_ROM%"
