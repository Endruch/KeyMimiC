# KeyMimic v2.0

**Professional Keyboard & Mouse Automation Tool for Windows**

## 🎯 Key Features

- ✅ **Simplified Syntax** — Use `press s` instead of `press('s')` - no parentheses or quotes needed!
- ✅ **Global Hotkeys** — Control Record/Start/Stop with F-keys even when app is minimized
- ✅ **Visual Keyboard Editor** — Click keys to generate macro code
- ✅ **Help Dialog** — Built-in key code reference
- ✅ **Individual Thread Logs** — Each thread has its own log
- ✅ **Dynamic Threads** — Add/remove threads as needed
- ✅ **Profile System** — Save and switch between macros
- ✅ **Keyboard Recording** — Record actions in real-time
- ✅ **Low-Level Input** — Uses Windows SendInput API with scan codes
- ✅ **Humanize Mode** — Random timing variations for natural behavior
- ✅ **100% English** — All interface and code in English

## 🚀 Quick Start

### Installation

```bash
cd KeyMimic_2.0
python main.py
```

**Requirements:**
- Python 3.7+
- Windows OS (for actual input)
- tkinter (usually included with Python)

### First Steps

1. Run `python main.py`
2. Click "Help" button to see all key codes
3. Click "Visual Editor" to generate macros by clicking keys
4. Write a macro or use "Record" to record actions
5. Click "Start" to execute

## 📝 Macro Syntax

### Basic Commands (New Simplified Syntax)

```python
# Keyboard - simple and clean!
press s             # Press S key
release s           # Release S key
press ctrl          # Press Ctrl
press enter         # Press Enter
press 31            # Can also use numeric scan codes

# Mouse actions
click               # Left click
right_click         # Right click
move 100 50         # Move mouse (x, y)

# Timing
sleep 1             # Wait 1 second
sleep 5 2           # Wait 5 sec ± 2 sec variation

# Logging
log Starting automation   # Log message (captures to end of line)
```

### Old Syntax (Still Supported)

For backward compatibility, the old syntax still works:

```python
press('s')          # Old way
release(31)         # Old way
sleep(1)            # Old way
```

### Metadata

```python
# thread_name: My Automation
# humanize: 15
```

### Complete Example

```python
# thread_name: WASD Movement
# humanize: 10

log Starting movement

press w
sleep 1
release w

press a
sleep 0.5
release a

click
sleep 0.3

log Complete!
```

## 🎮 Main Features

### 1. Symbolic Key Names

Instead of remembering numeric codes, use friendly names:

```python
# Old way (still works)
press(31)
release(31)

# New way (better!)
press('s')
release('s')
```

**Available names:**
- **Letters**: `'a'`, `'b'`, `'c'`, ..., `'z'`
- **Numbers**: `'1'`, `'2'`, `'3'`, ..., `'0'`
- **Function keys**: `'f1'`, `'f2'`, ..., `'f12'`
- **Modifiers**: `'ctrl'`, `'shift'`, `'alt'`, `'win'`
- **Special**: `'enter'`, `'space'`, `'tab'`, `'esc'`, `'backspace'`
- **Arrows**: `'up'`, `'down'`, `'left'`, `'right'`
- **And 60+ more!**

See complete list by clicking "Help" button.

### 2. Visual Keyboard Editor

Click the "Visual Editor" button to:
- See a full QWERTY keyboard layout
- Click keys to generate code
- Toggle modifiers (Ctrl/Shift/Alt)
- Insert sleep delays
- Generate macro code automatically

Perfect for beginners or quick macro creation!

### 3. Help Dialog

Click "Help" button to see:
- All available key names
- Numeric scan codes
- Organized by category
- Both symbolic and numeric formats

### 4. Thread Management

- **Add Thread**: "+" button
- **Remove Thread**: "X" in panel header
- **Individual Logs**: Each thread has its own log
- **Independent Execution**: Threads run separately

### 5. Profile System

- **Select Profile**: Dropdown menu
- **Create**: "+" button
- **Rename**: "Edit" button
- **Delete**: "Del" button
- **Auto-save**: Saves while editing

### 6. Keyboard Recording

1. Click "Record" button
2. Press keys
3. Click "Stop Recording"
4. Profile automatically created

## 🔧 Key Code Reference

### Letters (symbolic names)
```python
'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'
'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'
'z', 'x', 'c', 'v', 'b', 'n', 'm'
```

### Numbers
```python
'1', '2', '3', '4', '5', '6', '7', '8', '9', '0'
```

### Function Keys
```python
'f1', 'f2', 'f3', 'f4', 'f5', 'f6',
'f7', 'f8', 'f9', 'f10', 'f11', 'f12'
```

### Modifiers
```python
'shift', 'lshift', 'rshift'
'ctrl', 'lctrl', 'rctrl'
'alt', 'lalt', 'ralt'
'win', 'lwin', 'rwin'
```

### Special Keys
```python
'esc', 'tab', 'caps', 'space', 'enter',
'backspace', 'delete', 'insert'
```

### Arrows
```python
'up', 'down', 'left', 'right'
```

### Navigation
```python
'home', 'end', 'pageup', 'pagedown'
```

For complete list with numeric codes, click **Help** button in the app!

## 📁 File Structure

```
KeyMimic_2.0/
├── main.py                    # Application entry point
├── keymimic/
│   ├── core/                  # Core functionality
│   │   ├── constants.py       # Scan codes
│   │   ├── key_names.py       # Symbolic name mappings
│   │   ├── input_sender.py    # Windows API
│   │   ├── macro_parser.py    # Parser with aliases
│   │   ├── macro_runner.py    # Executor
│   │   └── recorder.py        # Keyboard recording
│   ├── gui/                   # User interface
│   │   ├── main_window.py     # Main window
│   │   ├── thread_panel.py    # Thread panel
│   │   ├── help_dialog.py     # Help window
│   │   └── visual_editor.py   # Visual keyboard
│   └── utils/                 # Utilities
│       └── profile_manager.py # Profile management
└── README.md                  # This file
```

## 💾 Data Location

Profiles saved in:
```
Documents/KeyMimic/profiles/
├── thread_1_profiles.json
├── thread_2_profiles.json
└── ...
```

## 🎓 Tips

1. **Simple syntax** — No parentheses or quotes needed!
2. **Use Visual Editor** — Quick macro creation
3. **Check Help** — Reference for all key names
4. **Test without loop** — Verify macros first
5. **Check thread logs** — Each thread shows its own activity
6. **Use humanize** — More natural in games
7. **Name profiles** — Easy to find later
8. **Configure hotkeys** — Click Settings to customize F-key shortcuts

## 📚 Example Macros

### Simple Movement
```python
# WASD movement
press w
sleep 1
release w
```

### With Modifiers
```python
# Ctrl+C to copy
press ctrl
press c
sleep 0.1
release c
release ctrl
```

### Mouse Actions
```python
# Click and move
click
sleep 0.5
move 100 50
right_click
```

### Loop with Humanize
```python
# thread_name: Farm Bot
# humanize: 15

press f1
sleep 0.1
release f1
sleep 2
click
sleep 1.5
```

## ⚠️ Important

- Works **only on Windows**
- May need admin rights for some games
- Some anti-cheats may block it
- Use responsibly within game/app rules

## 🔄 Version History

### v2.0.0 (Current)
- ✅ **Simplified syntax** - `press s` instead of `press('s')`
- ✅ **Global hotkeys** - Control with F-keys even when app is minimized
- ✅ **Hotkey configuration** - Customize Record/Start/Stop shortcuts in Settings
- ✅ 100% English interface and code
- ✅ Visual keyboard editor
- ✅ Help dialog with key codes
- ✅ Mouse action aliases
- ✅ Individual thread logs
- ✅ Modular architecture
- ✅ Backward compatible with old syntax

### v1.0.0
- Basic functionality
- 2 static threads
- Shared log
- Russian interface

## 📄 License

Free to use.

---

**Made with ❤️ for automation enthusiasts**

Need help? Click the **Help** button in the app!
