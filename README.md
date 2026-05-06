# 🎨 Proyecto PincelNet Arquitectura por Sub-Equipos

> Juego multijugador de dibujo y adivinanza desarrollado con Flask, C Sockets y MySQL.

---

## 👥 Organización del Equipo

### 🖥️ Sub-Equipo 1 — Front-End con HTML y Flask Templates
**Integrantes:**
- Jetzuvely Del Carmen González Gutiérrez
- José Carlos Béjar Gómez

**Responsabilidades:**
- Diseño de la interfaz gráfica de usuario
- Desarrollo de páginas HTML/CSS
- Implementación del canvas de dibujo
- Creación de vistas responsivas para escritorio y móvil
- Conexión de las vistas front-end con templates de Flask

---

### ⚙️ Sub-Equipo 2 — Python con Flask (Servidor Web como Cliente)
**Integrantes:**
- Cesar Ernesto Pérez Gómez
- David Patricio Avalos Molinar
- Jorge Enrique Ruiz Liera

**Responsabilidades:**
- Desarrollo del servidor Flask
- Implementación de la lógica del juego
- Gestión de salas y turnos de jugadores
- Manejo de puntuaciones y validación de palabras
- Comunicación con los servidores C de sockets
- Gestión de sesiones de usuario y rutas

---

### 🔌 Sub-Equipo 3-A — Servidor TCP Socket en C
**Integrantes:**
- Uriel Arturo Monarrez Cervantes
- Rodrigo Zatarain Aguirre

**Responsabilidades:**
- Desarrollo del servidor TCP socket en C
- Manejo de conexiones concurrentes de clientes
- Implementación de comunicación cifrada
- Gestión de sincronización multijugador
- Procesamiento eficiente de solicitudes de clientes

---

### 📡 Sub-Equipo 3-B — Servidor UDP y Redundancia en C
**Integrantes:**
- Alexis Vargas Moreno
- Carlos Santiago Cruz Díaz
- Iker Jesús Ortiz Rojero

**Responsabilidades:**
- Desarrollo del servidor UDP socket
- Implementación de redundancia y failover del servidor
- Sincronización de servidores de respaldo
- Optimización del rendimiento de red
- Mantenimiento de disponibilidad si el servidor principal falla

---

### 🗄️ Sub-Equipo 4 — Base de Datos con MySQL
**Integrantes:**
- Rodrigo López Gómez

**Responsabilidades:**
- Diseño y gestión de la base de datos MySQL
- Almacenamiento de usuarios, puntuaciones y datos de partidas
- Configuración de conexiones seguras a la base de datos
- Gestión de persistencia y respaldos
- Soporte de comunicación cifrada con los servidores

---

## 🏗️ Arquitectura General

```
[ Navegador / Cliente ]
        |
        v
[ Flask Web Server (Python) ]  <-->  [ MySQL Database ]
        |
        |-- TCP -->  [ Servidor TCP en C  (Sub-Equipo 3-A) ]
        |
        \-- UDP -->  [ Servidor UDP en C  (Sub-Equipo 3-B) ]
                          |
                          \-- Failover / Redundancia
```
