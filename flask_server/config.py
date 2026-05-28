import socket

# Flask se expone a la red
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000

SERVER_HOST = socket.gethostbyname(socket.gethostname())

# Servidor TCP en Docker
TCP_HOST = SERVER_HOST
TCP_PORT = 15000

# Servidor UDP en Docker
UDP_HOST = SERVER_HOST
UDP_PORT = 5002
