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
    {"type": "ping"}                              - keepalive, no action taken
                                                       on receipt - see peer_connection.py

`key` values are the same internal key-id strings used everywhere else in
the app (see core.constants.SCAN_CODES) - never a raw scan code, so both
machines only need to agree on the key's *name*, not its hardware layout.
"""

NET_PORT = 51955

# A silent connection (peer machine slept, wifi dropped, cable pulled) can
# otherwise sit "connected" from this side's point of view for a very long
# time - TCP has no built-in keepalive by default, so recv() would simply
# block forever with nothing ever arriving. HEARTBEAT_INTERVAL_S is how
# often a "ping" gets sent when there's nothing else to send; a healthy
# connection therefore never goes longer than that between *some* incoming
# byte. HEARTBEAT_TIMEOUT_S (several pings' worth, for margin) is how long
# without any incoming data before this side gives up and treats the
# connection as dead.
HEARTBEAT_INTERVAL_S = 5.0
HEARTBEAT_TIMEOUT_S = 15.0
