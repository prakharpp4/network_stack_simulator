"""
port_manager.py — Port allocation and service registry.

Models the OS port management subsystem:
  - Well-known ports  (0–1023)    pre-registered to services
  - Registered ports (1024–49151) not used here
  - Ephemeral ports  (49152–65535) dynamically allocated to clients

Usage:
    pm = PortManager()
    port = pm.allocate_port()          # get a free ephemeral port
    pm.release_port(port)              # return it to the pool
    pm.register_service("HTTP", 80)    # name a well-known port
"""

from logger import Logger


# Well-known port → service name
WELL_KNOWN_PORTS: dict[int, str] = {
    21:  "FTP",
    22:  "SSH",
    80:  "HTTP",
    443: "HTTPS",
}

EPHEMERAL_START = 49152
EPHEMERAL_END   = 65535


class PortManager:
    """
    Manages port allocation for a single host.

    Attributes:
        host_name       : human-readable owner label (for logging)
        _services       : port -> service-name registry
        _allocated      : set of currently in-use port numbers
        _next_ephemeral : pointer into the ephemeral range
    """

    def __init__(self, host_name: str) -> None:
        self.host_name = host_name
        self._services: dict[int, str] = dict(WELL_KNOWN_PORTS)
        self._allocated: set[int] = set(WELL_KNOWN_PORTS.keys())
        self._next_ephemeral: int = EPHEMERAL_START

    # ── Public API ──────────────────────────────

    def allocate_port(self) -> int:
        """
        Allocate the next free ephemeral port.
        Raises RuntimeError if the ephemeral range is exhausted.
        """
        while self._next_ephemeral <= EPHEMERAL_END:
            candidate = self._next_ephemeral
            self._next_ephemeral += 1
            if candidate not in self._allocated:
                self._allocated.add(candidate)
                Logger.log(
                    "PORT_MGR",
                    self.host_name,
                    "",
                    f"Allocated ephemeral port {candidate}",
                )
                return candidate
        raise RuntimeError(f"{self.host_name}: ephemeral port range exhausted")

    def release_port(self, port: int) -> None:
        """
        Release a previously allocated port back to the pool.
        Well-known ports are never removed from the registry.
        """
        if port in self._allocated:
            self._allocated.discard(port)
            Logger.log(
                "PORT_MGR",
                self.host_name,
                "",
                f"Released port {port}",
            )

    def register_service(self, service_name: str, port: int) -> None:
        """
        Register a named service on a specific port.
        Prevents the port from being allocated as ephemeral.
        """
        self._services[port] = service_name
        self._allocated.add(port)
        Logger.log(
            "PORT_MGR",
            self.host_name,
            "",
            f"Registered service '{service_name}' on port {port}",
        )

    def get_service(self, port: int) -> str:
        """Return service name for a port, or 'UNKNOWN'."""
        return self._services.get(port, "UNKNOWN")

    def status(self) -> str:
        """Human-readable snapshot of allocated ports."""
        lines = [f"  {self.host_name} Port Status:"]
        for port in sorted(self._allocated):
            svc = self._services.get(port, "ephemeral")
            lines.append(f"    port {port:<6} → {svc}")
        return "\n".join(lines)
