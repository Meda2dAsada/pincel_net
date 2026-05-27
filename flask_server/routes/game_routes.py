from flask import Blueprint, render_template, request, jsonify, session, Response
from services.udp_client import send_draw_event
from services.tcp_client import send_chat_message
import json
import queue

game_bp = Blueprint("game_bp", __name__)

# Clientes conectados por sala para actualizar canvas y chat en vivo
room_clients = {}


def broadcast_to_room(room_id, event):
    """Manda un evento a todos los navegadores conectados a una sala."""
    if room_id not in room_clients:
        return

    disconnected = []

    for client_queue in room_clients[room_id]:
        try:
            client_queue.put(event)
        except Exception:
            disconnected.append(client_queue)

    for client_queue in disconnected:
        room_clients[room_id].remove(client_queue)


@game_bp.route("/game/<room_id>")
def game(room_id):
    player = session.get("player_name", "Invitado")

    # Por ahora lista simple. Después puede venir desde BD o servidor C.
    players = [player]

    return render_template(
        "game.html",
        room_id=room_id,
        player=player,
        players=players
    )


@game_bp.route("/draw", methods=["POST"])
def draw():
    data = request.get_json() or {}

    room_id = data.get("room_id")
    player = data.get("player", session.get("player_name", "anonymous"))

    if not room_id:
        return jsonify({"ok": False, "error": "room_id requerido"}), 400

    draw_event = {
        "type": "UPDATE_CANVAS",
        "room_id": room_id,
        "player": player,
        "startX": data.get("startX"),
        "startY": data.get("startY"),
        "endX": data.get("endX"),
        "endY": data.get("endY"),
        "color": data.get("color", "#000000"),
        "size": data.get("size", 5)
    }

    # 1. Mandar evento al servidor UDP en C
    udp_ok = send_draw_event(
        draw_event["room_id"],
        draw_event["player"],
        draw_event["startX"],
        draw_event["startY"],
        draw_event["endX"],
        draw_event["endY"],
        draw_event["color"],
        draw_event["size"]
    )

    # 2. Mandar evento a los navegadores conectados en la misma sala
    broadcast_to_room(room_id, draw_event)

    return jsonify({"ok": True, "udp_ok": udp_ok})


@game_bp.route("/clear", methods=["POST"])
def clear_canvas():
    data = request.get_json() or {}

    room_id = data.get("room_id")
    player = data.get("player", session.get("player_name", "anonymous"))

    if not room_id:
        return jsonify({"ok": False, "error": "room_id requerido"}), 400

    clear_event = {
        "type": "CLEAR_CANVAS",
        "room_id": room_id,
        "player": player
    }

    broadcast_to_room(room_id, clear_event)

    return jsonify({"ok": True})


@game_bp.route("/guess", methods=["POST"])
def guess():
    data = request.get_json() or {}

    room_id = data.get("room_id")
    player = data.get("player", session.get("player_name", "anonymous"))
    message = data.get("message", "").strip()

    if not room_id or not message:
        return jsonify({"ok": False, "error": "room_id y message requeridos"}), 400

    # 1. Mandar mensaje al servidor TCP en C
    tcp_ok = send_chat_message(room_id, player, message)

    # 2. Mandar mensaje a los otros navegadores por SSE
    chat_event = {
        "type": "CHAT_MESSAGE",
        "room_id": room_id,
        "player": player,
        "message": message
    }

    broadcast_to_room(room_id, chat_event)

    return jsonify({"ok": True, "tcp_ok": tcp_ok})


@game_bp.route("/events/<room_id>")
def events(room_id):
    def stream():
        client_queue = queue.Queue()

        if room_id not in room_clients:
            room_clients[room_id] = []

        room_clients[room_id].append(client_queue)

        try:
            while True:
                event = client_queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            if room_id in room_clients and client_queue in room_clients[room_id]:
                room_clients[room_id].remove(client_queue)

    return Response(stream(), mimetype="text/event-stream")