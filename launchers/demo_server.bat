@echo off
REM Ring 2: hello_link demo hosting the TCP link (pair with demo_client.bat).
call "%~dp0_common.bat" || exit /b 1
set NGPC_LINK_ROLE=server
set NGPC_LINK_HOST=127.0.0.1
set NGPC_LINK_PORT=42424
set NGPC_LINK_MMIO=1
"%RETROARCH%" -L "%NGPC_CORE%" "%NGPC_DEMO_ROM%"
