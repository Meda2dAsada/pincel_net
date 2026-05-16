import socket

HOST = "127.0.0.1"
PORT = 6001

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))

print(f"UDP server listening on {HOST}:{PORT}")

while True:
    data, address = server.recvfrom(4096)
    print(f"[UDP RECEIVED] From {address}: {data.decode('utf-8')}")