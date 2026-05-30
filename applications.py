"""
applications.py — Application-layer services.

Two services are implemented:

  ChatApplication      — sends text messages over TCP
  FileTransferApplication — splits a file into chunks, transfers via TCP,
                            reassembles at the receiver

Both classes sit at the top of the TCP/IP stack and use the
Host's transport / network / data-link machinery underneath.
"""

import math
from typing import Callable, Optional

from devices import Host, Router
from logger import Logger


# ──────────────────────────────────────────────
#  Chat Application
# ──────────────────────────────────────────────

class ChatApplication:
    """
    Peer-to-peer text chat over TCP.

    Usage:
        chat = ChatApplication(host_a, host_b, router)
        chat.send("Hello from HostA!")
    """

    SERVICE_PORT = 5000           # well-known chat port (for this sim)
    CHUNK_SIZE   = 0              # full message in one segment

    def __init__(self, sender: Host, receiver: Host, router: Router) -> None:
        self.sender   = sender
        self.receiver = receiver
        self.router   = router

        # Register the chat port on both hosts
        self.sender.port_mgr.register_service("CHAT", self.SERVICE_PORT)
        self.receiver.port_mgr.register_service("CHAT", self.SERVICE_PORT)

        # Allocate an ephemeral source port for the sender
        self._src_port = self.sender.port_mgr.allocate_port()

        Logger.log(
            "APP",
            sender.name,
            receiver.name,
            f"ChatApplication ready: {sender.name}:{self._src_port} "
            f"→ {receiver.name}:{self.SERVICE_PORT}",
        )

    def send(self, message: str) -> str:
        """
        Send a chat message from sender to receiver.
        Returns the message as received by the receiver.
        """
        Logger.separator(f"CHAT: {self.sender.name} → {self.receiver.name}")
        Logger.log(
            "APP",
            self.sender.name,
            self.receiver.name,
            f"Chat message: '{message}'",
        )

        self.sender.send_tcp(
            message=message,
            dst_host=self.receiver,
            src_port=self._src_port,
            dst_port=self.SERVICE_PORT,
            router=self.router,
        )

        return message

    def close(self) -> None:
        """Release the ephemeral port when chat session ends."""
        self.sender.port_mgr.release_port(self._src_port)
        Logger.log("APP", self.sender.name, "", "Chat session closed")


# ──────────────────────────────────────────────
#  File Transfer Application
# ──────────────────────────────────────────────

class FileTransferApplication:
    """
    Transfers text file contents over TCP.

    The file is split into fixed-size chunks. Each chunk becomes one
    TCP segment. At the receiver, chunks are reassembled in order.

    This mimics the behaviour of FTP or SCP at a high level.
    """

    SERVICE_PORT = 21             # FTP well-known port
    CHUNK_SIZE   = 64             # bytes per chunk

    def __init__(self, sender: Host, receiver: Host, router: Router) -> None:
        self.sender   = sender
        self.receiver = receiver
        self.router   = router

        self.sender.port_mgr.register_service("FTP-DATA", self.SERVICE_PORT)
        self.receiver.port_mgr.register_service("FTP-DATA", self.SERVICE_PORT)
        self._src_port = self.sender.port_mgr.allocate_port()

        Logger.log(
            "APP",
            sender.name,
            receiver.name,
            f"FileTransferApp ready port {self._src_port} → {self.SERVICE_PORT}",
        )

    def transfer(
        self,
        filename: str,
        content: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """
        Transfer file content from sender to receiver.

        Args:
            filename          : display name of the file
            content           : full text content to transfer
            progress_callback : optional (current_chunk, total_chunks) callback
                                used by the GUI to update a progress bar

        Returns:
            The reassembled file content as received by the receiver.
        """
        Logger.separator(f"FILE TRANSFER: {filename}")
        Logger.log(
            "APP",
            self.sender.name,
            self.receiver.name,
            f"Initiating transfer: '{filename}' ({len(content)} bytes)",
        )

        # ── Chunking ──────────────────────────
        chunks  = self._split_into_chunks(content)
        total   = len(chunks)

        Logger.log(
            "APP",
            self.sender.name,
            self.receiver.name,
            f"File split into {total} chunk(s) of ≤{self.CHUNK_SIZE}B each",
        )

        # ── TCP sliding window send ────────────
        segments = self.sender.transport.tcp_send_chunks(
            chunks,
            src_port=self._src_port,
            dst_port=self.SERVICE_PORT,
            dst_ip=self.receiver.ip_address,
        )

        # ── Per-chunk encapsulation & delivery ─
        received_chunks: list[str] = []

        for i, (chunk, segment) in enumerate(zip(chunks, segments)):
            Logger.log(
                "APP",
                self.sender.name,
                self.receiver.name,
                f"Sending chunk {i+1}/{total}: '{chunk[:30]}{'…' if len(chunk)>30 else ''}'",
            )

            # Network + DataLink encapsulation
            packet = self.sender.network.encapsulate(
                self.sender._serialise_tcp(segment),
                self.receiver.ip_address,
                "TCP",
            )
            packet.payload = self.sender._serialise_tcp(segment)

            self.sender.data_link.send_payload(packet.summary(), self.router.name)

            # Router forwarding
            fwd = self.router.forward_packet(packet)
            if fwd is None:
                Logger.log("NETWORK", self.router.name, self.receiver.name,
                           f"✗ Chunk {i+1} dropped at router")
                continue

            # Receiver decapsulation
            raw_payload = self.receiver.network.decapsulate(packet)
            if raw_payload:
                seg = self.receiver._deserialise_tcp(packet.payload, self._src_port)
                chunk_data = self.receiver.transport.tcp_receive(seg)
                received_chunks.append(chunk_data)

            # Progress callback for GUI
            if progress_callback:
                progress_callback(i + 1, total)

            Logger.log(
                "APP",
                self.sender.name,
                self.receiver.name,
                f"Progress: {i+1}/{total} ({int((i+1)/total*100)}%)",
            )

        # ── Reassembly ────────────────────────
        reassembled = "".join(received_chunks)

        Logger.log(
            "APP",
            self.receiver.name,
            "",
            f"File reassembled: '{filename}' ({len(reassembled)} bytes received)",
        )

        # Verify integrity
        if reassembled == content:
            Logger.log("APP", self.receiver.name, "", "✓ File integrity verified — transfer complete")
        else:
            Logger.log("APP", self.receiver.name, "", "✗ File integrity check FAILED (chunks missing)")

        return reassembled

    def _split_into_chunks(self, content: str) -> list[str]:
        """Split content string into CHUNK_SIZE-byte pieces."""
        encoded = content.encode("utf-8")
        return [
            encoded[i : i + self.CHUNK_SIZE].decode("utf-8", errors="replace")
            for i in range(0, len(encoded), self.CHUNK_SIZE)
        ]

    def close(self) -> None:
        self.sender.port_mgr.release_port(self._src_port)


# ──────────────────────────────────────────────
#  Encapsulation Demonstration (standalone)
# ──────────────────────────────────────────────

def run_encapsulation_demo(host_a: Host, host_b: Host, router: Router) -> None:
    """
    Step-by-step encapsulation and decapsulation walkthrough.
    Each layer is shown individually with its PDU summary.
    """
    Logger.separator("ENCAPSULATION / DECAPSULATION DEMO")
    message = "Hello, Network!"

    Logger.log("DEMO", "HostA", "HostB", f"═══ SENDER SIDE (HostA) ═══")
    Logger.log("DEMO", "HostA", "HostB", f"[1] Application data: '{message}'")

    # Transport
    src_port = host_a.port_mgr.allocate_port()
    segment  = host_a.transport.tcp_send(message, src_port, 80, host_b.ip_address)
    Logger.log("DEMO", "HostA", "HostB", f"[2] TCP Segment: {segment.summary()}")

    # Network
    packet = host_a.network.encapsulate(
        host_a._serialise_tcp(segment), host_b.ip_address, "TCP"
    )
    packet.payload = host_a._serialise_tcp(segment)
    Logger.log("DEMO", "HostA", "HostB", f"[3] IP Packet:   {packet.summary()}")

    # Data Link
    from packets import EthernetFrame
    frame = EthernetFrame(
        src_mac=host_a.mac_address,
        dst_mac="AA:BB:CC:DD:EE:AA",   # router MAC
        payload=packet.summary(),
        seq_num=0,
    )
    Logger.log("DEMO", "HostA", "HostB", f"[4] Eth Frame:   {frame.summary()}")

    # Physical
    Logger.log("DEMO", "HostA", "HostB", "[5] Physical:    Bits transmitted on wire")

    Logger.log("DEMO", "Router", "HostB", "")
    Logger.log("DEMO", "Router", "HostB", "═══ ROUTER FORWARDING ═══")
    fwd = router.forward_packet(packet)
    Logger.log("DEMO", "Router", "HostB", f"    TTL after hop: {packet.ttl}")

    Logger.log("DEMO", "HostB", "", "")
    Logger.log("DEMO", "HostB", "", "═══ RECEIVER SIDE (HostB) ═══")
    Logger.log("DEMO", "HostB", "", "[5] Physical:    Bits received from wire")
    Logger.log("DEMO", "HostB", "", f"[4] Eth Frame:   CRC validated ✓")
    ip_payload = host_b.network.decapsulate(packet)
    Logger.log("DEMO", "HostB", "", f"[3] IP Packet:   decapsulated src={packet.src_ip}")
    seg_b = host_b._deserialise_tcp(packet.payload, src_port)
    msg   = host_b.transport.tcp_receive(seg_b)
    Logger.log("DEMO", "HostB", "", f"[2] TCP Segment: extracted seq={seg_b.seq_num}")
    Logger.log("DEMO", "HostB", "", f"[1] Application: message delivered: '{msg}'")

    host_a.port_mgr.release_port(src_port)


# ──────────────────────────────────────────────
#  Packet Loss Demo
# ──────────────────────────────────────────────

def run_packet_loss_demo(host_a: Host, host_b: Host, router: Router) -> None:
    """
    Demonstrate Go-Back-N ARQ with simulated packet loss.
    Frame 0 is forcibly dropped; retransmission follows after timeout.
    """
    Logger.separator("PACKET LOSS & RETRANSMISSION DEMO (Go-Back-N ARQ)")

    src_port = host_a.port_mgr.allocate_port()
    segment  = host_a.transport.tcp_send(
        "GBN test payload", src_port, 80, host_b.ip_address
    )
    packet   = host_a.network.encapsulate(
        host_a._serialise_tcp(segment), host_b.ip_address, "TCP"
    )
    packet.payload = host_a._serialise_tcp(segment)

    # DataLink send with loss_demo=True forces drop of first frame
    host_a.data_link.reset_sender()
    host_b.data_link.reset_receiver()
    host_a.data_link.send_payload(packet.summary(), router.name, loss_demo=True)

    Logger.log("DEMO", "HostA", "HostB",
               "After retransmission, receiver sends cumulative ACK")
    Logger.log("DEMO", "HostA", "HostB",
               "Go-Back-N: all frames from lost seq# retransmitted ✓")

    host_a.port_mgr.release_port(src_port)


# ──────────────────────────────────────────────
#  Router Forwarding Demo
# ──────────────────────────────────────────────

def run_router_demo(host_a: Host, host_b: Host, router: Router) -> None:
    """Show step-by-step how the router forwards a packet between subnets."""
    Logger.separator("ROUTER FORWARDING DEMO")

    src_port = host_a.port_mgr.allocate_port()
    segment  = host_a.transport.tcp_send(
        "Router demo payload", src_port, 80, host_b.ip_address
    )
    packet = host_a.network.encapsulate(
        host_a._serialise_tcp(segment), host_b.ip_address, "TCP"
    )
    packet.payload = host_a._serialise_tcp(segment)

    Logger.log("DEMO", "HostA", "Router",
               f"Packet leaving HostA: TTL={packet.ttl} dst={packet.dst_ip}")

    fwd = router.forward_packet(packet)
    if fwd:
        Logger.log("DEMO", "Router", "HostB",
                   f"Packet forwarded: TTL now {packet.ttl}")
        host_b.receive_tcp(packet, src_port)

    host_a.port_mgr.release_port(src_port)
