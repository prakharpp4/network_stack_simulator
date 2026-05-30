"""
packets.py — Protocol Data Units (PDUs) for every layer.

Each class models a real network PDU:
  - EthernetFrame  (Data Link Layer)
  - IPPacket       (Network Layer)
  - TCPSegment     (Transport Layer)
  - UDPSegment     (Transport Layer)

Dataclasses give us free __repr__ for the Packet Inspector panel.
CRC is a simple XOR checksum — educational, not cryptographic.
"""

from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────
#  CRC Helper  (simple XOR-based checksum)
# ──────────────────────────────────────────────

def compute_crc(data: str) -> int:
    """
    Compute a simple 8-bit XOR checksum over the UTF-8 bytes of data.
    Real Ethernet uses CRC-32; this is simplified for clarity.
    """
    result = 0
    for byte in data.encode("utf-8"):
        result ^= byte
    return result


def validate_crc(data: str, expected_crc: int) -> bool:
    """Return True if recomputed CRC matches the stored CRC."""
    return compute_crc(data) == expected_crc


# ──────────────────────────────────────────────
#  Data Link Layer  —  Ethernet Frame
# ──────────────────────────────────────────────

@dataclass
class EthernetFrame:
    """
    Simplified Ethernet II frame.

    Fields (matching the real standard):
        src_mac  : sender's MAC address  e.g. "AA:BB:CC:DD:EE:01"
        dst_mac  : receiver's MAC address
        payload  : raw bytes (carried IP packet, represented as string)
        crc      : checksum computed over src_mac+dst_mac+payload
        seq_num  : sequence number used by Go-Back-N ARQ
        is_ack   : True when this frame is an acknowledgement
        ack_num  : which sequence number is being acknowledged
    """
    src_mac: str
    dst_mac: str
    payload: str
    crc: int = field(default=0, init=False)
    seq_num: int = 0
    is_ack: bool = False
    ack_num: int = 0

    def __post_init__(self) -> None:
        # CRC is computed over everything except the CRC field itself
        self.crc = compute_crc(self.src_mac + self.dst_mac + self.payload)

    def is_valid(self) -> bool:
        """Check integrity by recomputing CRC."""
        return validate_crc(self.src_mac + self.dst_mac + self.payload, self.crc)

    def summary(self) -> str:
        kind = "ACK" if self.is_ack else "DATA"
        return (
            f"EthernetFrame[{kind}] seq={self.seq_num} "
            f"{self.src_mac} -> {self.dst_mac} "
            f"CRC=0x{self.crc:02X} payload_len={len(self.payload)}"
        )


# ──────────────────────────────────────────────
#  Network Layer  —  IPv4 Packet
# ──────────────────────────────────────────────

@dataclass
class IPPacket:
    """
    Simplified IPv4 packet.

    Fields:
        src_ip   : source IP address      e.g. "192.168.1.1"
        dst_ip   : destination IP address
        ttl      : Time-To-Live (router decrements by 1 on each hop)
        protocol : "TCP" or "UDP"
        payload  : serialised transport-layer segment (string)
    """
    src_ip: str
    dst_ip: str
    ttl: int
    protocol: str
    payload: str

    def summary(self) -> str:
        return (
            f"IPPacket  {self.src_ip} -> {self.dst_ip} "
            f"TTL={self.ttl} proto={self.protocol} "
            f"payload_len={len(self.payload)}"
        )


# ──────────────────────────────────────────────
#  Transport Layer  —  TCP Segment
# ──────────────────────────────────────────────

@dataclass
class TCPSegment:
    """
    Simplified TCP segment.

    Fields:
        src_port : sender's port number
        dst_port : receiver's port number
        seq_num  : sequence number (byte-stream position)
        ack_num  : acknowledgement number
        flags    : dict with SYN/ACK/FIN flags
        payload  : application data (string)
    """
    src_port: int
    dst_port: int
    seq_num: int
    ack_num: int
    payload: str
    flags: dict[str, bool] = field(default_factory=lambda: {
        "SYN": False, "ACK": False, "FIN": False
    })

    def summary(self) -> str:
        active_flags = [k for k, v in self.flags.items() if v]
        flag_str = "|".join(active_flags) if active_flags else "NONE"
        return (
            f"TCPSegment  {self.src_port} -> {self.dst_port} "
            f"seq={self.seq_num} ack={self.ack_num} "
            f"flags=[{flag_str}] payload_len={len(self.payload)}"
        )


# ──────────────────────────────────────────────
#  Transport Layer  —  UDP Segment
# ──────────────────────────────────────────────

@dataclass
class UDPSegment:
    """
    Simplified UDP segment — no reliability, minimal header.

    Fields:
        src_port : sender's port
        dst_port : receiver's port
        payload  : application data
        length   : total segment length (header 8B + payload)
    """
    src_port: int
    dst_port: int
    payload: str
    length: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        # Simulate real UDP: 8-byte fixed header + payload bytes
        self.length = 8 + len(self.payload.encode("utf-8"))

    def summary(self) -> str:
        return (
            f"UDPSegment  {self.src_port} -> {self.dst_port} "
            f"length={self.length} payload_len={len(self.payload)}"
        )
