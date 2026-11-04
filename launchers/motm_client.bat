@echo off
REM Retail: MOTM as TCP client of the bridge, talking to Capcom vs. SNK: Millennium Fight 2000 on Flycast. Retail ROMs must run with NGPC_LINK_MMIO=0: the side-channel corrupts their RAM.
call "%~dp0_common.bat" || exit /b 1
set NGPC_LINK_ROLE=client
set NGPC_LINK_HOST=127.0.0.1
set NGPC_LINK_PORT=42424
set NGPC_LINK_MMIO=0
"%RETROARCH%" -L "%NGPC_CORE%" "%MOTM_ROM%"
