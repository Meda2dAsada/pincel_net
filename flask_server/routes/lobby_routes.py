from flask import Blueprint, request, session, redirect, url_for, render_template
from db_client import DBClient

lobby_bp = Blueprint("lobby", __name__)

rooms = {}

@lobby_bp.route("/lobby", methods=["GET", "POST"])
def lobby():
    if request.method == "POST":

        player_name = request.form.get("player_name")
        room_id = request.form.get("room_id")
        status = "waiting"

        session["player_name"] = player_name
        session["room_id"] = room_id

        if room_id not in rooms:
            rooms[room_id] = []

        rooms[room_id].append(player_name)

        # --- INTEGRACIÓN CON BD ---
        try:
            db = DBClient(my_port=0)

            # 1. Guarda la sala (si ya existe, el servidor automáticamente la actualiza)
            db.save_room(room_code=room_id, status=status)
            
            # 2. Guarda el usuario (si ya existe, el servidor lo ignora)
            db.save_user(username=player_name)
            
            # 3. Actualiza el estado del usuario para vincularlo a la sala
            db.update_user(username=player_name, is_playing="1", room_id=room_id)
            
        except Exception as e:
            print(f"[ERROR DB] No se pudo guardar info de lobby: {e}")

        return redirect(url_for("game.game", room_id=room_id))

    return render_template("lobby.html")