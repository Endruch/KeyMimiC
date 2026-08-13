# KeyMiglic

## What it is

KeyMiglic is a keyboard and mouse macro recorder and player. It remembers real keystrokes, clicks, and mouse movements exactly as you performed them, then can play them back — once or in a loop — with the same pauses and hold durations as the original recording.

Useful anywhere you need to repeat the same sequence of actions: game routines, repetitive tasks in applications, or automating anything on your computer you're tired of doing by hand.

## How to use it

1. Press **Record** (or the record hotkey) and perform the keyboard and/or mouse actions the way you want them played back.
2. Press **Stop Recording** — the recording is saved as a new profile.
3. Optionally, open the recording in the editor and adjust it: remove extra steps, enable/disable individual steps, add a Repeat, or set pauses manually.
4. Press **Start** to play the macro back — once, or in a loop (the **Loop** checkbox).
5. All the main actions (Start, Stop, start/stop recording) can be bound to global hotkeys — they work even while the program window is minimized.

Profiles are saved on disk as separate files - you can move them between computers by copying the file into the right folder.

## ⚠️ Warning

Many online games and services prohibit macros and input automation in their rules and may ban your account for using them - regardless of what tool was used. Check the rules of the specific game or application before using it there, and assess the risk yourself. The author is not responsible for the consequences of using this program where it's prohibited.

## Build

```powershell
cd Desktop; Remove-Item KeyMimiC -Recurse -Force -ErrorAction SilentlyContinue; git clone -b keymimic-v3 --single-branch https://github.com/Endruch/KeyMimiC.git; cd KeyMimiC; pip install -r requirements.txt pyinstaller; pyinstaller --onefile --windowed --name KeyMiglic --icon assets\icon.ico --add-data "assets;assets" main.py
```
