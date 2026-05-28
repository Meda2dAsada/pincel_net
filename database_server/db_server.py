import traceback
import socket
import json
import hmac as hmac_lib
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding, types
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

import base64
import hashlib


from enum import Enum

from database import get_session
from models.user import User
from models.room import Room
from models.guess import Guess

MY_HOST = "127.0.0.1"
MY_PORT = 5003

CLIENT_HOST = "127.0.0.1"
CLIENT_PORT = 15000
CLIENT_ADRESS = None

UDP_HOST = "127.0.0.1"
UDP_PORT = 5002

APP_KEY = b"Another day in paradise"

# ──────────────────────────────────────────────
# Criptografía para Base de Datos (AES-128-CBC)
# ──────────────────────────────────────────────
# Derivamos la llave (16 bytes) y el IV (16 bytes) de la APP_KEY
DB_AES_KEY = hashlib.sha256(APP_KEY).digest()[:16]  # Primeros 16 bytes del hash SHA-256
DB_AES_IV  = hashlib.md5(APP_KEY).digest()          # 16 bytes del hash MD5

def db_encrypt(data) -> str:
    """Encripta un string usando AES-128-CBC y retorna Base64."""
    if not data:
        return data

    if not isinstance(data, (str, bytes)):
        data = str(data)

    if isinstance(data, str):
        data = data.encode('utf-8')

    cipher = Cipher(algorithms.AES128(DB_AES_KEY), modes.CBC(DB_AES_IV), backend=default_backend())
    encryptor = cipher.encryptor()

    padder = sym_padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()

    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode('utf-8')


def db_decrypt(b64_data: str) -> str:
    """Desencripta un string en Base64 usando AES-128-CBC."""
    if not b64_data: 
        return b64_data
    try:
        ciphertext = base64.b64decode(b64_data)
        cipher = Cipher(algorithms.AES128(DB_AES_KEY), modes.CBC(DB_AES_IV), backend=default_backend())
        decryptor = cipher.decryptor()
        
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        # CORRECCIÓN AQUÍ: sym_padding en lugar de padding
        unpadder = sym_padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data.decode('utf-8')
    except ValueError:
        # Si falla el padding (significa que el dato NO estaba encriptado en la BD)
        return b64_data
    except Exception:
        # Cualquier otro error, devolvemos el dato original en lugar de crashear
        return b64_data


server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((MY_HOST, MY_PORT))


class State(Enum):
    IDLE       = "idle"
    SAVE_USER  = "save_user"
    SAVE_ROOM  = "save_room"
    SAVE_GUESS = "save_guess"
    UPDATE_USER = "update_user" 
    UPDATE_ROOM = "update_room"
    GET_ROOMS   = "get_rooms"
    GET_USERS   = "get_users"


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
        if CLIENT_ADRESS is not None:
            size = udp_socket.sendto(package.encode("utf-8"), CLIENT_ADRESS)
        else:
            size = udp_socket.sendto(package.encode("utf-8"), (CLIENT_HOST, CLIENT_PORT))
        udp_socket.close()
        return size
    except Exception as e:
        print("[UDP ERROR]", e)
        return -1
    

def mail_to_udp(data: dict, HOST, PORT) -> int:
    package = json.dumps(data)
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        size = udp_socket.sendto(package.encode("utf-8"), (HOST, PORT))
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
    session = get_session()
    try:
        username = content.get("username", "").strip()
        if not username:
            mail(empty_data(400))
            return

        enc_username = db_encrypt(username) # <-- ENCRIPTAR ANTES DE BUSCAR/GUARDAR

        existing = User.find_by_username(session, enc_username)
        if existing:
            mail(empty_data(200))
            return

        # Absolutamente todo encriptado
        enc_score = db_encrypt("-1")
        enc_is_playing = db_encrypt("0")
        enc_room_id = db_encrypt("-1")

        user = User.create(session, username=enc_username, score=enc_score, is_playing=enc_is_playing, room_id=enc_room_id)
        mail(empty_data(200))

    except Exception as e:
        session.rollback()
        mail(empty_data(500))
    finally:
        session.close()


def save_room(content: dict):
    session = get_session()
    try:
        room_code = str(content.get("room_code", "")).strip()
        
        # Leemos el status, pero si es "200" (código de red), lo forzamos a "waiting"
        status = str(content.get("status", "waiting")).strip()
        if status == "200":
            status = "waiting"

        enc_room_code = db_encrypt(room_code)
        enc_status = db_encrypt(status)

        existing = Room.find_by_code(session, enc_room_code)
        if existing:
            existing.status = enc_status
            existing.save(session)
        else:
            Room.create(session, room_code=enc_room_code, status=enc_status)

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

        enc_user_id = db_encrypt(str(user_id))
        enc_game_id = db_encrypt(str(game_id))
        enc_guess = db_encrypt(guess)
        enc_is_correct = db_encrypt(is_correct)
        
        if user_id < 0 or game_id < 0 or not guess:
            print("[DB] Error: datos de guess incompletos")
            mail(empty_data(400))
            return

        record = Guess.create(
            session,
            user_id=enc_user_id,
            game_id=enc_game_id,
            guess=enc_guess,
            is_correct=enc_is_correct,
        )
        
        print(f"[DB] Guess Saved — {record}")
        mail(empty_data(200))

    except Exception as e:
        print(f"[DB ERROR] save_guess: {e}")
        session.rollback()
        mail(empty_data(500))
    finally:
        session.close()


def update_user(content: dict):
    session = get_session()
    try:
        username = content.get("username", "").strip()
        score = content.get("score")
        is_playing = content.get("is_playing")
        room_id = content.get("room_id")

        enc_username = db_encrypt(username)
        existing = User.find_by_username(session, enc_username)
        
        if not existing:
            mail(empty_data(404)) # Not found
            return

        # Actualizar sólo lo que se envió en el content
        if score is not None:
            existing.score = db_encrypt(str(score))
        if is_playing is not None:
            existing.is_playing = db_encrypt(str(is_playing))
        if room_id is not None:
            existing.room_id = db_encrypt(str(room_id))

        existing.save(session)
        mail(empty_data(200))

    except Exception as e:
        session.rollback()
        mail(empty_data(500))
    finally:
        session.close()

def update_room(content: dict):
    session = get_session()
    try:
        room_code = str(content.get("room_code", "")).strip()
        status = content.get("status")

        enc_room_code = db_encrypt(room_code)
        existing = Room.find_by_code(session, enc_room_code)

        if not existing:
            mail(empty_data(404))
            return

        if status is not None:
            existing.status = db_encrypt(str(status))

        existing.save(session)
        mail(empty_data(200))

    except Exception as e:
        session.rollback()
        mail(empty_data(500))
    finally:
        session.close()

def get_rooms(address: tuple):
    # Usamos la variable global para asegurarnos de que la respuesta regrese al cliente correcto
    global CLIENT_ADRESS
    
    session = get_session()
    try:
        rooms = session.query(Room).all()
        active_rooms = []
        
        print(f"\n[DEBUG] --- ANALIZANDO SALAS EN LA BD ---")
        for r in rooms:
            try:
                # 1. Desencriptamos
                dec_code = db_decrypt(r.room_code)
                dec_status = db_decrypt(r.status)
                
                # 2. Imprimimos exactamente qué está leyendo el servidor
                print(f" -> Sala BD cruda: {r.room_code[:10]}... | Status crudo: {r.status[:10]}...")
                print(f" -> Sala desencriptada: '{dec_code}' | Status desencriptado: '{dec_status}'")
                
                # 3. Limpiamos el texto (quitamos espacios extra y pasamos a minúsculas)
                clean_status = str(dec_status).strip().lower()

                if clean_status in ["waiting", "playing", "activo", "200"]:
                    active_rooms.append(dec_code)
                else:
                    print(f"    [!] El status '{clean_status}' no es válido para mostrar en el lobby.")
                    
            except Exception as e:
                print(f" [ERROR LEYENDO SALA] {e}")
                continue
        
        print(f"[DEBUG] ---------------------------------")
        print(f"[DB] Enviando {len(active_rooms)} salas activas al lobby {CLIENT_ADRESS}")
        
        response = {
            "headers": {"ip": MY_HOST, "hmac": make_hmac(MY_HOST), "state": "ROOMS_LIST"},
            "rooms": active_rooms,
            "status": 200
        }
        
        # Enviar respuesta al cliente (usamos CLIENT_ADRESS en vez de 'address' por si acaso)
        server.sendto(json.dumps(response).encode("utf-8"), CLIENT_ADRESS)
        
    except Exception as e:
        print(f"[DB ERROR] get_rooms: {e}")
    finally:
        session.close()

def get_users(content: dict):
    # Usamos la variable global para responder al cliente correcto
    global CLIENT_ADRESS
    
    session = get_session()
    try:
        room_id = str(content.get("room_id", "")).strip()
        enc_room_id = db_encrypt(room_id)

        # Buscamos los usuarios vinculados a esa sala en la BD
        users = session.query(User).filter(User.room_id == enc_room_id).all()
        active_users = []

        for u in users:
            try:
                # Desencriptamos el nombre para que Flask pueda procesarlo
                dec_user = db_decrypt(u.username)
                active_users.append(dec_user)
            except:
                continue

        response = {
            "headers": {"ip": MY_HOST, "hmac": make_hmac(MY_HOST), "state": "USERS_LIST"},
            "users": active_users,
            "status": 200
        }
        server.sendto(json.dumps(response).encode("utf-8"), CLIENT_ADRESS)
        
    except Exception as e:
        print(f"[DB ERROR] get_users: {e}")
    finally:
        session.close()

# ──────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print(f"UDP server listening on {MY_HOST}:{MY_PORT}")

    while True:
        try:
            package, address = server.recvfrom(4096)
            
            # 1. Actualizamos la variable global (como tú lo querías)
            
            CLIENT_ADRESS = address

            # 2. Interceptamos el Handshake ANTES de intentar desencriptar
            parsed = json.loads(package.decode("utf-8"))
            if "pk" in parsed:
                print(f"[DEBUG] 🤝 Handshake de {CLIENT_ADRESS}. Respondiendo...")
            
                CLIENT_PK = public_key_from_pem(parsed["pk"])
                
                data = {
                    "headers": {"ip": MY_HOST, "hmac": make_hmac(MY_HOST)},
                    "pk": public_key_to_pem(public_key),
                }
                mail(data) # Le responde a Flask usando la variable global
                continue   # Saltamos el resto y volvemos a esperar la petición real

            # 3. Si no es Handshake, procesamos normal
            content = unpack(package, CLIENT_ADRESS)
            headers, _ = decode_package(package)

            if str(content.get("status")) == "200":
                STATE_VAL = headers.get("state", "idle")
                
                STATE = State(STATE_VAL)
                match STATE:
                    case State.IDLE: pass
                    case State.SAVE_USER: save_user(content)
                    case State.UPDATE_USER: update_user(content)
                    case State.SAVE_ROOM: save_room(content)
                    case State.UPDATE_ROOM: update_room(content)
                    case State.GET_ROOMS: get_rooms(CLIENT_ADRESS)         
                    case State.GET_USERS: get_users(content)
                    case _:
                        print(f"[WARNING] Estado no reconocido: {STATE_VAL}")

        except Exception as e:
            print(f"\n [ERROR FATAL EN BUCLE] No se pudo procesar el paquete.")
            traceback.print_exc()