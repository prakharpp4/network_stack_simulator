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

## Screenshots

> Run the GUI and take screenshots for your report here.

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

## Viva / Interview Questions & Answers

### Q1. What is encapsulation in networking?
**A.** Encapsulation is the process of adding protocol headers (and sometimes trailers) at each layer as data travels down the stack. The application message becomes the payload of a TCP segment, which becomes the payload of an IP packet, which becomes the payload of an Ethernet frame. At the receiver, the reverse (decapsulation) strips each header.

### Q2. What is the difference between TCP and UDP?
**A.** TCP is connection-oriented and reliable: it uses sequence numbers, acknowledgements, retransmission, and flow control to guarantee ordered delivery. UDP is connectionless and unreliable: it sends datagrams with no acknowledgement or retransmission, giving lower overhead and latency. TCP is used for chat (needs reliability); UDP suits DNS, video streaming where speed > reliability.

### Q3. What is Go-Back-N ARQ?
**A.** A sliding-window Automatic Repeat reQuest protocol. The sender can have up to N unacknowledged frames in flight. If any frame is lost or corrupted, the sender retransmits **all** frames from that sequence number onward. The receiver only accepts in-order frames; out-of-order frames are discarded (which triggers the retransmit). This project implements it in DataLinkLayer.

### Q4. What is CRC and how does it work?
**A.** Cyclic Redundancy Check is an error-detection code. The sender computes a checksum by treating the frame contents as a polynomial, divides it by a fixed generator polynomial, and appends the remainder. The receiver recomputes the CRC; a mismatch means the frame was corrupted. This project uses a simplified XOR checksum (same concept, less math) via `compute_crc()` in packets.py.

### Q5. What does TTL do in an IP packet?
**A.** Time-To-Live prevents packets from looping forever. Each router that forwards a packet decrements TTL by 1. If TTL reaches 0, the packet is dropped and an ICMP "Time Exceeded" message is sent back (not simulated here). Linux defaults to TTL=64; this project uses the same default.

### Q6. What is a MAC address and how does ARP work?
**A.** A MAC (Media Access Control) address is a 48-bit hardware address on a network interface (format `AA:BB:CC:DD:EE:FF`). ARP (Address Resolution Protocol) maps an IP address to a MAC address on the same LAN. When HostA wants to send to the router, it broadcasts "Who has 192.168.1.1?" and the router replies with its MAC. This project hardcodes MACs for simplicity.

### Q7. What is a routing table and how is it used?
**A.** A routing table maps destination IP prefixes to next-hop IP addresses or exit interfaces. When a router receives a packet, it looks up the destination IP in the table (longest prefix match) and forwards the packet to the next hop. This project uses a simple dictionary-based static routing table in `NetworkLayer`.

### Q8. What is the difference between a Hub, Switch, and Router?
**A.** A **hub** broadcasts every frame to all ports (Layer 1). A **switch** forwards frames only to the correct MAC address port (Layer 2). A **router** forwards packets between different IP subnets using routing tables (Layer 3). This project includes a Layer-3 router.

### Q9. What are well-known ports vs ephemeral ports?
**A.** Well-known ports (0–1023) are assigned to standard services by IANA: HTTP=80, HTTPS=443, FTP=21, SSH=22. Ephemeral ports (49152–65535) are dynamically allocated by the OS to client-side connections and released after the connection closes. `PortManager` in this project models both.

### Q10. What is the sliding window protocol in TCP?
**A.** TCP's sliding window allows the sender to have multiple unacknowledged segments in flight simultaneously, improving throughput. The window size controls how many segments can be outstanding. As ACKs arrive, the window "slides" forward. This is implemented in `TransportLayer.tcp_send_chunks()`.

### Q11. What is the difference between a segment, packet, and frame?
**A.** A **segment** is the PDU at the Transport layer (TCP/UDP). A **packet** is the PDU at the Network layer (IP). A **frame** is the PDU at the Data Link layer (Ethernet). Each lower layer wraps the upper layer's PDU as its payload.

### Q12. What happens if a CRC check fails?
**A.** The frame is silently discarded at the Data Link layer. For TCP, the missing ACK triggers a retransmission timeout. For UDP, the data is simply lost. In this project `DataLinkLayer.receive_frame()` logs and discards frames with bad CRCs.

### Q13. Why does TCP have a 3-way handshake?
**A.** The handshake establishes a reliable connection: (1) Client sends SYN, (2) Server replies SYN-ACK, (3) Client sends ACK. This synchronises sequence numbers on both sides so each end knows what data the other has received. This project simulates data transfer without the full handshake for brevity.

### Q14. What is the purpose of the Physical layer?
**A.** The Physical layer converts digital frames into signals (electrical, optical, or radio) and transmits them over the medium. It defines bit rates, connectors, and signal levels. In this project it models transmission delay as `bits / bandwidth`.

### Q15. What is subnetting?
**A.** Subnetting divides a large IP address range into smaller networks. In this project, HostA is on 192.168.1.0/24 and HostB is on 192.168.2.0/24 — two separate subnets connected by the router.

### Q16. How does OOP benefit network simulation?
**A.** Each protocol layer becomes a class with well-defined methods, matching the real-world principle of layer independence. Encapsulation (the OOP kind) hides implementation details; polymorphism lets devices be extended without changing callers; composition models "a host HAS-A transport layer."

### Q17. What is the difference between connection-oriented and connectionless?
**A.** Connection-oriented (TCP) establishes a logical channel before data transfer, provides ordered delivery, and tears down the connection afterward. Connectionless (UDP) sends each datagram independently with no state. Connection-oriented costs setup time but provides reliability.

### Q18. What is ARP poisoning?
**A.** ARP poisoning (a security attack) involves sending fake ARP replies to associate the attacker's MAC with a legitimate IP, redirecting traffic through the attacker (man-in-the-middle). This is why secure networks use static ARP entries or dynamic ARP inspection.

### Q19. Why is Go-Back-N less efficient than Selective Repeat?
**A.** In Go-Back-N, if frame N is lost, all frames N, N+1, N+2, … (up to the window) are retransmitted even if they arrived correctly. Selective Repeat only retransmits the specific lost frame, using receiver buffering. GBN is simpler to implement; SR is more efficient on lossy links.

### Q20. How would you extend this project to support HTTPS?
**A.** Add a TLS simulation layer between Application and Transport: generate a simulated key exchange (record the server's public key, perform a simulated handshake), then encrypt payloads with a simple XOR cipher or Python's `cryptography` library before passing to TCP. Register port 443 in PortManager.

---

## Resume Descriptions

### 2-Line Version
**Network Stack Simulator** | Python, OOP, Tkinter  
Built a full TCP/IP stack simulator in Python modelling all five layers (Physical → Application) with Ethernet framing, IPv4 routing, TCP sliding window, UDP, and Go-Back-N ARQ; demonstrated with a Tkinter GUI featuring live packet inspection.

### 4-Line Version
**Network Stack Simulator** | Python 3.12 · OOP · Tkinter · Computer Networks  
Designed and implemented a full TCP/IP stack simulator from scratch, modelling Physical, Data Link (Ethernet + CRC + Go-Back-N ARQ), Network (IPv4, static routing, TTL), Transport (TCP sliding window, UDP), and Application layers (chat, file transfer).  
Architected 8 modules (≈1200 lines) using OOP — Device, Host, Router, five layer classes, PDU dataclasses, PortManager — with zero external libraries.  
Built a Tkinter GUI with colour-coded live event logs, a Packet Inspector panel, and five runnable demos showcasing encapsulation, packet loss recovery, and router forwarding.
