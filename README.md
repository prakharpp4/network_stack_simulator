# Network Stack Simulator
### End-to-End TCP/IP Communication using Object-Oriented Programming

---

## Project Overview

This simulator models complete network communication between two hosts using all five layers of the TCP/IP stack. Written in Python using OOP principles, it demonstrates how data travels from an application, through Transport → Network → Data Link → Physical layers, across a router, and is decapsulated in reverse at the receiver.

```
HostA  ──────────  Router  ──────────  HostB
192.168.1.2        192.168.1.1         192.168.2.2
                   192.168.2.1
```

---

## Features

| Layer | What is Simulated |
|---|---|
| Physical | Bit transmission delay, frame loss simulation |
| Data Link | Ethernet framing, CRC-8 checksum, Go-Back-N ARQ |
| Network | IPv4 packets, static routing table, TTL decrement |
| Transport | TCP (sliding window, seq/ack), UDP (best-effort) |
| Application | Chat over TCP, File Transfer with chunking |

---

## Architecture

```
network_simulator/
├── main.py          # Entry point (GUI or CLI mode)
├── gui.py           # Tkinter GUI (≈250 lines)
├── devices.py       # Host, Router, build_topology()
├── layers.py        # PhysicalLayer, DataLinkLayer, NetworkLayer, TransportLayer
├── packets.py       # EthernetFrame, IPPacket, TCPSegment, UDPSegment
├── applications.py  # ChatApplication, FileTransferApplication, demo functions
├── port_manager.py  # PortManager (well-known + ephemeral ports)
├── logger.py        # Structured event logger with subscriber callbacks
└── README.md        # This file
```

### Class Diagram (simplified)

```
Device
├── Host       ── owns DataLinkLayer, NetworkLayer, TransportLayer, PortManager
└── Router     ── owns NetworkLayer, DataLinkLayer (×2)

DataLinkLayer  ── owns PhysicalLayer
TransportLayer ── creates TCPSegment / UDPSegment
NetworkLayer   ── creates IPPacket, holds routing table
DataLinkLayer  ── creates EthernetFrame, runs Go-Back-N

ChatApplication        ── uses Host.send_tcp
FileTransferApplication── uses Host.transport.tcp_send_chunks
```

---

## How To Run

### Requirements
- Python 3.12 or newer
- No external packages required (only Python standard library + tkinter)

### Install (nothing to install)
```bash
cd network_simulator
```

### GUI Mode (default)
```bash
python main.py
```

### CLI / Terminal Mode (no GUI needed)
```bash
python main.py --cli
```

---

## GUI Guide

| Panel | Description |
|---|---|
| Topology Panel | Shows HostA → Router → HostB with IPs and MACs |
| Event Log | Colour-coded scrollable log of every layer event |
| Packet Inspector | Shows Frame / Packet / Segment for the last transmission |
| Buttons | Trigger each of the 5 demos |

### Button Actions

- **Send Chat Message** — HostA sends two TCP messages to HostB
- **Transfer File** — HostA splits a text file into chunks and transfers to HostB
- **Run Packet Loss Demo** — Demonstrates Go-Back-N retransmission
- **Show Encapsulation** — Step-by-step encap/decap walkthrough
- **Router Forwarding Demo** — Shows TTL decrement and route lookup



---

## Sample Output (CLI mode)

```
──────────────────────────────────────────────────────────────
  DEMO 1 — Chat Communication
──────────────────────────────────────────────────────────────
[12:01:10] [PORT_MGR  ] HostA                          | Registered service 'CHAT' on port 5000
[12:01:10] [PORT_MGR  ] HostA                          | Allocated ephemeral port 49152
[12:01:10] [APP       ] HostA -> HostB                 | Chat message: 'Hello from HostA!'
[12:01:10] [TRANSPORT ] HostA:49152 -> 192.168.2.2:5000| TCP segment created seq=0 len=17
[12:01:10] [NETWORK   ] HostA -> 192.168.2.2           | IP packet created TTL=64 proto=TCP
[12:01:10] [DATA_LINK ] HostA -> Router                | Framed payload → seq=0 CRC=0x7F
[12:01:10] [PHYSICAL  ] HostA -> Router                | Transmitting frame seq=0 (136 bits, delay≈0.14ms)
[12:01:10] [PHYSICAL  ] HostA -> Router                | ✓  Frame seq=0 delivered to physical medium
[12:01:10] [NETWORK   ] Router -> 192.168.2.2          | Forwarding packet TTL decremented to 63
[12:01:10] [NETWORK   ] HostB ->                       | ✓  IP packet decapsulated src=192.168.1.2 TTL=63
[12:01:10] [TRANSPORT ] HostB ->                       | TCP segment received src_port=49152 seq=0 len=17
[12:01:10] [APP       ] HostB ->                       | Message delivered to application: 'Hello from HostA!'
```

---

 demos showcasing encapsulation, packet loss recovery, and router forwarding.
