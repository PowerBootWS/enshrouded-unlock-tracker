@echo off
rem Steam pre-launch hook. In Steam: Enshrouded > Properties > Launch Options, enter:
rem   "C:\Path\To\steam-prelaunch.bat" %command%
rem Edit these paths:
set INI=C:\Path\To\your-unlocks.ini
set MOD=C:\Program Files (x86)\Steam\steamapps\common\Enshrouded\mods\endless-chests-solo
rem Optional: full path to python.exe if Steam cannot find Python on its own, e.g.
rem set PYTHON=C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe
set PYTHON=

rem Record what Steam passed, for troubleshooting.
echo %date% %time% args: %* > "%~dp0last-launch.txt"

if not defined PYTHON where py >nul 2>&1 && set PYTHON=py
if not defined PYTHON where python >nul 2>&1 && set PYTHON=python
if not defined PYTHON (
  echo Python not found. Set PYTHON at the top of this file to the full path of python.exe.
  pause
  goto launch
)

"%PYTHON%" "%~dp0enshrouded_unlocks.py" --ini "%INI%" --dll "%MOD%\bin\endless-chests-solo.dll" --chest-ini "%MOD%\endless-chests.ini" >> "%~dp0last-launch.txt" 2>&1
if errorlevel 1 (
  echo Unlock filter failed - see last-launch.txt. The game will start with the previous chest settings.
  pause
)

:launch
rem Run the game in this window and wait, so Steam sees it as running until you quit.
%*
