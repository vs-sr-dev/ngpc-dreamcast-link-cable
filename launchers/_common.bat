@echo off
REM Shared prologue: load config.bat, prepare the log directory.
if not exist "%~dp0config.bat" (
  echo launchers\config.bat not found: copy config.example.bat to config.bat and edit it.
  exit /b 1
)
call "%~dp0config.bat"
set NGPC_LINK_LOG_DIR=
if not "%LINK_LOGS%"=="" (
  if not exist "%LINK_LOGS%" mkdir "%LINK_LOGS%"
  set NGPC_LINK_LOG_DIR=%LINK_LOGS%
)
exit /b 0
