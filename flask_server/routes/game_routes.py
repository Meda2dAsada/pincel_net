from flask import Blueprint, session, render_template, request, jsonify
import socket
import json

game_bp = Blueprint("game", __name__)

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

@game_bp.route("/game/<room_id>")
def game(room_id):
    player = session.get("player_name", "anonymous")
    return render_template("game.html", room_id=room_id, player=player)

@game_bp.route("/game/start", methods=["POST"])
def start_round():
    """Endpoint para que el creador de la sala o el sistema inicie el turno"""
    data = request.get_json()
    room_id = data.get("room_id")
    player = session.get("player_name", "anonymous")

    # Solicitamos al servidor C que configure la ronda y elija palabra random
    tcp_response = call_tcp_server({
        "type": "START_ROUND",
        "room_id": room_id,
        "player": player
    })
    return jsonify(tcp_response)

@game_bp.route("/guess", methods=["POST"])
def guess():
    data = request.get_json()
    room_id = data.get("room_id")
    message = data.get("message").strip()
    player = session.get("player_name", "anonymous")

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