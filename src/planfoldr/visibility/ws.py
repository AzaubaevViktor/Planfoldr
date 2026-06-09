"""Minimal RFC6455 WebSocket server (stdlib only, zero dependencies).

Implements just enough of the protocol for live one-way push to the Visibility pages: the opening
handshake, server→client text frames (unmasked), and reading/handling client close + ping frames.
This keeps "Live view ... общается по вебсокет" literally true without adding a dependency.
"""

from __future__ import annotations

import base64
import hashlib
import socket
import threading
from typing import List, Optional, Tuple

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def accept_key(client_key: str) -> str:
    digest = hashlib.sha1((client_key + _GUID).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_text_frame(text: str) -> bytes:
    data = text.encode("utf-8")
    header = bytearray([0x81])  # FIN=1, opcode=0x1 (text)
    n = len(data)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += n.to_bytes(2, "big")
    else:
        header.append(127)
        header += n.to_bytes(8, "big")
    return bytes(header) + data


def _recv_exactly(conn: socket.socket, n: int) -> Optional[bytes]:
    chunks = bytearray()
    while len(chunks) < n:
        part = conn.recv(n - len(chunks))
        if not part:
            return None
        chunks += part
    return bytes(chunks)


def read_frame(conn: socket.socket) -> Optional[Tuple[int, bytes]]:
    """Read one client→server frame. Returns (opcode, payload) or None on close/EOF."""
    head = _recv_exactly(conn, 2)
    if head is None:
        return None
    opcode = head[0] & 0x0F
    masked = bool(head[1] & 0x80)
    length = head[1] & 0x7F
    if length == 126:
        ext = _recv_exactly(conn, 2)
        if ext is None:
            return None
        length = int.from_bytes(ext, "big")
    elif length == 127:
        ext = _recv_exactly(conn, 8)
        if ext is None:
            return None
        length = int.from_bytes(ext, "big")
    mask = _recv_exactly(conn, 4) if masked else b"\x00\x00\x00\x00"
    if mask is None:
        return None
    payload = _recv_exactly(conn, length) if length else b""
    if payload is None:
        return None
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload


def do_handshake(conn: socket.socket) -> bool:
    request = b""
    while b"\r\n\r\n" not in request:
        part = conn.recv(1024)
        if not part:
            return False
        request += part
        if len(request) > 65536:
            return False
    key = None
    for line in request.decode("latin-1").split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
    if not key:
        return False
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key(key)}\r\n\r\n"
    )
    conn.sendall(response.encode("latin-1"))
    return True


class WebSocketServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8766) -> None:
        self.host = host
        self.port = port
        self._server: Optional[socket.socket] = None
        self._clients: List[socket.socket] = []
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> int:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen(16)
        self.port = self._server.getsockname()[1]
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return self.port

    def _accept_loop(self) -> None:
        while self._running:
            try:
                conn, _ = self._server.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            if not do_handshake(conn):
                conn.close()
                return
        except OSError:
            conn.close()
            return
        with self._lock:
            self._clients.append(conn)
        try:
            while self._running:
                frame = read_frame(conn)
                if frame is None or frame[0] == 0x8:  # EOF or close
                    break
                if frame[0] == 0x9:  # ping → pong
                    conn.sendall(bytes([0x8A, 0]))
        except OSError:
            pass
        finally:
            with self._lock:
                if conn in self._clients:
                    self._clients.remove(conn)
            conn.close()

    def broadcast(self, text: str) -> None:
        frame = encode_text_frame(text)
        with self._lock:
            clients = list(self._clients)
        for conn in clients:
            try:
                conn.sendall(frame)
            except OSError:
                with self._lock:
                    if conn in self._clients:
                        self._clients.remove(conn)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def stop(self) -> None:
        self._running = False
        with self._lock:
            clients = list(self._clients)
            self._clients.clear()
        for conn in clients:
            try:
                conn.close()
            except OSError:
                pass
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
