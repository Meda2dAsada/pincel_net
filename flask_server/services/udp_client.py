import socket
import json

UDP_HOST = "127.0.0.1"
UDP_PORT = 6001

def send_draw_event(room_id, x, y, color):
    data = {
        "type": "UPDATE_CANVAS",
        "room_id": room_id,
        "x": x,
        "y": y,
        "color": color
    }

    message = json.dumps(data)

    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.sendto(message.encode("utf-8"), (UDP_HOST, UDP_PORT))
        udp_socket.close()
        return True
    except Exception as e:
        print("[UDP ERROR]", e)
        return False