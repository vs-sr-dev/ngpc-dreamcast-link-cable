@echo off
REM Copy this file to config.bat (git-ignored) and edit the paths.
REM Every launcher in this folder calls config.bat first.

REM RetroArch executable (any recent Windows build).
set RETROARCH=C:\RetroArch\retroarch.exe

REM The patched beetle-ngp core you built (see docs/SETUP.md).
set NGPC_CORE=%~dp0..\build\mednafen_ngp_libretro.dll

REM The hello_link NGPC demo ROM you built.
set NGPC_DEMO_ROM=%~dp0..\homebrew\ngpc_hello_link\bin\main.ngp

REM BYOA: your own dump of SNK vs. Capcom: The Match of the Millennium.
set MOTM_ROM=C:\path\to\your\SNK vs. Capcom - The Match of the Millennium (World) (En,Ja).ngc

REM Where the core and the bridge write their logs. Leave empty to disable.
set LINK_LOGS=%~dp0..\logs

REM Real Dreamcast on a USB-UART adapter (bridge_serial.bat): COM port and speed.
set DC_SERIAL=COM7
set DC_BAUD=19200
