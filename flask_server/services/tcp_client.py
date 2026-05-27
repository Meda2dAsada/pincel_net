import socket
import json

TCP_HOST = "localhost"
TCP_PORT = 15000

def send_chat_message(room_id, player, message):
    data = {
        "type": "MESSAGE",
        "room_id": room_id,
        "player": player,
        "message": message
    }

    payload = json.dumps(data)

    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect((TCP_HOST, TCP_PORT))
        tcp_socket.sendall(payload.encode("utf-8"))
        tcp_socket.close()
        return True
    except Exception as e:
        print("[TCP ERROR]", e)
        return False