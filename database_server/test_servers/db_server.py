import socket

HOST = "127.0.0.1"
PORT = 6000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(5)

print(f"TCP server listening on {HOST}:{PORT}")

while True:
    client_socket, address = server.accept()
    data = client_socket.recv(4096)

    print(f"[TCP RECEIVED] From {address}: {data.decode('utf-8')}")

    client_socket.close()