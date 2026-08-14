"""
Wire format for the LAN remote-control connection between two KeyMiglic
instances (see SPEC.md for the full design). Newline-delimited JSON over a
single TCP socket - once connected, both sides are equal peers and can send
any of these message types in either direction:

    {"type": "arm"}                               - CapsLock just turned on
                                                       here, forwarding starts
    {"type": "disarm"}                            - CapsLock just turned off
                                                       here, forwarding stops
    {"type": "key", "key": <id>, "down": <bool>}  - a forwarded key press/
                                                       release
    {"type": "script_status", "running": <bool>}  - this side's macro just
                                                       started/stopped

`key` values are the same internal key-id strings used everywhere else in
the app (see core.constants.SCAN_CODES) - never a raw scan code, so both
machines only need to agree on the key's *name*, not its hardware layout.
"""

NET_PORT = 51955
