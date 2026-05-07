# PincelNet — Distributed Drawing and Guessing Game

## Project Description

PincelNet is a real-time multiplayer drawing and guessing game built as a distributed system. The project demonstrates the integration of multiple networked components: a Flask-based web server, socket servers written in C (both TCP and UDP), and a MySQL relational database. Players join rooms, take turns drawing a given word on a shared canvas, and earn points by guessing what others draw correctly.

The project was developed as part of the Distributed Computing course (Práctica 3 — Final Project), submitted on May 6, 2026.

Repository: https://github.com/Meda2dAsada/pincel_net

---

## Objectives

- Design and implement a distributed, multi-component application that separates concerns across distinct servers and services.
- Apply socket programming in C at the transport layer, supporting both TCP (reliable, connection-oriented) and UDP (lightweight, with redundancy).
- Build a web-facing layer using Python and Flask that acts as a client to the underlying C socket servers while serving the browser-based front-end.
- Implement real-time multiplayer game logic including room management, player turns, word assignment, drawing synchronization, and score tracking.
- Persist game data (users, scores, match history) in a MySQL database with secure connectivity.
- Ensure system availability through server redundancy and failover mechanisms on the UDP server layer.
- Practice team organization by dividing responsibilities into specialized sub-teams with clear interfaces between components.

---

## Scope

The system covers the following functional areas:

- A browser-accessible drawing canvas with a responsive interface for both desktop and mobile.
- A Flask web server that manages user sessions, game rooms, player turns, and word validation, and that communicates with the C socket servers over the local network.
- A TCP socket server in C that handles concurrent client connections, encrypted communication, and multiplayer state synchronization.
- A UDP socket server in C that provides a redundant backup layer with automatic failover should the primary server become unavailable.
- A MySQL database layer for storing and retrieving user accounts, scores, and game session data.

The project does not cover public deployment, user authentication beyond session management, or cross-internet socket communication; all socket communication is assumed to occur within the same local or private network.

---

## Team Organization

### Sub-Team 1 — Front-End with HTML and Flask Templates

Members:
- Jetzuvely Del Carmen González Gutiérrez (0266768) — GitHub: 0266768-velita
- José Carlos Béjar Gómez (0262149) — GitHub: carlosbejar65

Responsibilities:
- Design of the graphical user interface
- Development of HTML/CSS pages
- Implementation of the drawing canvas
- Creation of responsive views for desktop and mobile
- Connection of front-end views with Flask templates

---

### Sub-Team 2 — Python with Flask (Web Server acting as Client)

Members:
- Cesar Ernesto Pérez Gómez (0262141) — GitHub: CesarErnestoPerezGomez
- David Patricio Avalos Molinar (0267568) — GitHub: Pato23K
- Jorge Enrique Ruiz Liera (0250990) — GitHub: jorgeee22

Responsibilities:
- Development of the Flask server
- Implementation of game logic
- Management of rooms and player turns
- Handling of scores and word validation
- Communication with the C socket servers
- Management of user sessions and routes

---

### Sub-Team 3-A — TCP Socket Server in C

Members:
- Uriel Arturo Monarrez Cervantes (0263097) — GitHub: UrielMC17
- Rodrigo Zatarain Aguirre (0267814) — GitHub: 0267814

Responsibilities:
- Development of the TCP socket server in C
- Handling of concurrent client connections
- Implementation of encrypted communication
- Management of multiplayer synchronization
- Efficient processing of client requests

---

### Sub-Team 3-B — UDP and Redundancy Server in C

Members:
- Alexis Vargas Moreno (0268585) — GitHub: AlexisVarBB
- Carlos Santiago Cruz Díaz (0264547) — GitHub: CSCD13
- Iker Jesús Ortiz Rojero (0263663) — GitHub: Meda2dAsada

Responsibilities:
- Development of the UDP socket server
- Implementation of server redundancy and failover
- Synchronization of backup servers
- Optimization of networking performance
- Maintenance of server availability if the main server fails

---

### Sub-Team 4 — Database with MySQL

Members:
- Rodrigo López Gómez (0262146) — GitHub: rodlopg

Responsibilities:
- Design and management of the MySQL database
- Storage of users, scores, and game data
- Configuration of secure database connections
- Management of persistence and backups
- Support for encrypted communication with servers

---

## General Architecture

```
[ Browser / Client ]
        |
        v
[ Flask Web Server (Python) ]  <-->  [ MySQL Database ]
        |
        |-- TCP -->  [ TCP Server in C  (Sub-Team 3-A) ]
        |
        \-- UDP -->  [ UDP Server in C  (Sub-Team 3-B) ]
                          |
                          \-- Failover / Redundancy
```
