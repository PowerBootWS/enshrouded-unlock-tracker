@echo off
rem Edit these paths, then use this file instead of launching Enshrouded directly.
set INI=C:\Path\To\your-unlocks.ini
set MOD=C:\Program Files (x86)\Steam\steamapps\common\Enshrouded\mods\endless-chests-solo

py "%~dp0enshrouded_unlocks.py" --ini "%INI%" --dll "%MOD%\bin\endless-chests-solo.dll" --chest-ini "%MOD%\endless-chests.ini"
if errorlevel 1 (
  pause
  exit /b 1
)
start "" steam://rungameid/1203620
