"""
main.py — Entry point for the Network Stack Simulator.

Run modes:
    python main.py          → launches Tkinter GUI
    python main.py --cli    → runs all demos in the terminal (no GUI)

The --cli mode is useful on headless servers (e.g., SSH sessions)
and for quickly verifying that all modules work correctly.
"""

import sys
from logger import Logger


def run_cli_demos() -> None:
    """Run all five demos in the terminal with console logging."""

    # Wire the logger to print directly to stdout
    Logger.subscribe(print)

    from devices import build_topology
    from applications import (
        ChatApplication,
        FileTransferApplication,
        run_encapsulation_demo,
        run_packet_loss_demo,
        run_router_demo,
    )

    host_a, router, host_b = build_topology()

    # ── Demo 1: Chat ──────────────────────────
    Logger.separator("DEMO 1 — Chat Communication")
    chat = ChatApplication(host_a, host_b, router)
    chat.send("Hello from HostA!")
    chat.send("This is TCP-based chat.")
    chat.close()

    host_a.reset()
    host_b.reset()

    # ── Demo 2: File Transfer ─────────────────
    Logger.separator("DEMO 2 — File Transfer")
    ftp = FileTransferApplication(host_a, host_b, router)
    sample = (
        "Line 1: Network simulation in Python.\n"
        "Line 2: Demonstrating TCP file transfer.\n"
        "Line 3: Chunks reassembled at receiver.\n"
    )
    ftp.transfer("demo.txt", sample)
    ftp.close()

    host_a.reset()
    host_b.reset()

    # ── Demo 3: Packet Loss ───────────────────
    run_packet_loss_demo(host_a, host_b, router)

    host_a.reset()
    host_b.reset()

    # ── Demo 4: Router Forwarding ─────────────
    run_router_demo(host_a, host_b, router)

    host_a.reset()
    host_b.reset()

    # ── Demo 5: Encapsulation ─────────────────
    run_encapsulation_demo(host_a, host_b, router)

    Logger.separator("All demos complete.")


def main() -> None:
    if "--cli" in sys.argv:
        run_cli_demos()
    else:
        # GUI mode — import here so missing Tkinter on a headless server
        # doesn't crash the --cli path
        try:
            from gui import launch
            launch()
        except ImportError as exc:
            print(f"[ERROR] Cannot start GUI: {exc}")
            print("Tip: run with --cli flag for terminal-only mode.")
            sys.exit(1)


if __name__ == "__main__":
    main()
