@echo off
REM Rings 2-3: hello_link demo as TCP client: to demo_server.bat (Ring 2) or to the bridge (Ring 3). The demo reads the 0x6BFC/0x6BFD side-channel, hence NGPC_LINK_MMIO=1.
call "%~dp0_common.bat" || exit /b 1
set NGPC_LINK_ROLE=client
set NGPC_LINK_HOST=127.0.0.1
set NGPC_LINK_PORT=42424
set NGPC_LINK_MMIO=1
"%RETROARCH%" -L "%NGPC_CORE%" "%NGPC_DEMO_ROM%"
