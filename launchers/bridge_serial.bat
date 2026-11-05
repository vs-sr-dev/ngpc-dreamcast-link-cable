@echo off
REM Real Dreamcast: the bridge talks to the console's serial port through a
REM USB-UART adapter instead of to Flycast. Needs pyserial. Experimental.
REM Then run: python tools\first_contact.py   (MF2K on Download Stand By)
call "%~dp0_common.bat" || exit /b 1
set BRIDGE_SERIAL=%DC_SERIAL%
set BRIDGE_BAUD=%DC_BAUD%
set BRIDGE_LOG=
if not "%LINK_LOGS%"=="" set BRIDGE_LOG=%LINK_LOGS%\bridge_serial.log
python "%~dp0..\bridge\bridge.py"
