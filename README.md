# Python Socket Programming

A Python-based socket programming project that progressively implements
TCP/UDP communication, timeout handling, multi-client support, and a
peer-to-peer (P2P) communication system with a GUI.

## Overview

This project was developed through several stages, gradually extending
the functionality of a basic socket communication system.

The project focuses on:
- TCP and UDP network communication
- Message segmentation and reconstruction
- Data encryption and integrity verification
- Connection timeout handling
- Multi-client server communication
- Peer-to-peer communication
- GUI-based operation

## Features

### 1. TCP
- Implemented local Client/Server communication using TCP.
- Handles messages that exceed the transmission size by splitting them
  into multiple segments.
- Reconstructs the segmented message at the receiver side to ensure
  the original message can be correctly interpreted.

### 2. TCP + UDP
- Supports both TCP and UDP communication.
- Added data protection before transmission.
- The sender processes the message before transmission, and the receiver
  performs the corresponding processing to recover the original message.

### 3. Timeout and Multiport
- Added timeout handling to prevent failed connections from occupying
  network resources for an extended period.
- Supports multiple connections through multiple ports.
- Allows the server to handle multiple clients simultaneously.

### 4. P2P System
- Integrates the functionality developed in previous stages.
- Implements a peer-to-peer communication system.
- Supports network communication with the previously developed
  transmission and connection-handling mechanisms.
- Added a GUI to provide a more convenient user interface.

## Project Structure

```text
.
├── TCP/
├── TCP_UDP/
├── Timeout_Multiport/
├── P2P/
└── README.md
