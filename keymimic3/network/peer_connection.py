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
"""

import json
import socket
import threading

from PySide6.QtCore import QObject, Signal

from .protocol import NET_PORT

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
        self._send_lock = threading.Lock()
        self._generation = 0  # bumped on every disconnect/new attempt

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
        was_connected = self._sock is not None
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
        if was_connected:
            # The reader thread's own cleanup won't emit `disconnected` for
            # this connection anymore - the generation bump above (needed to
            # stop a *stale* background thread from ever touching state
            # again) also suppresses its normally-legitimate final emission
            # for *this* still-current one, so this call is the only place
            # left that will ever notify listeners this specific connection
            # just ended.
            self.signals.disconnected.emit()

    def send(self, msg: dict):
        sock = self._sock
        if sock is None:
            return
        try:
            data = (json.dumps(msg) + "\n").encode("utf-8")
            with self._send_lock:
                sock.sendall(data)
        except OSError:
            pass  # the reader loop will notice the drop and emit `disconnected`

    # -- internal ---------------------------------------------------------

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
        self._sock = sock
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
                self.signals.disconnected.emit()
