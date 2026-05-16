from flask import Flask

from routes.lobby_routes import lobby_bp
from routes.game_routes import game_bp

app = Flask(__name__)

app.secret_key = "pincelnet_secret"

app.register_blueprint(lobby_bp)
app.register_blueprint(game_bp)

@app.route("/")
def home():
    return """
    <h1>PincelNet</h1>

    <a href='/lobby'>Ir al Lobby</a>
    """

if __name__ == "__main__":
    app.run(debug=True)