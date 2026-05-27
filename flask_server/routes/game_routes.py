import hashlib

from flask import Blueprint, session, render_template, request, jsonify, redirect, url_for

from routes.lobby_routes import rooms
from services.game_state import game_state
from services.udp_client import send_draw_event
from services.tcp_client import send_chat_message
from services.db_client import DBClient

game_bp = Blueprint("game", __name__)


def _stable_db_id(value):
    digest = hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


@game_bp.route("/game/<room_id>")
def game(room_id):
    player = session.get("player_name")
    if not player:
        return redirect(url_for("lobby.lobby"))

    state = game_state.get_player_state(room_id, player, rooms.get(room_id, []))

    return render_template(
        "game.html",
        room_id=room_id,
        player=player,
        players=rooms.get(room_id, []),
        game_state=state,
    )


@game_bp.route("/state/<room_id>")
def state(room_id):
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
    data = request.get_json(silent=True) or {}
    room_id = data.get("room_id")
    player = session.get("player_name", "anonymous")

    can_draw, reason = game_state.can_player_draw(room_id, player, rooms.get(room_id, []))
    if not can_draw:
        return jsonify({
            "status": "error",
            "message": reason,
            "state": game_state.get_player_state(room_id, player, rooms.get(room_id, [])),
        }), 403

    start_x = data.get("startX")
    start_y = data.get("startY")
    end_x = data.get("endX")
    end_y = data.get("endY")
    color = data.get("color", "black")
    size = data.get("size", 5)

    send_draw_event(room_id, start_x, start_y, end_x, end_y, color, size)
    print(
        f"[FLASK -> UDP] room={room_id}, player={player}, "
        f"start=({start_x},{start_y}), end=({end_x},{end_y}), "
        f"color={color}, size={size}"
    )

    return jsonify({
        "status": "ok",
        "message": "Draw event received by Flask and sent to UDP",
    })


@game_bp.route("/guess", methods=["POST"])
def guess():
    data = request.get_json(silent=True) or {}

    room_id = data.get("room_id")
    message = data.get("message")
    player = session.get("player_name", "anonymous")
    result = game_state.submit_guess(room_id, player, message, rooms.get(room_id, []))

    if result["accepted"]:
        try:
            db = DBClient(my_port=0)
            db.save_guess(
                user_id=_stable_db_id(player),
                game_id=_stable_db_id(room_id),
                guess=message,
                is_correct=result["correct"],
            )
        except Exception as e:
            print(f"[ERROR DB] No se pudo guardar el guess: {e}")

    if result["accepted"] and result["correct"]:
        event = game_state.add_chat_event(
            room_id,
            "system",
            "Sistema",
            f"{player} adivino la palabra",
            rooms.get(room_id, []),
        )
        send_chat_message(room_id, "Sistema", event["message"])
        print(
            f"[FLASK -> TCP] room={room_id}, player={player}, "
            f"correct=True, points={result['points']}"
        )
    elif result["accepted"]:
        event = game_state.add_chat_event(
            room_id,
            "chat",
            player,
            message,
            rooms.get(room_id, []),
        )
        send_chat_message(room_id, player, event["message"])
        print(f"[FLASK -> TCP] room={room_id}, player={player}, message={event['message']}")

    return jsonify({
        "status": "ok",
        "message": result["message"],
        "accepted": result["accepted"],
        "correct": result["correct"],
        "points": result["points"],
        "round_finished": result["round_finished"],
        "state": result["state"],
    })
