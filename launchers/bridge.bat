@echo off
REM Ring 3 / retail: the NGPC<->Flycast bridge, pure passthrough.
REM Start it before Flycast and before the NGPC side.
call "%~dp0_common.bat" || exit /b 1
set BRIDGE_LOG=
if not "%LINK_LOGS%"=="" set BRIDGE_LOG=%LINK_LOGS%\bridge.log
python "%~dp0..\bridge\bridge.py"
