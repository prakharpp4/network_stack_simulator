"""
devices.py — Network devices: Host and Router.

Each device owns exactly the layers it should according to the TCP/IP model:

    Host   — all five layers (Application → Physical)
    Router — Network + Data Link + Physical only (no Transport/Application)

The topology used throughout the simulator is:

    HostA  <──>  Router  <──>  HostB

MAC and IP addresses are hardcoded for simplicity.
"""

from layers import DataLinkLayer, NetworkLayer, TransportLayer
from port_manager import PortManager
from packets import EthernetFrame, IPPacket, TCPSegment, UDPSegment
from logger import Logger
from typing import Optional


# ──────────────────────────────────────────────
#  Address constants  (fixed topology)
# ──────────────────────────────────────────────

HOST_A_IP  = "192.168.1.2"
HOST_B_IP  = "192.168.2.2"
ROUTER_IP_A = "192.168.1.1"   # Router's interface on subnet A
ROUTER_IP_B = "192.168.2.1"   # Router's interface on subnet B

HOST_A_MAC  = "AA:BB:CC:DD:EE:01"
HOST_B_MAC  = "AA:BB:CC:DD:EE:02"
ROUTER_MAC_A = "AA:BB:CC:DD:EE:AA"
ROUTER_MAC_B = "AA:BB:CC:DD:EE:BB"


# ──────────────────────────────────────────────
#  Base Device
# ──────────────────────────────────────────────

class Device:
    """
    Abstract base for all network devices.
    Holds the device name and shared description.
    """

    def __init__(self, name: str, description: str) -> None:
        self.name        = name
        self.description = description

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"


# ──────────────────────────────────────────────
#  Router
# ──────────────────────────────────────────────

class Router(Device):
    """
    Layer-3 forwarding device.

    The router has two network interfaces (one per subnet) and a
    static routing table. It does NOT have a Transport or Application
    layer — it only inspects and forwards IP packets.
    """

    def __init__(self) -> None:
        super().__init__("Router", "Layer-3 IPv4 router")

        # Network layer (uses interface A IP as its own address)
        self.network = NetworkLayer(self.name, ROUTER_IP_A)

        # Data Link layers — one per interface
        self.dl_a = DataLinkLayer(self.name, ROUTER_MAC_A, HOST_A_MAC)
        self.dl_b = DataLinkLayer(self.name, ROUTER_MAC_B, HOST_B_MAC)

        # Static routing table
        self.network.add_route(HOST_A_IP, HOST_A_IP)
        self.network.add_route(HOST_B_IP, HOST_B_IP)

        Logger.log("DEVICE", self.name, "", "Router initialised with static routes")

    def forward_packet(self, packet: IPPacket) -> Optional[IPPacket]:
        """
        Receive an IP packet, decrement TTL, look up the next hop,
        and return the (possibly modified) packet for the next device.

        Returns None if TTL expired or no route exists.
        """
        Logger.log(
            "NETWORK",
            self.name,
            packet.dst_ip,
            f"Packet arrived at router: src={packet.src_ip} dst={packet.dst_ip}",
        )

        next_hop = self.network.forward(packet)
        if next_hop is None:
            return None

        Logger.log(
            "NETWORK",
            self.name,
            packet.dst_ip,
            f"Forwarding to next hop: {next_hop}",
        )
        return packet


# ──────────────────────────────────────────────
#  Host
# ──────────────────────────────────────────────

class Host(Device):
    """
    End-host running all TCP/IP layers.

    Layers stacked bottom-up:
        Physical      (inside DataLinkLayer)
        DataLinkLayer
        NetworkLayer
        TransportLayer
        PortManager   (OS-level port allocation)

    Applications (Chat, FileTransfer) are injected and use
    the host's transport layer + port manager.
    """

    def __init__(
        self,
        name: str,
        ip_address: str,
        mac_address: str,
        router_mac: str,
        router_ip: str,
    ) -> None:
        super().__init__(name, f"End host at {ip_address}")

        self.ip_address = ip_address
        self.mac_address = mac_address

        # Layer instances
        self.data_link  = DataLinkLayer(name, mac_address, router_mac)
        self.network    = NetworkLayer(name, ip_address)
        self.transport  = TransportLayer(name)
        self.port_mgr   = PortManager(name)

        # Static default route: everything goes through the router
        self.network.add_route(HOST_A_IP, router_ip)
        self.network.add_route(HOST_B_IP, router_ip)

        Logger.log("DEVICE", self.name, "", f"Host initialised  IP={ip_address}  MAC={mac_address}")

    # ── Full stack: SEND ───────────────────────

    def send_tcp(
        self,
        message: str,
        dst_host: "Host",
        src_port: int,
        dst_port: int,
        router: Router,
        loss_demo: bool = False,
    ) -> None:
        """
        Full encapsulation chain: Application → Transport → Network → DataLink → Physical.
        Then hand the packet to the router, then to dst_host for decapsulation.
        """
        Logger.log(
            "APP",
            self.name,
            dst_host.name,
            f"Application message ready: '{message}'",
        )

        # ── Transport Layer ──
        segment = self.transport.tcp_send(
            message, src_port, dst_port, dst_host.ip_address
        )

        # ── Network Layer ──
        packet = self.network.encapsulate(segment.summary(), dst_host.ip_address, "TCP")
        # Store the actual segment inside the packet payload for reconstruction
        packet.payload = self._serialise_tcp(segment)

        # ── Data Link Layer ──
        self.data_link.send_payload(packet.summary(), router.name, loss_demo=loss_demo)

        # ── Router forwarding ──
        forwarded = router.forward_packet(packet)
        if forwarded is None:
            Logger.log("NETWORK", router.name, dst_host.name, "✗ Packet dropped at router")
            return

        # ── Delivery to destination ──
        dst_host.receive_tcp(packet, src_port)

    def receive_tcp(self, packet: IPPacket, src_port: int) -> str:
        """
        Full decapsulation: Physical → DataLink → Network → Transport → Application.
        Returns the recovered application message.
        """
        # ── Network Layer ──
        raw = self.network.decapsulate(packet)
        if raw is None:
            return ""

        # ── Transport Layer ──
        segment = self._deserialise_tcp(packet.payload, src_port)
        message = self.transport.tcp_receive(segment)

        # ── Application Layer ──
        Logger.log(
            "APP",
            self.name,
            "",
            f"Message delivered to application: '{message}'",
        )
        return message

    def send_udp(
        self,
        message: str,
        dst_host: "Host",
        src_port: int,
        dst_port: int,
        router: Router,
    ) -> None:
        """UDP send — no reliability, no retransmission."""
        Logger.log("APP", self.name, dst_host.name, f"UDP message: '{message}'")

        segment  = self.transport.udp_send(message, src_port, dst_port, dst_host.ip_address)
        packet   = self.network.encapsulate(segment.summary(), dst_host.ip_address, "UDP")
        packet.payload = self._serialise_udp(segment)
        self.data_link.send_payload(packet.summary(), router.name)

        forwarded = router.forward_packet(packet)
        if forwarded:
            dst_host.receive_udp(packet, src_port)

    def receive_udp(self, packet: IPPacket, src_port: int) -> str:
        raw = self.network.decapsulate(packet)
        if raw is None:
            return ""
        segment = self._deserialise_udp(packet.payload, src_port)
        return self.transport.udp_receive(segment)

    # ── Serialisation helpers ──────────────────
    # We store the segment data as a delimited string inside IPPacket.payload
    # because this is an educational simulator (no real binary serialisation).

    def _serialise_tcp(self, seg: TCPSegment) -> str:
        return f"TCP|{seg.src_port}|{seg.dst_port}|{seg.seq_num}|{seg.ack_num}|{seg.payload}"

    def _deserialise_tcp(self, raw: str, src_port: int) -> TCPSegment:
        try:
            _, sp, dp, seq, ack, *payload_parts = raw.split("|")
            return TCPSegment(
                src_port=int(sp),
                dst_port=int(dp),
                seq_num=int(seq),
                ack_num=int(ack),
                payload="|".join(payload_parts),
            )
        except Exception:
            # Fallback: treat whole string as payload
            return TCPSegment(
                src_port=src_port,
                dst_port=80,
                seq_num=0,
                ack_num=0,
                payload=raw,
            )

    def _serialise_udp(self, seg: UDPSegment) -> str:
        return f"UDP|{seg.src_port}|{seg.dst_port}|{seg.payload}"

    def _deserialise_udp(self, raw: str, src_port: int) -> UDPSegment:
        try:
            _, sp, dp, *payload_parts = raw.split("|")
            return UDPSegment(
                src_port=int(sp),
                dst_port=int(dp),
                payload="|".join(payload_parts),
            )
        except Exception:
            return UDPSegment(src_port=src_port, dst_port=80, payload=raw)

    def reset(self) -> None:
        """Reset layer state between demos."""
        self.transport.reset()
        self.data_link.reset_sender()
        self.data_link.reset_receiver()


# ──────────────────────────────────────────────
#  Factory  — build the fixed topology
# ──────────────────────────────────────────────

def build_topology() -> tuple[Host, Router, Host]:
    """
    Construct and return (host_a, router, host_b) with correct
    addresses and cross-references wired up.
    """
    router = Router()

    host_a = Host(
        name="HostA",
        ip_address=HOST_A_IP,
        mac_address=HOST_A_MAC,
        router_mac=ROUTER_MAC_A,
        router_ip=ROUTER_IP_A,
    )

    host_b = Host(
        name="HostB",
        ip_address=HOST_B_IP,
        mac_address=HOST_B_MAC,
        router_mac=ROUTER_MAC_B,
        router_ip=ROUTER_IP_B,
    )

    return host_a, router, host_b
