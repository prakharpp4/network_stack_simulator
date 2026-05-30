"""
layers.py — The five TCP/IP stack layers.

Each class represents one layer and owns exactly its layer's
responsibilities. Layers are composed inside Host / Router objects
(see devices.py) — they do NOT hold references to each other directly.

Layers implemented:
  PhysicalLayer   — bit transmission simulation, delay
  DataLinkLayer   — Ethernet framing, CRC, Go-Back-N ARQ
  NetworkLayer    — IPv4 routing, TTL, forwarding table
  TransportLayer  — TCP (sliding window) + UDP (best-effort)
"""

import time
import random
from typing import Optional, Callable

from packets import (
    EthernetFrame, IPPacket, TCPSegment, UDPSegment,
    compute_crc, validate_crc,
)
from logger import Logger


# ──────────────────────────────────────────────
#  1.  PHYSICAL LAYER
# ──────────────────────────────────────────────

class PhysicalLayer:
    """
    Simulates bit-level transmission over a wire.

    In reality this layer converts frames to electrical/optical signals.
    Here we model the transmission delay proportional to frame size
    and optionally simulate random bit errors (frame loss).
    """

    BITS_PER_SECOND = 1_000_000          # 1 Mbps link speed
    LOSS_PROBABILITY = 0.0               # set > 0 to enable loss demos

    def __init__(self, owner: str) -> None:
        self.owner = owner               # e.g. "HostA" — for logging

    def transmit(self, frame: EthernetFrame, destination: str) -> bool:
        """
        Simulate putting bits on the wire.

        Returns False if the frame is 'lost' (simulated packet loss).
        """
        # Transmission delay: size_in_bits / link_speed
        payload_bits = len(frame.payload.encode()) * 8
        delay_ms = (payload_bits / self.BITS_PER_SECOND) * 1000

        Logger.log(
            "PHYSICAL",
            self.owner,
            destination,
            f"Transmitting frame seq={frame.seq_num} "
            f"({payload_bits} bits, delay≈{delay_ms:.2f}ms)",
        )
        time.sleep(delay_ms / 1000.0)   # non-blocking in GUI thread — kept tiny

        # Simulate packet loss
        if random.random() < self.LOSS_PROBABILITY:
            Logger.log(
                "PHYSICAL",
                self.owner,
                destination,
                f"⚠  Frame seq={frame.seq_num} LOST on the wire (simulated)",
            )
            return False                 # caller treats this as a lost frame

        Logger.log(
            "PHYSICAL",
            self.owner,
            destination,
            f"✓  Frame seq={frame.seq_num} delivered to physical medium",
        )
        return True

    def receive(self, frame: EthernetFrame) -> None:
        """Log receipt of bits from the wire."""
        Logger.log(
            "PHYSICAL",
            self.owner,
            "",
            f"Received frame seq={frame.seq_num} from physical medium",
        )


# ──────────────────────────────────────────────
#  2.  DATA LINK LAYER
# ──────────────────────────────────────────────

class DataLinkLayer:
    """
    Handles framing, CRC checking, and Go-Back-N ARQ.

    Go-Back-N ARQ overview:
      - Sender maintains a window of up to WINDOW_SIZE unacknowledged frames.
      - If a frame times out or is lost, ALL frames from that sequence number
        onward are retransmitted.
      - Receiver only accepts frames in order; out-of-order frames are dropped.
    """

    WINDOW_SIZE  = 4     # max unacknowledged frames in flight
    TIMEOUT_SECS = 0.5   # retransmission timeout

    def __init__(self, owner: str, src_mac: str, dst_mac: str) -> None:
        self.owner   = owner
        self.src_mac = src_mac
        self.dst_mac = dst_mac
        self.physical = PhysicalLayer(owner)

        # Sender state
        self._send_base   = 0   # oldest unACK'd sequence number
        self._next_seq    = 0   # next sequence number to use
        self._send_buffer: dict[int, EthernetFrame] = {}

        # Receiver state
        self._expected_seq = 0  # next sequence number expected

    # ── Sender side ────────────────────────────

    def send_payload(
        self,
        payload: str,
        destination: str,
        loss_demo: bool = False,
    ) -> None:
        """
        Wrap payload in an Ethernet frame and send it via Go-Back-N.

        When loss_demo=True, the first frame is artificially dropped to
        demonstrate timeout-and-retransmit.
        """
        frame = EthernetFrame(
            src_mac=self.src_mac,
            dst_mac=self.dst_mac,
            payload=payload,
            seq_num=self._next_seq,
        )
        self._send_buffer[self._next_seq] = frame

        Logger.log(
            "DATA_LINK",
            self.owner,
            destination,
            f"Framed payload → seq={frame.seq_num} CRC=0x{frame.crc:02X}",
        )

        # Simulate loss on the first send during the demo
        if loss_demo and self._next_seq == 0:
            Logger.log(
                "DATA_LINK",
                self.owner,
                destination,
                f"[DEMO] Forcing loss on frame seq={frame.seq_num}",
            )
            self._next_seq += 1
            # Simulate timeout
            Logger.log(
                "DATA_LINK",
                self.owner,
                destination,
                f"⏱  Timeout waiting for ACK seq={frame.seq_num} — retransmitting",
            )
            # Retransmit
            Logger.log(
                "DATA_LINK",
                self.owner,
                destination,
                f"↩  Retransmitting frame seq={frame.seq_num}",
            )
            self.physical.transmit(frame, destination)
        else:
            delivered = self.physical.transmit(frame, destination)
            if not delivered:
                Logger.log(
                    "DATA_LINK",
                    self.owner,
                    destination,
                    f"⏱  No ACK received — retransmitting seq={frame.seq_num}",
                )
                self.physical.transmit(frame, destination)

        self._next_seq += 1
        self._send_base = self._next_seq   # advance window (single-frame for clarity)

    # ── Receiver side ──────────────────────────

    def receive_frame(self, frame: EthernetFrame) -> Optional[str]:
        """
        Validate CRC and check sequence order.

        Returns the payload string if the frame is valid and in-order,
        otherwise returns None (frame is discarded — GBN behaviour).
        """
        self.physical.receive(frame)

        # CRC check
        if not frame.is_valid():
            Logger.log(
                "DATA_LINK",
                self.owner,
                "",
                f"✗  CRC MISMATCH on frame seq={frame.seq_num} — frame discarded",
            )
            return None

        # Go-Back-N: only accept the expected sequence number
        if frame.seq_num != self._expected_seq:
            Logger.log(
                "DATA_LINK",
                self.owner,
                "",
                f"✗  Out-of-order frame seq={frame.seq_num} "
                f"(expected {self._expected_seq}) — discarded",
            )
            return None

        Logger.log(
            "DATA_LINK",
            self.owner,
            "",
            f"✓  Frame seq={frame.seq_num} accepted CRC OK — decapsulating",
        )
        self._expected_seq += 1
        return frame.payload

    def reset_receiver(self) -> None:
        """Reset receiver sequence counter between demos."""
        self._expected_seq = 0

    def reset_sender(self) -> None:
        """Reset sender state between demos."""
        self._send_base  = 0
        self._next_seq   = 0
        self._send_buffer.clear()


# ──────────────────────────────────────────────
#  3.  NETWORK LAYER
# ──────────────────────────────────────────────

class NetworkLayer:
    """
    IPv4 packet handling: encapsulation, routing table lookup, TTL.

    Routing table format:
        { "destination_ip": "next_hop_or_interface" }

    The router holds its own NetworkLayer instance and uses it to
    forward packets between subnets.
    """

    DEFAULT_TTL = 64   # matches Linux default

    def __init__(self, owner: str, ip_address: str) -> None:
        self.owner      = owner
        self.ip_address = ip_address
        self._routing_table: dict[str, str] = {}

    def add_route(self, destination: str, next_hop: str) -> None:
        """Add a static route to the routing table."""
        self._routing_table[destination] = next_hop
        Logger.log(
            "NETWORK",
            self.owner,
            "",
            f"Route added: {destination} via {next_hop}",
        )

    def encapsulate(
        self,
        payload: str,
        dst_ip: str,
        protocol: str,
    ) -> IPPacket:
        """Wrap transport payload in an IP packet."""
        packet = IPPacket(
            src_ip=self.ip_address,
            dst_ip=dst_ip,
            ttl=self.DEFAULT_TTL,
            protocol=protocol,
            payload=payload,
        )
        Logger.log(
            "NETWORK",
            self.owner,
            dst_ip,
            f"IP packet created TTL={packet.ttl} proto={protocol}",
        )
        return packet

    def decapsulate(self, packet: IPPacket) -> Optional[str]:
        """
        Extract payload from IP packet.
        Drops the packet if TTL has reached 0.
        """
        if packet.ttl <= 0:
            Logger.log(
                "NETWORK",
                self.owner,
                "",
                f"✗  Packet TTL=0 — dropped (destination {packet.dst_ip})",
            )
            return None

        Logger.log(
            "NETWORK",
            self.owner,
            "",
            f"✓  IP packet decapsulated src={packet.src_ip} TTL={packet.ttl}",
        )
        return packet.payload

    def forward(self, packet: IPPacket) -> Optional[str]:
        """
        Router-side: decrement TTL, look up next hop, return it.
        Returns the next-hop IP string, or None if no route / TTL=0.
        """
        # Decrement TTL before forwarding
        packet.ttl -= 1
        Logger.log(
            "NETWORK",
            self.owner,
            packet.dst_ip,
            f"Forwarding packet TTL decremented to {packet.ttl}",
        )

        if packet.ttl <= 0:
            Logger.log(
                "NETWORK",
                self.owner,
                "",
                f"✗  TTL expired — packet to {packet.dst_ip} dropped",
            )
            return None

        next_hop = self._routing_table.get(packet.dst_ip)
        if next_hop is None:
            Logger.log(
                "NETWORK",
                self.owner,
                packet.dst_ip,
                f"✗  No route to {packet.dst_ip} — packet dropped",
            )
            return None

        Logger.log(
            "NETWORK",
            self.owner,
            packet.dst_ip,
            f"Route found: {packet.dst_ip} → next_hop {next_hop}",
        )
        return next_hop


# ──────────────────────────────────────────────
#  4.  TRANSPORT LAYER
# ──────────────────────────────────────────────

class TransportLayer:
    """
    TCP and UDP transport implementations.

    TCP  — reliable, ordered, connection-oriented (sliding window)
    UDP  — unreliable, connectionless, minimal overhead
    """

    WINDOW_SIZE = 4    # TCP sliding window size (segments)

    def __init__(self, owner: str) -> None:
        self.owner = owner
        self._tcp_seq: int = 0   # running TCP sequence number

    # ── TCP ────────────────────────────────────

    def tcp_send(
        self,
        payload: str,
        src_port: int,
        dst_port: int,
        dst_ip: str,
    ) -> TCPSegment:
        """
        Build a TCP segment. Sequence number advances per call.
        Simulates single-segment window for clarity.
        """
        segment = TCPSegment(
            src_port=src_port,
            dst_port=dst_port,
            seq_num=self._tcp_seq,
            ack_num=0,
            payload=payload,
        )
        self._tcp_seq += len(payload)

        Logger.log(
            "TRANSPORT",
            f"{self.owner}:{src_port}",
            f"{dst_ip}:{dst_port}",
            f"TCP segment created seq={segment.seq_num} len={len(payload)}",
        )
        return segment

    def tcp_receive(self, segment: TCPSegment) -> str:
        """Validate and extract payload from a TCP segment."""
        Logger.log(
            "TRANSPORT",
            self.owner,
            "",
            f"TCP segment received src_port={segment.src_port} "
            f"seq={segment.seq_num} len={len(segment.payload)}",
        )
        return segment.payload

    def tcp_send_chunks(
        self,
        chunks: list[str],
        src_port: int,
        dst_port: int,
        dst_ip: str,
    ) -> list[TCPSegment]:
        """
        Send multiple chunks with sliding-window logging.
        Window of size WINDOW_SIZE segments are 'in flight' simultaneously.
        """
        segments: list[TCPSegment] = []
        total = len(chunks)

        Logger.log(
            "TRANSPORT",
            self.owner,
            dst_ip,
            f"TCP sliding window: sending {total} segments, "
            f"window={self.WINDOW_SIZE}",
        )

        for i, chunk in enumerate(chunks):
            segment = self.tcp_send(chunk, src_port, dst_port, dst_ip)
            segments.append(segment)

            # Log window state
            window_start = max(0, i - self.WINDOW_SIZE + 1)
            Logger.log(
                "TRANSPORT",
                self.owner,
                dst_ip,
                f"  Window [{window_start}–{i}] "
                f"segment {i+1}/{total} queued",
            )
            # Simulate ACK every WINDOW_SIZE segments
            if (i + 1) % self.WINDOW_SIZE == 0 or i == total - 1:
                Logger.log(
                    "TRANSPORT",
                    self.owner,
                    dst_ip,
                    f"  ACK received for segments up to seq={segment.seq_num}",
                )

        return segments

    # ── UDP ────────────────────────────────────

    def udp_send(
        self,
        payload: str,
        src_port: int,
        dst_port: int,
        dst_ip: str,
    ) -> UDPSegment:
        """Build a UDP segment — no reliability, no seq numbers."""
        segment = UDPSegment(
            src_port=src_port,
            dst_port=dst_port,
            payload=payload,
        )
        Logger.log(
            "TRANSPORT",
            f"{self.owner}:{src_port}",
            f"{dst_ip}:{dst_port}",
            f"UDP segment created length={segment.length}",
        )
        return segment

    def udp_receive(self, segment: UDPSegment) -> str:
        """Extract payload from UDP segment (no validation)."""
        Logger.log(
            "TRANSPORT",
            self.owner,
            "",
            f"UDP segment received src_port={segment.src_port} "
            f"len={len(segment.payload)}",
        )
        return segment.payload

    def reset(self) -> None:
        """Reset TCP sequence counter between demos."""
        self._tcp_seq = 0
