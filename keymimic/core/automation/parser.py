"""
Clean macro parser with unified syntax.

Format:
    # thread_name: MyMacro
    # humanize: 15
    press s
    press s 2.5
    release s
    sleep 1.0
    click
    right_click
    move 100 50
    log "message"

Only supports space-separated syntax (no parentheses).
"""

import re


# Metadata patterns
_THREAD_NAME_RE = re.compile(r'#\s*thread_name\s*:\s*(.+)', re.IGNORECASE)
_HUMANIZE_RE = re.compile(r'#\s*humanize\s*:\s*([\d.]+)', re.IGNORECASE)

# Command pattern: command_name arg1 arg2 ...
_COMMAND_RE = re.compile(r'^\s*(\w+)\s+(.+?)(?:\s*#.*)?$', re.MULTILINE)

# Commands with no arguments
_NO_ARG_COMMANDS = {'click', 'right_click'}


def _parse_arguments(argstr):
    """
    Parse space-separated arguments.

    Supports:
    - Quoted strings: "hello world"
    - Integers: 42
    - Floats: 3.14
    - Unquoted strings: s, ctrl, hello

    Returns:
        List of parsed arguments
    """
    args = []
    if not argstr.strip():
        return args

    # Extract tokens: quoted strings or space-separated words
    tokens = re.findall(r'"[^"]*"|\'[^\']*\'|[^\s]+', argstr)

    for token in tokens:
        token = token.strip()

        # String literal (quoted) - remove quotes
        if (token.startswith('"') and token.endswith('"')) or \
           (token.startswith("'") and token.endswith("'")):
            args.append(token[1:-1])
            continue

        # Try integer
        try:
            args.append(int(token))
            continue
        except ValueError:
            pass

        # Try float
        try:
            args.append(float(token))
            continue
        except ValueError:
            pass

        # Otherwise keep as string (key name or text)
        args.append(token)

    return args


def parse_macro(text):
    """
    Parse macro text and extract metadata and commands.

    Args:
        text: Macro text with metadata and commands

    Returns:
        Tuple: (metadata, commands)
        - metadata: dict with 'thread_name' and 'humanize'
        - commands: list of (command_name, [args]) tuples

    Example:
        metadata, commands = parse_macro(text)
        # metadata = {'thread_name': 'MyMacro', 'humanize': 15}
        # commands = [('press', ['s']), ('sleep', [1.0]), ('release', ['s'])]
    """
    # Extract metadata
    metadata = {
        'thread_name': None,
        'humanize': 0
    }

    m = _THREAD_NAME_RE.search(text)
    if m:
        metadata['thread_name'] = m.group(1).strip()

    m = _HUMANIZE_RE.search(text)
    if m:
        metadata['humanize'] = int(float(m.group(1)))

    # Remove comment-only lines and empty lines
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        # Skip empty lines and pure comment lines
        if not stripped or stripped.startswith('#'):
            continue
        lines.append(line)

    cleaned_text = '\n'.join(lines)

    # Extract commands
    commands = []
    for name, argstr in _COMMAND_RE.findall(cleaned_text):
        args = _parse_arguments(argstr)
        commands.append((name, args))

    # Handle no-arg commands (e.g., "click" without arguments)
    for line in cleaned_text.split('\n'):
        stripped = line.strip()
        if not stripped or '#' in stripped:
            continue
        parts = stripped.split()
        if len(parts) == 1 and parts[0] in _NO_ARG_COMMANDS:
            commands.append((parts[0], []))

    return metadata, commands


def validate_commands(commands):
    """
    Validate command list for correct syntax.

    Args:
        commands: List of (command_name, [args]) tuples

    Raises:
        ValueError: If command is unknown or has wrong number of arguments

    Returns:
        None if valid
    """
    # Valid commands with (min_args, max_args)
    # None means unlimited
    VALID_COMMANDS = {
        'press': (1, 2),       # press key [duration]
        'release': (1, 1),     # release key
        'click': (0, 0),       # click
        'right_click': (0, 0), # right_click
        'move': (2, 2),        # move dx dy (relative)
        'move_to': (2, 2),     # move_to x y (absolute)
        'sleep': (1, 2),       # sleep duration [variation]
        'log': (1, 1),         # log message
        'wait_with_keys': (1, None),  # wait_with_keys key1 key2 ...
    }

    for name, args in commands:
        if name not in VALID_COMMANDS:
            raise ValueError(f"Unknown command: {name}")

        min_args, max_args = VALID_COMMANDS[name]

        if len(args) < min_args:
            raise ValueError(f"Command '{name}' requires at least {min_args} argument(s), got {len(args)}")

        if max_args is not None and len(args) > max_args:
            raise ValueError(f"Command '{name}' accepts at most {max_args} argument(s), got {len(args)}")
