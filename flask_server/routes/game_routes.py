from flask import Blueprint, render_template, request, jsonify, session, Response
import socket
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


TCP_HOST = "127.0.0.1"
TCP_PORT = 15000

def call_tcp_server(payload: dict) -> dict:
    """Función auxiliar para comunicarse de forma síncrona con el servidor C"""
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect((TCP_HOST, TCP_PORT))
        tcp_socket.sendall(json.dumps(payload).encode("utf-8"))
        
        response = tcp_socket.recv(1048).decode("utf-8")
        tcp_socket.close()
        return json.loads(response)
    except Exception as e:
        print("[TCP SERVER ERROR]", e)
        return {}

TCP_HOST = "127.0.0.1"
TCP_PORT = 15000

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
    player = session.get("player_name", "anonymous")
    state_data = game_state.get_player_state(room_id, player, rooms.get(room_id, []))
    return jsonify(state_data)


@game_bp.route("/messages/<room_id>")
def messages(room_id):
    after_id = request.args.get("after", default=0, type=int)
    payload = game_state.get_chat_events(room_id, after_id, rooms.get(room_id, []))
    return jsonify(payload)



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

    # 1. Mandar evento al servidor TCP en C para persistencia
    tcp_resp = call_tcp_server(draw_event)

    # 2. Mandar evento a los navegadores conectados en la misma sala
    broadcast_to_room(room_id, draw_event)

    return jsonify({"ok": True, "tcp_status": tcp_resp.get("status")})


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

    # Notificar al servidor TCP para que limpie el JSON
    call_tcp_server(clear_event)

    broadcast_to_room(room_id, clear_event)

    return jsonify({"ok": True})

@game_bp.route("/events/<room_id>")
def events(room_id):
    """Stream de eventos en tiempo real (SSE) para la sala."""
    def stream():
        q = queue.Queue()
        if room_id not in room_clients:
            room_clients[room_id] = []
        room_clients[room_id].append(q)
        
        try:
            while True:
                event = q.get()
                yield f"data: {json.dumps(event)}\n\n"
        except GeneratorExit:
            room_clients[room_id].remove(q)

    return Response(stream(), mimetype="text/event-stream")

@game_bp.route("/game/start", methods=["POST"])
def start_game():
    data = request.get_json() or {}
    room_id = data.get("room_id")
    player = session.get("player_name", "anonymous")
    
    # Llamamos al servidor C para que asigne palabra y dibujante
    tcp_response = call_tcp_server({
        "type": "START_ROUND",
        "room_id": room_id,
        "player": player
    })
    return jsonify(tcp_response)


@game_bp.route("/guess", methods=["POST"])
def guess():
    data = request.get_json() or {}

    room_id = data.get("room_id")
    message = data.get("message").strip()
    player = session.get("player_name", "anonymous")
    result = game_state.submit_guess(room_id, player, message, rooms.get(room_id, []))

    # Enviamos el intento al servidor C para su validación formal
    tcp_response = call_tcp_server({
        "type": "MESSAGE",
        "room_id": room_id,
        "player": player,
        "message": message
    })

    # Si la lógica centralizada en C dice que es correcto, se procede a guardar el log en la base de datos
    if tcp_response.get("status") == "correct":
        try:
            from db_client import DBClient
            db = DBClient(my_port=0)
            db.save_guess(user_id=player, game_id=room_id, guess=message, is_correct=True)
            print(f"[BD INTEGRACIÓN] Puntos guardados para {player}")
        except Exception as e:
            print(f"[ERROR BD] No se pudo persistir el acierto: {e}")

    return jsonify(tcp_response)

@game_bp.route("/game/state/<room_id>", methods=["GET"])
def get_game_state(room_id):
    """GETTER de estado de la sala: El frontend llamará a esto de forma recurrente"""
    tcp_response = call_tcp_server({
        "type": "GET_STATE",
        "room_id": room_id
    })
    return jsonify(tcp_response)