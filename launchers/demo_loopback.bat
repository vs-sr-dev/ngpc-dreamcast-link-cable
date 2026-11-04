@echo off
REM Ring 1: hello_link demo, in-process loopback (every byte sent comes straight back).
call "%~dp0_common.bat" || exit /b 1
set NGPC_LINK_ROLE=
set NGPC_LINK_HOST=127.0.0.1
set NGPC_LINK_PORT=42424
set NGPC_LINK_MMIO=1
"%RETROARCH%" -L "%NGPC_CORE%" "%NGPC_DEMO_ROM%"
