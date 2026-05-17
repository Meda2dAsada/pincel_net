import socket
import json
import hmac as hmac_lib
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding, types
from cryptography.hazmat.primitives import hashes, serialization
from enum import Enum

MY_HOST = "127.0.6.6"
MY_PORT = 3306

DB_HOST = "127.0.6.7"
DB_PORT = 3306

APP_KEY = b"Another day in paradise"

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((MY_HOST, MY_PORT))


class State(Enum):
    IDLE = "idle"
    SAVE_USER = "save_user"
    SAVE_ROOM = "save_room"
    SAVE_GUESS = "save_guess"


STATE = State.IDLE

enum_status_dict = {item.name: item.value for item in State}
string_status_dict = {item.value: item.name for item in State}

def get_enum(value):  return enum_status_dict[value]
def get_string(name): return string_status_dict[name]


DB_PK = None

# Generar par de claves RSA
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
public_key = private_key.public_key()


def encrypt(message: bytes, pk: types.PUBLIC_KEY_TYPES) -> str:
    """Cifra bytes con la clave pública dada. Retorna base64 string."""
    if isinstance(message, str):
        message = message.encode()
    ciphertext = pk.encrypt(
        message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(ciphertext).decode()


def decrypt(b64_ciphertext: str, lk=None) -> bytes:
    """Descifra un base64 string con la clave privada."""
    if lk is None:
        lk = private_key
    ciphertext = base64.b64decode(b64_ciphertext)
    plaintext = lk.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return plaintext


def make_hmac(address: str) -> str:
    """Genera un HMAC-SHA256 de la dirección con APP_KEY. Retorna hex string."""
    return hmac_lib.new(APP_KEY, address.encode(), hashlib.sha256).hexdigest()


def hmac_ok(address: str, received_hmac: str) -> bool:
    """Verifica que el HMAC recibido corresponde a la dirección."""
    expected = make_hmac(address)
    return hmac_lib.compare_digest(expected, received_hmac)


def mail(data: dict) -> int:
    """Envía un dict JSON al servidor DB. Retorna bytes enviados o -1 en error."""
    package = json.dumps(data)
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        size = udp_socket.sendto(package.encode("utf-8"), (DB_HOST, DB_PORT))
        udp_socket.close()
        return size
    except Exception as e:
        print("[UDP ERROR]", e)
        return -1


def public_key_to_pem(pk) -> str:
    """Serializa una clave pública a PEM string para enviarla por JSON."""
    return pk.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()


def public_key_from_pem(pem_str: str):
    """Deserializa una PEM string a objeto de clave pública."""
    return serialization.load_pem_public_key(pem_str.encode())


def encrypt_content(content: dict, key=None) -> dict:
    """Cifra todas las claves y valores del dict con la clave pública dada."""
    if key is None:
        key = DB_PK
    encrypted = {
        encrypt(k, key): encrypt(v, key)
        for k, v in zip(content.keys(), content.values())
    }
    return encrypted


def decrypt_content(content: dict, key=None) -> dict:
    """Descifra todas las claves y valores del dict con la clave privada."""
    if key is None:
        key = private_key
    decrypted = {
        decrypt(k, key).decode(): decrypt(v, key).decode()
        for k, v in zip(content.keys(), content.values())
    }
    return decrypted 


def empty_data(status=200) -> dict:
    return {
        "headers": {
            "ip":   MY_HOST,
            "hmac": make_hmac(MY_HOST),
        },
        "content": {},
        "status": status
    }


def decode_package(package: bytes) -> tuple:
    parsed = json.loads(package.decode("utf-8"))
    return parsed["headers"], parsed.get("content", {})


def unpack(package: bytes, address: tuple) -> dict:
    """Valida el paquete entrante y descifra su contenido."""
    headers, encrypted_content = decode_package(package)
    if hmac_ok(headers["ip"], headers["hmac"]):
        if encrypted_content:
            return {**decrypt_content(encrypted_content), "status": 200}
        return {"status": 200}

    print("[ERROR] Invalid credentials")
    return empty_data(400)


def exchange_pk():
    """Inicia el handshake enviando nuestra PK al servidor y recibiendo la suya."""
    global DB_PK 

    # El cliente inicia enviando su PK
    data = {
        "headers": {
            "ip":   MY_HOST,
            "hmac": make_hmac(MY_HOST),
        },
        "pk": public_key_to_pem(public_key)
    }
    mail(data)

    # Esperar la PK del servidor
    package, address = server.recvfrom(4096)
    parsed = json.loads(package.decode("utf-8"))
    headers = parsed["headers"]

    if not hmac_ok(headers["ip"], headers["hmac"]):
        print("[ERROR] Handshake HMAC inválido")
        return

    DB_PK = public_key_from_pem(parsed["pk"])
    print("[HANDSHAKE] Intercambio de claves completado")


def send(message: str, msg_state=STATE):
    data = {
        "headers": {
            "ip":    MY_HOST,
            "hmac":  make_hmac(MY_HOST),
            "state": get_string(msg_state),
        },
        "content": {"data": encrypt(message, DB_PK)}
    }
    mail(data)


def save_user(username: str):
    content = {
        "username":   username,
        "score":      "-1",
        "is_playing": "0",
        "room_id":    "-1",
    }
    data = {
        "headers": {
            "ip":    MY_HOST,
            "hmac":  make_hmac(MY_HOST),
            "state": State.SAVE_USER.value,
        },
        "content": encrypt_content(content)
    }
    mail(data)
    package, address = server.recvfrom(4096)
    response = unpack(package, address)
    if response.get("status") == 200:
        print("[LOG] User Saved")


def save_room(room_code, status):
    content = {
        "room_code": str(room_code),
        "status":    str(status),
    }
    data = {
        "headers": {
            "ip":    MY_HOST,
            "hmac":  make_hmac(MY_HOST),
            "state": State.SAVE_ROOM.value,
        },
        "content": encrypt_content(content)
    }
    mail(data)
    package, address = server.recvfrom(4096)
    response = unpack(package, address)
    if response.get("status") == 200:
        print("[LOG] Room Saved")


def save_guess(user_id, game_id, guess, is_correct):
    content = {
        "user_id":    str(user_id),
        "game_id":    str(game_id),
        "guess":      str(guess),
        "is_correct": str(is_correct),
    }
    data = {
        "headers": {
            "ip":    MY_HOST,
            "hmac":  make_hmac(MY_HOST),
            "state": State.SAVE_GUESS.value, 
        },
        "content": encrypt_content(content)
    }
    mail(data)
    package, address = server.recvfrom(4096)
    response = unpack(package, address)
    if response.get("status") == 200:
        print("[LOG] Guess Saved")

'''
if __name__ == "__main__":
    print(f"UDP client listening on {MY_HOST}:{MY_PORT}")

    exchange_pk()

    while True:
        package, address = server.recvfrom(4096)
        headers, content = decode_package(package)
        print(f"[UDP RECEIVED] From {address}")

        if address[0] == headers.get("ip") and address[0] == DB_HOST:
            STATE = State(headers.get("state", State.IDLE.value))
            match STATE:
                case State.IDLE:
                    break
                case State.SAVE_USER:
                    save_user(content.get("username", ""))
                case State.SAVE_ROOM:
                    save_room(content.get("room_code"), content.get("status"))
                case State.SAVE_GUESS:
                    save_guess(
                        content.get("user_id"),
                        content.get("game_id"),
                        content.get("guess"),
                        content.get("is_correct")
                    )
                case _:
                    break
'''

if __name__ == "__main__":
    print(f"UDP client listening on {MY_HOST}:{MY_PORT}")

    exchange_pk()

    # — Usuario de prueba —
    print("\n[TEST] Enviando usuario de prueba...")
    save_user("rodolfo_test")

    # — Sala de prueba —
    print("\n[TEST] Enviando sala de prueba...")
    save_room("SALA01", "waiting")

    # — Guess de prueba —
    # user_id=1 y game_id=1 asumen que el usuario y la sala
    # quedaron guardados con id=1 en la BD
    print("\n[TEST] Enviando guess de prueba...")
    save_guess(
        user_id=1,
        game_id=1,
        guess="perro",
        is_correct=False,
    )

    print("\n[TEST] Prueba completada.")