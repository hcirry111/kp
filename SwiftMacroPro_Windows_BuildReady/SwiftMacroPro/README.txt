SwiftMacro Pro — Windows macro studio

FEATURES
- Hold-to-run mode: hold a chosen key to run/repeat the macro; releasing it stops.
- Toggle/hotkey mode, start/stop hotkeys, emergency stop.
- Keyboard and mouse recording.
- Manually add key taps, clicks, waits and angle movements.
- Timed angle movement: choose angle 0–360°, distance in pixels and movement duration in milliseconds.
  Example: 90° / 200 px / 250 ms moves down 200 pixels over about a quarter-second.
- Per-action delay, enable/disable, reorder, edit, action limit, repeat count, loop, start delay and repeat interval.
- Save/load profiles as JSON.

BUILD A WINDOWS EXE
1. Install Python 3.10+ for Windows from https://www.python.org/downloads/
2. Extract this folder.
3. Double-click build_exe.bat.
4. When it finishes, find dist\SwiftMacroPro.exe.

RUN FROM SOURCE
Open Command Prompt in this folder and run:
  py -m pip install -r requirements.txt
  py swiftmacro_pro.py

DEFAULT HOTKEYS
F6 = play, F7 = stop, F12 = emergency stop.
In "While key is held" mode, set Hold key to e.g. mouse-independent keyboard key "space".
Keep that key down to run; release it to stop.

NOTES
- This package contains source and a Windows build script; the .exe must be compiled on Windows.
- Extremely short timings may be limited by Windows, the target app/game, and input polling.
- Use only where automation is allowed. Some games prohibit macros or simulated input.
- Start with a harmless test window and modest timings before using in another app.
