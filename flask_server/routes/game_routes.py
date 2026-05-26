from flask import Blueprint, session, render_template, request, jsonify
from routes.lobby_routes import rooms
from services.udp_client import send_draw_event
from services.tcp_client import send_chat_message
from db_client import DBClient

game_bp = Blueprint("game", __name__)

@game_bp.route("/game/<room_id>")
def game(room_id):
    player = session.get("player_name")

    return render_template(
        "game.html",
        room_id=room_id,
        player=player,
        players=rooms.get(room_id, [])
    )

@game_bp.route("/draw", methods=["POST"])
def draw():
    # Para dibujar no necesitamos guardar en BD, solo emitir por UDP
    data = request.get_json()

    room_id = data.get("room_id")
    x = data.get("x")
    y = data.get("y")
    color = data.get("color", "black")

    send_draw_event(room_id, x, y, color)
    print(f"[FLASK -> UDP] room={room_id}, x={x}, y={y}, color={color}")

    return jsonify({
        "status": "ok",
        "message": "Draw event received by Flask and sent to UDP"
    })

@game_bp.route("/guess", methods=["POST"])
def guess():
    data = request.get_json()

    room_id = data.get("room_id")
    message = data.get("message")
    player = session.get("player_name", "anonymous")

    # --- INTEGRACIÓN CON BD ---
    try:
        # my_port=0 evita colisiones de puertos en Flask
        db = DBClient(my_port=0) 
        
        # Nota: Si tu BD exige un INT estricto, tendrías que buscar el ID del 
        # usuario/sala. Por ahora pasamos el nombre/room_id directamente.
        db.save_guess(
            user_id=player, 
            game_id=room_id, 
            guess=message, 
            is_correct=False
        )
    except Exception as e:
        print(f"[ERROR DB] No se pudo guardar el guess: {e}")

    send_chat_message(room_id, player, message)
    print(f"[FLASK -> TCP] room={room_id}, player={player}, message={message}")

    return jsonify({
        "status": "ok",
        "message": "Guess received by Flask and sent to TCP"
    })