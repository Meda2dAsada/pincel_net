# config.py

# Flask se expone a la red
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000

# IP estando dentro de la up, puedes cambiarlo para hacer pruebas desde casa.
SERVER_HOST = "192.168.100.14"

# Servidor TCP en Docker
TCP_HOST = SERVER_HOST
TCP_PORT = 15000

# Servidor UDP en Docker
UDP_HOST = SERVER_HOST
UDP_PORT = 5002