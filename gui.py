"""
gui.py — Tkinter GUI for the Network Stack Simulator.

Layout (top → bottom):
  ┌─────────────────────────────────────┐
  │  Title bar                          │
  ├─────────────────────────────────────┤
  │  Topology panel   HostA→Router→HostB│
  ├──────────────────┬──────────────────┤
  │  Log viewer      │  Packet Inspector│
  │  (scrollable)    │                  │
  ├──────────────────┴──────────────────┤
  │  Demo buttons (4 × actions)         │
  └─────────────────────────────────────┘

The GUI is intentionally simple — its only job is to make the
simulator easy to demonstrate during a lab or interview.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from typing import Optional

from logger import Logger
from devices import build_topology
from applications import (
    ChatApplication,
    FileTransferApplication,
    run_encapsulation_demo,
    run_packet_loss_demo,
    run_router_demo,
)


# ──────────────────────────────────────────────
#  Colour palette
# ──────────────────────────────────────────────

BG_DARK    = "#1e2130"
BG_MED     = "#252839"
BG_PANEL   = "#2e3250"
ACCENT     = "#4fc3f7"
GREEN      = "#69f0ae"
ORANGE     = "#ffb74d"
RED        = "#ef5350"
TEXT_LIGHT = "#eceff1"
TEXT_DIM   = "#90a4ae"

LAYER_COLORS = {
    "APP":       "#c5e1a5",
    "TRANSPORT": "#80deea",
    "NETWORK":   "#ffcc80",
    "DATA_LINK": "#ce93d8",
    "PHYSICAL":  "#ef9a9a",
    "PORT_MGR":  "#b0bec5",
    "DEVICE":    "#fff59d",
    "DEMO":      "#f8bbd0",
}


class SimulatorGUI:
    """Main application window."""

    SAMPLE_FILE_CONTENT = (
        "This is a sample text file being transferred over the network.\n"
        "It demonstrates how FileTransferApplication splits content into chunks,\n"
        "sends each chunk as a TCP segment, and reassembles them at the receiver.\n"
        "Line 4: Network simulation is a great way to learn TCP/IP.\n"
        "Line 5: End of file."
    )

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Network Stack Simulator")
        self.root.configure(bg=BG_DARK)
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)

        # Build the network topology
        self.host_a, self.router, self.host_b = build_topology()

        # Track the last PDU for the inspector panel
        self._last_frame_text:   str = "—"
        self._last_packet_text:  str = "—"
        self._last_segment_text: str = "—"

        # Subscribe the log display to the Logger
        Logger.subscribe(self._append_log)

        self._build_ui()
        Logger.separator("Network Stack Simulator — Ready")
        Logger.log("DEVICE", "Topology", "", "HostA ──── Router ──── HostB")

    # ──────────────────────────────────────────
    #  UI construction
    # ──────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_title()
        self._build_topology_panel()
        self._build_main_area()
        self._build_button_bar()

    def _build_title(self) -> None:
        title_frame = tk.Frame(self.root, bg=BG_DARK, pady=8)
        title_frame.pack(fill=tk.X)

        tk.Label(
            title_frame,
            text="⬡  Network Stack Simulator",
            font=("Courier New", 16, "bold"),
            bg=BG_DARK,
            fg=ACCENT,
        ).pack(side=tk.LEFT, padx=20)

        tk.Label(
            title_frame,
            text="TCP/IP End-to-End Communication  |  OOP Implementation",
            font=("Courier New", 9),
            bg=BG_DARK,
            fg=TEXT_DIM,
        ).pack(side=tk.LEFT)

        # Clear-log button on the right
        tk.Button(
            title_frame,
            text="Clear Log",
            command=self._clear_log,
            bg=BG_PANEL,
            fg=TEXT_DIM,
            activebackground=BG_MED,
            relief=tk.FLAT,
            padx=10,
            font=("Courier New", 9),
        ).pack(side=tk.RIGHT, padx=15)

    def _build_topology_panel(self) -> None:
        topo_frame = tk.Frame(self.root, bg=BG_MED, pady=10)
        topo_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        tk.Label(
            topo_frame,
            text="Network Topology",
            font=("Courier New", 9, "bold"),
            bg=BG_MED,
            fg=TEXT_DIM,
        ).pack(anchor=tk.W, padx=15)

        topo_inner = tk.Frame(topo_frame, bg=BG_MED)
        topo_inner.pack()

        nodes = [
            ("HostA\n192.168.1.2\nAA:BB:CC:DD:EE:01", GREEN),
            ("───────\n  TCP/IP\n  link  ", TEXT_DIM),
            ("Router\n192.168.1.1\n192.168.2.1",        ORANGE),
            ("───────\n  TCP/IP\n  link  ", TEXT_DIM),
            ("HostB\n192.168.2.2\nAA:BB:CC:DD:EE:02", ACCENT),
        ]

        for text, colour in nodes:
            tk.Label(
                topo_inner,
                text=text,
                font=("Courier New", 9),
                bg=BG_MED,
                fg=colour,
                justify=tk.CENTER,
                padx=5,
            ).pack(side=tk.LEFT)

    def _build_main_area(self) -> None:
        """Log viewer (left) + Packet Inspector (right)."""
        pane = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL,
            bg=BG_DARK, sashwidth=4, sashrelief=tk.FLAT,
        )
        pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ── Log Viewer ──
        log_frame = tk.Frame(pane, bg=BG_MED, bd=1, relief=tk.FLAT)
        pane.add(log_frame, minsize=600)

        tk.Label(
            log_frame,
            text="  Event Log",
            font=("Courier New", 9, "bold"),
            bg=BG_MED,
            fg=TEXT_DIM,
            anchor=tk.W,
        ).pack(fill=tk.X)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            bg=BG_DARK,
            fg=TEXT_LIGHT,
            font=("Courier New", 9),
            wrap=tk.NONE,
            state=tk.DISABLED,
            relief=tk.FLAT,
            bd=0,
            insertbackground=ACCENT,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Colour tags per layer
        for layer, colour in LAYER_COLORS.items():
            self.log_text.tag_config(layer, foreground=colour)

        # ── Packet Inspector ──
        inspect_frame = tk.Frame(pane, bg=BG_MED, bd=1, relief=tk.FLAT)
        pane.add(inspect_frame, minsize=260)

        tk.Label(
            inspect_frame,
            text="  Packet Inspector",
            font=("Courier New", 9, "bold"),
            bg=BG_MED,
            fg=TEXT_DIM,
            anchor=tk.W,
        ).pack(fill=tk.X)

        self._inspector_text = scrolledtext.ScrolledText(
            inspect_frame,
            bg=BG_DARK,
            fg=TEXT_LIGHT,
            font=("Courier New", 9),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            bd=0,
            width=32,
        )
        self._inspector_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _build_button_bar(self) -> None:
        bar = tk.Frame(self.root, bg=BG_DARK, pady=8)
        bar.pack(fill=tk.X, padx=10, pady=(0, 10))

        buttons = [
            ("💬  Send Chat Message",     self._run_chat_demo,         ACCENT),
            ("📁  Transfer File",          self._run_file_demo,         GREEN),
            ("⚠   Run Packet Loss Demo",   self._run_loss_demo,         ORANGE),
            ("🔬  Show Encapsulation",     self._run_encap_demo,        "#ce93d8"),
            ("🌐  Router Forwarding Demo", self._run_router_demo,       "#ffcc80"),
        ]

        for label, command, colour in buttons:
            tk.Button(
                bar,
                text=label,
                command=command,
                bg=BG_PANEL,
                fg=colour,
                activebackground=BG_MED,
                activeforeground=TEXT_LIGHT,
                relief=tk.FLAT,
                padx=14,
                pady=6,
                font=("Courier New", 9, "bold"),
                cursor="hand2",
                bd=0,
            ).pack(side=tk.LEFT, padx=5)

    # ──────────────────────────────────────────
    #  Log display
    # ──────────────────────────────────────────

    def _append_log(self, line: str) -> None:
        """Called by Logger for every event; schedules a GUI update."""
        self.root.after(0, self._write_log_line, line)

    def _write_log_line(self, line: str) -> None:
        self.log_text.config(state=tk.NORMAL)
        # Detect which layer the line belongs to for colouring
        tag = None
        for layer in LAYER_COLORS:
            if f"[{layer}" in line or f"] {layer}" in line:
                tag = layer
                break
        if tag:
            self.log_text.insert(tk.END, line + "\n", tag)
        else:
            self.log_text.insert(tk.END, line + "\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def _clear_log(self) -> None:
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)
        Logger.clear()
        self._update_inspector("—", "—", "—")

    # ──────────────────────────────────────────
    #  Packet Inspector
    # ──────────────────────────────────────────

    def _update_inspector(
        self,
        frame_txt: str,
        packet_txt: str,
        segment_txt: str,
    ) -> None:
        text = (
            "┌─ Ethernet Frame ────────┐\n"
            f"{frame_txt}\n\n"
            "┌─ IP Packet ─────────────┐\n"
            f"{packet_txt}\n\n"
            "┌─ TCP/UDP Segment ───────┐\n"
            f"{segment_txt}\n"
        )
        self._inspector_text.config(state=tk.NORMAL)
        self._inspector_text.delete("1.0", tk.END)
        self._inspector_text.insert(tk.END, text)
        self._inspector_text.config(state=tk.DISABLED)

    # ──────────────────────────────────────────
    #  Demo runners  (each runs in a thread to
    #  keep the GUI responsive)
    # ──────────────────────────────────────────

    def _run_in_thread(self, fn) -> None:
        """Run fn in a daemon thread so the GUI stays responsive."""
        t = threading.Thread(target=fn, daemon=True)
        t.start()

    def _reset_hosts(self) -> None:
        """Reset host state between demos."""
        self.host_a.reset()
        self.host_b.reset()

    def _run_chat_demo(self) -> None:
        def _task():
            self._reset_hosts()
            Logger.separator("DEMO 1 — Chat Communication")
            chat = ChatApplication(self.host_a, self.host_b, self.router)

            messages = [
                "Hello from HostA!",
                "How is the network today?",
            ]
            for msg in messages:
                chat.send(msg)
                # Update inspector with representative PDU info
                self.root.after(0, self._update_inspector,
                    f"src={self.host_a.mac_address}\ndst=AA:BB:CC:DD:EE:AA\nCRC=computed",
                    f"src={self.host_a.ip_address}\ndst={self.host_b.ip_address}\nTTL=64  proto=TCP",
                    f"TCP  {chat._src_port}→5000\npayload='{msg[:20]}'",
                )

            chat.close()
        self._run_in_thread(_task)

    def _run_file_demo(self) -> None:
        def _task():
            self._reset_hosts()
            Logger.separator("DEMO 2 — File Transfer")
            ftp = FileTransferApplication(self.host_a, self.host_b, self.router)

            def progress(current: int, total: int):
                pct = int(current / total * 100)
                self.root.after(0, self._update_inspector,
                    f"src={self.host_a.mac_address}\ndst=AA:BB:CC:DD:EE:AA",
                    f"{self.host_a.ip_address}→{self.host_b.ip_address}\nTTL=63 proto=TCP",
                    f"TCP chunk {current}/{total}\n({pct}% complete)",
                )

            ftp.transfer(
                filename="sample.txt",
                content=self.SAMPLE_FILE_CONTENT,
                progress_callback=progress,
            )
            ftp.close()
        self._run_in_thread(_task)

    def _run_loss_demo(self) -> None:
        def _task():
            self._reset_hosts()
            run_packet_loss_demo(self.host_a, self.host_b, self.router)
            self.root.after(0, self._update_inspector,
                "Frame seq=0\n[LOST — retransmitted]",
                f"{self.host_a.ip_address}→{self.host_b.ip_address}",
                "TCP GBN retransmission",
            )
        self._run_in_thread(_task)

    def _run_encap_demo(self) -> None:
        def _task():
            self._reset_hosts()
            run_encapsulation_demo(self.host_a, self.host_b, self.router)
            self.root.after(0, self._update_inspector,
                f"src={self.host_a.mac_address}\ndst=AA:BB:CC:DD:EE:AA\nCRC=0xXX",
                f"{self.host_a.ip_address}→{self.host_b.ip_address}\nTTL=63 proto=TCP",
                "TCP seq=0 ack=0\npayload='Hello, Network!'",
            )
        self._run_in_thread(_task)

    def _run_router_demo(self) -> None:
        def _task():
            self._reset_hosts()
            run_router_demo(self.host_a, self.host_b, self.router)
            self.root.after(0, self._update_inspector,
                f"src={self.host_a.mac_address}",
                f"{self.host_a.ip_address}→{self.host_b.ip_address}\nTTL=63 (decremented)",
                "TCP forwarded via Router",
            )
        self._run_in_thread(_task)


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────

def launch() -> None:
    root = tk.Tk()
    app  = SimulatorGUI(root)
    root.mainloop()
