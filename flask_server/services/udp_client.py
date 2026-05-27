import socket
import json
from config import UDP_HOST, UDP_PORT

def send_draw_event(room_id, player, startX, startY, endX, endY, color, size):
    data = {
        "type": "UPDATE_CANVAS",
        "room_id": room_id,
        "player": player,
        "startX": startX,
        "startY": startY,
        "endX": endX,
        "endY": endY,
        "color": color,
        "size": size
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