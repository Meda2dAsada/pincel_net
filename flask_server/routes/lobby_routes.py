from flask import Blueprint, request, session, redirect, url_for, render_template
from services.db_client import DBClient

lobby_bp = Blueprint("lobby", __name__)

@lobby_bp.route("/lobby", methods=["GET", "POST"])
def lobby():
    # ==========================================
    # 1. CUANDO EL USUARIO ENVÍA EL FORMULARIO
    # ==========================================
    if request.method == "POST":
        player_name = request.form.get("player_name")
        room_id = request.form.get("room_id")
        status = "waiting"

        session["player_name"] = player_name
        session["room_id"] = room_id

        # --- INTEGRACIÓN CON BD ---
        try:
            db = DBClient() # my_port=0 asigna un puerto libre aleatorio

            # Guarda la sala, el usuario y lo vincula
            db.save_room(room_code=room_id, status=status)
            db.save_user(username=player_name)
            db.update_user(username=player_name, is_playing="1", room_id=room_id)
            
        except Exception as e:
            print(f"[ERROR DB] No se pudo guardar info de lobby: {e}")

        return redirect(url_for("game_bp.game", room_id=room_id))

    # ==========================================
    # 2. CUANDO EL USUARIO CARGA LA PÁGINA (GET)
    # ==========================================
    active_rooms = []
    
    try:
        db = DBClient()
        
        # Llamamos al método que pide las salas al servidor UDP (db_server.py)
        respuesta = db.get_rooms() 
        
        # Como db_server.py suele devolver un JSON/diccionario con la llave "rooms":
        if isinstance(respuesta, dict) and "rooms" in respuesta:
            active_rooms = respuesta["rooms"]
        elif isinstance(respuesta, list):
            active_rooms = respuesta # Por si tu DBClient ya extrae la lista

    except Exception as e:
        print(f"[ERROR DB] No se pudieron obtener las salas: {e}")

    # Es VITAL pasar la variable 'rooms' al render_template para que Jinja2 la detecte
    return render_template("lobby.html", rooms=active_rooms)