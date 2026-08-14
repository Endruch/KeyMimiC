"""
TCP connection to the other KeyMiglic instance (see SPEC.md §2.2). Plain
Python `socket` - no Windows API involved, so unlike almost everything else
in this app this layer can be exercised for real on any OS, including
during development on macOS.

"Start Server" / "Connect" (see ThreadPanel) only decide how the socket
gets established - one side listens, the other dials in. Once connected,
the two roles are indistinguishable: both just read/write the same socket,
see protocol.py for what gets sent.

Only one connection at a time is supported. Starting a new server/connect
attempt (or disconnecting) invalidates any previous attempt via a
generation counter, so a slow/stale background thread from a previous
attempt can never clobber a newer connection.

send() is always non-blocking, from any thread, including the GUI thread -
it only ever enqueues onto _send_queue; a single dedicated sender thread
(running for this object's whole lifetime) does the actual blocking
sock.sendall(). This used to not be true, and RemoteControlManager calling
peer.send() straight from a GUI-thread QTimer (arming/disarming, script
status) would freeze the entire UI for as long as a degraded/dead network
took to time out a blocking send - which, without TCP keepalive, can be a
very long time. The same sender thread also sends an occasional "ping" so
a silently-dead peer (wifi dropped, machine slept) gets noticed by the
*reader* side within HEARTBEAT_TIMEOUT_S instead of the connection just
sitting "connected" forever - see protocol.py.
"""

import json
import queue
import socket
import threading

from PySide6.QtCore import QObject, Signal

from .protocol import NET_PORT, HEARTBEAT_INTERVAL_S, HEARTBEAT_TIMEOUT_S

CONNECT_TIMEOUT_S = 5.0


class PeerConnectionSignals(QObject):
    connected = Signal()
    disconnected = Signal()
    message = Signal(dict)
    error = Signal(str)  # user-facing message, e.g. "Could not connect: ..."


class PeerConnection:
    """One TCP connection to the peer app, established as a server or a client."""

    def __init__(self):
        self.signals = PeerConnectionSignals()
        # Thin pass-through so callers can do peer.connected.connect(...) directly.
        self.connected = self.signals.connected
        self.disconnected = self.signals.disconnected
        self.message = self.signals.message
        self.error = self.signals.error

        self._sock = None
        self._listen_sock = None
        self._generation = 0  # bumped on every disconnect/new attempt
        self.peer_ip = None  # remote address of the current connection, if any

        self._send_queue = queue.Queue()
        threading.Thread(target=self._run_sender, daemon=True).start()

    def is_connected(self) -> bool:
        return self._sock is not None

    def local_ip(self) -> str:
        """Best-effort local LAN IP, for display next to Start Server."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"
        finally:
            s.close()

    def start_server(self):
        self.disconnect()
        gen = self._bump_generation()
        threading.Thread(target=self._run_server, args=(gen,), daemon=True).start()

    def connect_to(self, ip: str):
        self.disconnect()
        gen = self._bump_generation()
        threading.Thread(target=self._run_client, args=(ip, gen), daemon=True).start()

    def disconnect(self):
        # Also covers "still just listening, no peer yet" (Stop Server before
        # anyone connected) - the UI needs to hear about that reverting to
        # idle just as much as an actual established connection dropping.
        was_active = self._sock is not None or self._listen_sock is not None
        self._bump_generation()
        if self._listen_sock is not None:
            try:
                self._listen_sock.close()
            except OSError:
                pass
            self._listen_sock = None
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
            self.peer_ip = None
        if was_active:
            # The reader/listener thread's own cleanup won't emit
            # `disconnected` for this attempt anymore - the generation bump
            # above (needed to stop a *stale* background thread from ever
            # touching state again) also suppresses its normally-legitimate
            # final emission for *this* still-current one, so this call is
            # the only place left that will ever notify listeners this
            # specific connection/listen attempt just ended.
            self.signals.disconnected.emit()

    def send(self, msg: dict):
        """Non-blocking from any thread - see module docstring."""
        self._send_queue.put_nowait(msg)

    # -- internal ---------------------------------------------------------

    def _run_sender(self):
        """
        The only thread that ever writes to the socket. Runs for this
        object's whole lifetime (not tied to any one connection's
        generation) - when nothing is connected it just drops queued
        messages, same as the old send() did.
        """
        while True:
            try:
                msg = self._send_queue.get(timeout=HEARTBEAT_INTERVAL_S)
            except queue.Empty:
                msg = {"type": "ping"}
            sock = self._sock
            if sock is None:
                continue
            try:
                data = (json.dumps(msg) + "\n").encode("utf-8")
                sock.sendall(data)
            except OSError:
                pass  # the reader loop is the single source of truth for "disconnected"

    def _bump_generation(self) -> int:
        self._generation += 1
        return self._generation

    def _run_server(self, gen):
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_sock.bind(("0.0.0.0", NET_PORT))
            listen_sock.listen(1)
            if gen != self._generation:
                listen_sock.close()
                return
            self._listen_sock = listen_sock
            conn, _addr = listen_sock.accept()
        except OSError as exc:
            if gen == self._generation:
                self.signals.error.emit(f"Could not start server: {exc}")
            return
        finally:
            if self._listen_sock is listen_sock:
                self._listen_sock = None
        if gen != self._generation:
            conn.close()
            return
        self._on_socket_ready(conn, gen)

    def _run_client(self, ip, gen):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(CONNECT_TIMEOUT_S)
            sock.connect((ip, NET_PORT))
            sock.settimeout(None)
        except OSError as exc:
            if gen == self._generation:
                self.signals.error.emit(f"Could not connect: {exc}")
            sock.close()
            return
        if gen != self._generation:
            sock.close()
            return
        self._on_socket_ready(sock, gen)

    def _on_socket_ready(self, sock, gen):
        # Bounds how long recv() can block with nothing arriving - without
        # this, a peer that silently vanishes (wifi drop, sleep, cable
        # pulled - no clean TCP close) would leave this side sitting
        # "connected" forever. A healthy peer's sender thread pings often
        # enough (see protocol.HEARTBEAT_INTERVAL_S) that this should never
        # actually fire for a live connection - socket.timeout is a
        # subclass of OSError, so it's caught by the same handler below as
        # any other dead-connection error.
        sock.settimeout(HEARTBEAT_TIMEOUT_S)
        self._sock = sock
        try:
            self.peer_ip = sock.getpeername()[0]
        except OSError:
            self.peer_ip = None
        self.signals.connected.emit()
        buf = b""
        try:
            while gen == self._generation:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except ValueError:
                        continue
                    self.signals.message.emit(msg)
        except OSError:
            pass
        finally:
            try:
                sock.close()
            except OSError:
                pass
            if gen == self._generation:
                self._sock = None
                self.peer_ip = None
                self.signals.disconnected.emit()
