from flask import Blueprint, request, session, redirect, url_for, render_template

lobby_bp = Blueprint("lobby", __name__)

rooms = {}

@lobby_bp.route("/lobby", methods=["GET", "POST"])
def lobby():

    if request.method == "POST":

        player_name = request.form.get("player_name")
        room_id = request.form.get("room_id")

        session["player_name"] = player_name

        if room_id not in rooms:
            rooms[room_id] = []

        rooms[room_id].append(player_name)

        session["room_id"] = room_id

        return redirect(url_for("game.game", room_id=room_id))

    return render_template("lobby.html")