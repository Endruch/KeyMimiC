"""
Macro parsing and command extraction.
Supports both numeric codes and friendly key names.
Supports both old syntax (press('s')) and new syntax (press s).
"""

import re
from .key_names import resolve_key, MOUSE_ACTIONS


# Old syntax: press('s') - with parentheses
_CALL_RE = re.compile(r'(\w+)\s*\(([^)]*)\)')

# New syntax: press s - without parentheses (line-based)
_SIMPLE_RE = re.compile(r'^\s*(\w+)\s+(.+?)(?:\s*#.*)?$', re.MULTILINE)


def _parse_args(argstr):
    """
    Parse function arguments from string.
    Handles strings, numbers, and key names (e.g., 's', 'ctrl', etc.)
    """
    args = []
    if not argstr.strip():
        return args

    for token in re.findall(r'"[^"]*"|\'[^\']*\'|[^,]+', argstr):
        token = token.strip()

        # String literal
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

        # Otherwise keep as string (will be resolved later if it's a key name)
        args.append(token)

    return args


def _parse_args_simple(argstr):
    """
    Parse space-separated arguments (new syntax without parentheses).
    Handles strings, numbers, and key names.
    """
    args = []
    if not argstr.strip():
        return args

    # Extract tokens: quoted strings or space-separated words
    tokens = re.findall(r'"[^"]*"|\'[^\']*\'|[^\s]+', argstr)

    for token in tokens:
        token = token.strip()

        # String literal (quoted)
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
    Supports both old syntax: press('s') and new syntax: press s

    Returns:
        tuple: (thread_name, humanize_percent, [(command, [args]), ...])
    """
    thread_name = None
    humanize = 0.0

    # Extract metadata
    m = re.search(r'#\s*thread_name\s*:\s*(.+)', text)
    if m:
        thread_name = m.group(1).strip()

    m = re.search(r'#\s*humanize\s*:\s*([\d.]+)', text)
    if m:
        humanize = float(m.group(1))

    commands = []

    # Try new syntax first (line-based, without parentheses)
    simple_commands = _SIMPLE_RE.findall(text)
    if simple_commands:
        for name, argstr in simple_commands:
            # Resolve mouse action aliases
            if name in MOUSE_ACTIONS:
                name = MOUSE_ACTIONS[name]
            commands.append((name, _parse_args_simple(argstr)))
    else:
        # Fall back to old syntax (with parentheses)
        # Remove comments and flatten
        cleaned_lines = [re.sub(r'#.*$', '', line) for line in text.split('\n')]
        flat = ' '.join(cleaned_lines)

        # Extract commands
        for name, argstr in _CALL_RE.findall(flat):
            # Resolve mouse action aliases
            if name in MOUSE_ACTIONS:
                name = MOUSE_ACTIONS[name]
            commands.append((name, _parse_args(argstr)))

    return thread_name, humanize, commands
