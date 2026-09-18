#!/usr/bin/env python3
from __future__ import annotations

import socket
import sys


def send_wol(mac: str) -> None:
    cleaned = mac.replace("-", "").replace(":", "")
    if len(cleaned) != 12:
        raise ValueError("MACアドレスの形式が不正です")
    data = b"\xff" * 6 + bytes.fromhex(cleaned) * 16
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(data, ("255.255.255.255", 9))


def main() -> int:
    if len(sys.argv) != 2:
        print("使い方: python wol.py <MACアドレス>")
        return 1
    try:
        send_wol(sys.argv[1])
    except ValueError as exc:
        print(str(exc))
        return 1
    print("Magic Packet を送信しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
