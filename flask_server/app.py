from flask import Flask, redirect, url_for

from routes.lobby_routes import lobby_bp
from routes.game_routes import game_bp

app = Flask(__name__)

app.secret_key = "pincelnet_secret"

app.register_blueprint(lobby_bp)
app.register_blueprint(game_bp)

@app.route("/")
def home():
    try:
        return redirect(url_for('lobby_bp.lobby'))
    except:
        return redirect("/lobby")

if __name__ == "__main__":
    app.run(debug=True)