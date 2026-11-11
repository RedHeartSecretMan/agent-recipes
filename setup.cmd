@echo off
setlocal
bun "%~dp0setup" %*
exit /b %ERRORLEVEL%
