"""Send raw bytes (ESC/POS) to a network thermal printer over TCP.

Epson TM-* with built-in Ethernet/Wi-Fi listens on raw TCP port 9100.
"""
from __future__ import annotations

import socket
from contextlib import closing


class NetworkPrintError(Exception):
    pass


def send_raw(host: str, port: int, payload: bytes, timeout: float = 5.0) -> int:
    if not host:
        raise NetworkPrintError("Skriverens IP/hostname er ikke satt")
    try:
        with closing(socket.create_connection((host, int(port)), timeout=timeout)) as sock:
            sock.sendall(payload)
            return len(payload)
    except (socket.timeout, TimeoutError) as e:
        raise NetworkPrintError(f"Tidsavbrudd ({timeout}s) mot {host}:{port}") from e
    except OSError as e:
        raise NetworkPrintError(f"Kan ikke nå skriver {host}:{port} – {e}") from e
