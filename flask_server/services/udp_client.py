import socket
import json

UDP_HOST = "localhost"
UDP_PORT = 5002

def send_draw_event(room_id, start_x, start_y, end_x, end_y, color, size):
    data = {
        "type": "UPDATE_CANVAS",
        "room_id": room_id,
        "startX": start_x,
        "startY": start_y,
        "endX": end_x,
        "endY": end_y,
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
