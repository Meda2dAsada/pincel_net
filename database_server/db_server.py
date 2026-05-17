import socket
import json
import hmac as hmac_lib
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding, types
from cryptography.hazmat.primitives import hashes, serialization
from enum import Enum

from database import get_session
from models.user import User
from models.room import Room
from models.guess import Guess

MY_HOST = "127.0.6.7"
MY_PORT = 3306

CLIENT_HOST = "127.0.6.6"
CLIENT_PORT = 3306

APP_KEY = b"Another day in paradise"

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((MY_HOST, MY_PORT))


class State(Enum):
    IDLE      = "idle"
    SAVE_USER = "save_user"
    SAVE_ROOM = "save_room"
    SAVE_GUESS = "save_guess"


STATE = State.IDLE

enum_status_dict  = {item.name: item.value for item in State}
string_status_dict = {item.value: item.name for item in State}

def get_enum(value):  return enum_status_dict[value]
def get_string(name): return string_status_dict[name]


CLIENT_PK = None

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key  = private_key.public_key()


# ──────────────────────────────────────────────
# Criptografía
# ──────────────────────────────────────────────

def encrypt(message, pk: types.PUBLIC_KEY_TYPES) -> str:
    if isinstance(message, str):
        message = message.encode()
    ciphertext = pk.encrypt(
        message,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None)
    )
    return base64.b64encode(ciphertext).decode()


def decrypt(b64_ciphertext: str, lk=None) -> bytes:
    if lk is None:
        lk = private_key
    ciphertext = base64.b64decode(b64_ciphertext)
    return lk.decrypt(
        ciphertext,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None)
    )


def make_hmac(address: str) -> str:
    return hmac_lib.new(APP_KEY, address.encode(), hashlib.sha256).hexdigest()


def hmac_ok(address: str, received_hmac: str) -> bool:
    return hmac_lib.compare_digest(make_hmac(address), received_hmac)


def public_key_to_pem(pk) -> str:
    return pk.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


def public_key_from_pem(pem_str: str):
    return serialization.load_pem_public_key(pem_str.encode())


def encrypt_content(content: dict, key) -> dict:
    return {encrypt(k, key): encrypt(v, key) for k, v in content.items()}


def decrypt_content(content: dict, key=None) -> dict:
    if key is None:
        key = private_key
    return {decrypt(k, key).decode(): decrypt(v, key).decode() for k, v in content.items()}


# ──────────────────────────────────────────────
# Red
# ──────────────────────────────────────────────

def mail(data: dict) -> int:
    package = json.dumps(data)
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        size = udp_socket.sendto(package.encode("utf-8"), (CLIENT_HOST, CLIENT_PORT))
        udp_socket.close()
        return size
    except Exception as e:
        print("[UDP ERROR]", e)
        return -1


def empty_data(status: int = 400) -> dict:
    return {
        "headers": {"ip": MY_HOST, "hmac": make_hmac(MY_HOST)},
        "content": {},
        "status":  status,
    }


def decode_package(package: bytes) -> tuple:
    parsed = json.loads(package.decode("utf-8"))
    return parsed["headers"], parsed.get("content", {})


def unpack(package: bytes, address: tuple) -> dict:
    headers, encrypted_content = decode_package(package)
    if hmac_ok(headers["ip"], headers["hmac"]):
        if encrypted_content:
            return {**decrypt_content(encrypted_content), "status": 200}
        return {"status": 200}
    print("[ERROR] Invalid credentials")
    return empty_data(400)


def exchange_pk():
    global CLIENT_PK
    package, address = server.recvfrom(4096)
    parsed  = json.loads(package.decode("utf-8"))
    headers = parsed["headers"]

    if not hmac_ok(headers["ip"], headers["hmac"]):
        print("[ERROR] Handshake HMAC inválido")
        return

    CLIENT_PK = public_key_from_pem(parsed["pk"])
    data = {
        "headers": {"ip": MY_HOST, "hmac": make_hmac(MY_HOST)},
        "pk": public_key_to_pem(public_key),
    }
    mail(data)
    print("[HANDSHAKE] Intercambio de claves completado")


# ──────────────────────────────────────────────
# Handlers con modelos SQLAlchemy
# ──────────────────────────────────────────────

def save_user(content: dict):
    """
    Espera en content:
        username, score, is_playing, room_id
    """
    session = get_session()
    try:
        username = content.get("username", "").strip()
        if not username:
            print("[DB] Error: username vacío")
            mail(empty_data(400))
            return

        # Evitar duplicados
        existing = User.find_by_username(session, username)
        if existing:
            print(f"[DB] Usuario '{username}' ya existe — id={existing.id}")
            mail(empty_data(200))
            return

        user = User.create(session, username=username)
        print(f"[DB] User Saved — {user}")
        mail(empty_data(200))

    except Exception as e:
        print(f"[DB ERROR] save_user: {e}")
        session.rollback()
        mail(empty_data(500))
    finally:
        session.close()


def save_room(content: dict):
    """
    Espera en content:
        room_code, status
    """
    session = get_session()
    try:
        room_code = str(content.get("room_code", "")).strip()
        status    = str(content.get("status", "waiting")).strip()

        if not room_code:
            print("[DB] Error: room_code vacío")
            mail(empty_data(400))
            return

        existing = Room.find_by_code(session, room_code)
        if existing:
            # Actualizar estado si ya existe
            existing.status = status
            existing.save(session)
            print(f"[DB] Room Updated — {existing}")
        else:
            room = Room.create(session, room_code=room_code, status=status)
            print(f"[DB] Room Saved — {room}")

        mail(empty_data(200))

    except Exception as e:
        print(f"[DB ERROR] save_room: {e}")
        session.rollback()
        mail(empty_data(500))
    finally:
        session.close()


def save_guess(content: dict):
    """
    Espera en content:
        user_id, game_id, guess, is_correct
    """
    session = get_session()
    try:
        user_id    = int(content.get("user_id", -1))
        game_id    = int(content.get("game_id", -1))
        guess      = content.get("guess", "").strip()
        is_correct = content.get("is_correct", "false").lower() in ("true", "1", "yes")

        if user_id < 0 or game_id < 0 or not guess:
            print("[DB] Error: datos de guess incompletos")
            mail(empty_data(400))
            return

        record = Guess.create(
            session,
            user_id=user_id,
            game_id=game_id,
            guess=guess,
            is_correct=is_correct,
        )
        print(f"[DB] Guess Saved — {record}")
        mail(empty_data(200))

    except Exception as e:
        print(f"[DB ERROR] save_guess: {e}")
        session.rollback()
        mail(empty_data(500))
    finally:
        session.close()


# ──────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print(f"UDP server listening on {MY_HOST}:{MY_PORT}")

    exchange_pk()

    while True:
        package, address = server.recvfrom(4096)
        print(f"[UDP RECEIVED] From {address}")

        content = unpack(package, address)
        headers, _ = decode_package(package)

        if content.get("status") == 200:
            STATE = State(headers.get("state", State.IDLE.value))
            match STATE:
                case State.IDLE:
                    break
                case State.SAVE_USER:
                    save_user(content)
                case State.SAVE_ROOM:
                    save_room(content)
                case State.SAVE_GUESS:
                    save_guess(content)
                case _:
                    break