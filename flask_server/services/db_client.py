import socket
import json
import hmac as hmac_lib
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding, types
from cryptography.hazmat.primitives import hashes, serialization
from enum import Enum

APP_KEY = b"Another day in paradise"

def make_hmac(address: str) -> str:
    return hmac_lib.new(APP_KEY, address.encode(), hashlib.sha256).hexdigest()

class State(Enum):
    IDLE = "idle"
    SAVE_USER = "save_user"
    SAVE_ROOM = "save_room"
    SAVE_GUESS = "save_guess"
    UPDATE_USER = "update_user"
    UPDATE_ROOM = "update_room"
    GET_USERS = "get_users"


class DBClient:
    def __init__(self, my_host="127.0.0.1", my_port=5002, db_host="127.0.0.1", db_port=5003, app_key=b"Another day in paradise"):
        self.my_host = my_host
        self.my_port = my_port
        self.db_host = db_host
        self.db_port = db_port
        self.app_key = app_key

        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.bind((self.my_host, self.my_port))

        self.state = State.IDLE

        # Generar par de claves RSA para esta instancia
        self.__private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.__public_key = self.__private_key.public_key()
        
        # Atributo privado para guardar la clave del servidor
        self.__db_pk = None

        print(f"UDP client listening on {self.my_host}:{self.my_port}")
        # Realizamos el handshake automáticamente al instanciar
        self._exchange_pk()

    # ──────────────────────────────────────────────
    # Helpers y Criptografía
    # ──────────────────────────────────────────────

    def _get_string(self, state_enum): 
        return state_enum.value

    def _encrypt(self, message: bytes, pk: types.PUBLIC_KEY_TYPES) -> str:
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

    def _decrypt(self, b64_ciphertext: str, lk=None) -> bytes:
        if lk is None:
            lk = self.__private_key
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

    def _make_hmac(self, address: str) -> str:
        return hmac_lib.new(self.app_key, address.encode(), hashlib.sha256).hexdigest()

    def _hmac_ok(self, address: str, received_hmac: str) -> bool:
        expected = self._make_hmac(address)
        return hmac_lib.compare_digest(expected, received_hmac)

    def _public_key_to_pem(self, pk) -> str:
        return pk.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def _public_key_from_pem(self, pem_str: str):
        return serialization.load_pem_public_key(pem_str.encode())

    def _encrypt_content(self, content: dict, key=None) -> dict:
        if key is None:
            key = self.__db_pk
        encrypted = {
            self._encrypt(k, key): self._encrypt(v, key)
            for k, v in zip(content.keys(), content.values())
        }
        return encrypted

    def _decrypt_content(self, content: dict, key=None) -> dict:
        if key is None:
            key = self.__private_key
        decrypted = {
            self._decrypt(k, key).decode(): self._decrypt(v, key).decode()
            for k, v in zip(content.keys(), content.values())
        }
        return decrypted 

    def _empty_data(self, status=200) -> dict:
        return {
            "headers": {
                "ip":   self.my_host,
                "hmac": self._make_hmac(self.my_host),
            },
            "content": {},
            "status": status
        }

    # ──────────────────────────────────────────────
    # Red
    # ──────────────────────────────────────────────

    def _mail(self, data: dict) -> int:
        package = json.dumps(data)
        try:
            # ❌ ELIMINA O COMENTA ESTAS LÍNEAS QUE CREAN UN SOCKET TEMPORAL:
            # udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # size = udp_socket.sendto(package.encode("utf-8"), (self.db_host, self.db_port))
            # udp_socket.close()

            #  SOLUCIÓN: Usar el socket persistente de la clase (self.server)
            size = self.server.sendto(package.encode("utf-8"), (self.db_host, self.db_port))
            return size
        except Exception as e:
            print("[UDP ERROR]", e)
            return -1

    def _decode_package(self, package: bytes) -> tuple:
        parsed = json.loads(package.decode("utf-8"))
        return parsed["headers"], parsed.get("content", {})

    def _unpack(self, package: bytes, address: tuple) -> dict:
        headers, encrypted_content = self._decode_package(package)
        if self._hmac_ok(headers["ip"], headers["hmac"]):
            if encrypted_content:
                return {**self._decrypt_content(encrypted_content), "status": 200}
            return {"status": 200}

        print("[ERROR] Invalid credentials")
        return self._empty_data(400)

    def _exchange_pk(self):
        data = {
            "headers": {
                "ip":   self.my_host,
                "hmac": self._make_hmac(self.my_host),
            },
            "pk": self._public_key_to_pem(self.__public_key)
        }
        self._mail(data)

        package, address = self.server.recvfrom(4096)
        parsed = json.loads(package.decode("utf-8"))
        headers = parsed["headers"]

        if not self._hmac_ok(headers["ip"], headers["hmac"]):
            print("[ERROR] Handshake HMAC inválido")
            return

        self.__db_pk = self._public_key_from_pem(parsed["pk"])
        print("[HANDSHAKE] Intercambio de claves completado")

    # ──────────────────────────────────────────────
    # Métodos Públicos de BD
    # ──────────────────────────────────────────────

    def send(self, message: str, msg_state=None):
        if msg_state is None:
            msg_state = self.state
        data = {
            "headers": {
                "ip":    self.my_host,
                "hmac":  self._make_hmac(self.my_host),
                "state": self._get_string(msg_state),
            },
            "content": {"data": self._encrypt(message, self.__db_pk)}
        }
        self._mail(data)

    def save_user(self, username: str):
        content = {
            "username":   username,
            "score":      "-1",
            "is_playing": "0",
            "room_id":    "-1",
        }
        data = {
            "headers": {
                "ip":    self.my_host,
                "hmac":  self._make_hmac(self.my_host),
                "state": State.SAVE_USER.value,
            },
            "content": self._encrypt_content(content)
        }
        self._mail(data)
        package, address = self.server.recvfrom(4096)
        response = self._unpack(package, address)
        if response.get("status") == 200:
            print("[LOG] User Saved")

    def save_room(self, room_code, status):
        content = {
            "room_code": str(room_code),
            "status":    str(status),
        }
        data = {
            "headers": {
                "ip":    self.my_host,
                "hmac":  self._make_hmac(self.my_host),
                "state": State.SAVE_ROOM.value,
            },
            "content": self._encrypt_content(content)
        }
        self._mail(data)
        package, address = self.server.recvfrom(4096)
        response = self._unpack(package, address)
        if response.get("status") == 200:
            print("[LOG] Room Saved")

    def save_guess(self, user_id, game_id, guess, is_correct):
        content = {
            "user_id":    str(user_id),
            "game_id":    str(game_id),
            "guess":      str(guess),
            "is_correct": str(is_correct),
        }
        data = {
            "headers": {
                "ip":    self.my_host,
                "hmac":  self._make_hmac(self.my_host),
                "state": State.SAVE_GUESS.value, 
            },
            "content": self._encrypt_content(content)
        }
        self._mail(data)
        package, address = self.server.recvfrom(4096)
        response = self._unpack(package, address)
        if response.get("status") == 200:
            print("[LOG] Guess Saved")

    def update_user(self, username: str, score: str = None, is_playing: str = None, room_id: str = None):
        content = {"username": username}
        
        if score is not None: content["score"] = str(score)
        if is_playing is not None: content["is_playing"] = str(is_playing)
        if room_id is not None: content["room_id"] = str(room_id)

        data = {
            "headers": {
                "ip":    self.my_host,
                "hmac":  self._make_hmac(self.my_host),
                "state": State.UPDATE_USER.value,
            },
            "content": self._encrypt_content(content)
        }
        self._mail(data)
        package, address = self.server.recvfrom(4096)
        response = self._unpack(package, address)
        if response.get("status") == 200:
            print(f"[LOG] User '{username}' Updated")
        else:
            print(f"[ERROR] Could not update user '{username}'")

    def update_room(self, room_code: str, status: str):
        content = {
            "room_code": str(room_code),
            "status":    str(status),
        }
        data = {
            "headers": {
                "ip":    self.my_host,
                "hmac":  self._make_hmac(self.my_host),
                "state": State.UPDATE_ROOM.value,
            },
            "content": self._encrypt_content(content)
        }
        self._mail(data)
        package, address = self.server.recvfrom(4096)
        response = self._unpack(package, address)
        if response.get("status") == 200:
            print(f"[LOG] Room '{room_code}' Updated")
        else:
            print(f"[ERROR] Could not update room '{room_code}'")
    
    def get_rooms(self):
        # 1. Contenido base a enviar
        content = {"status": "200"}
        
        # 2. Empaquetamos usando la misma estructura que save_room y save_user
        data = {
            "headers": {
                "ip":    self.my_host,
                "hmac":  self._make_hmac(self.my_host),
                "state": "get_rooms",
            },
            "content": self._encrypt_content(content)
        }
        
        # 3. Enviamos el paquete usando el método interno que ya maneja tu socket (self.server)
        self._mail(data)
        
        # 4. Escuchamos la respuesta de vuelta
        try:
            self.server.settimeout(2.0)
            package, address = self.server.recvfrom(4096)
            self.server.settimeout(None)  # Restauramos el socket a su estado normal
            
            # Como programamos db_server.py para que devuelva la lista en texto plano,
            # lo leemos directamente en lugar de usar _unpack()
            respuesta = json.loads(package.decode("utf-8"))
            
            if "rooms" in respuesta:
                return respuesta["rooms"]
            return []
            
        except socket.timeout:
            print("[ERROR DB] Timeout esperando la lista de salas desde el servidor.")
            return []
        except Exception as e:
            print(f"[ERROR DB] Error al recibir/procesar las salas: {e}")
            return []

    def get_users_in_room(self, room_id):
        # 1. Contenido con el ID de la sala para filtrar en el servidor
        content = {"room_id": str(room_id)}
        
        # 2. Empaquetamos la petición cifrada
        data = {
            "headers": {
                "ip":    self.my_host,
                "hmac":  self._make_hmac(self.my_host),
                "state": State.GET_USERS.value,
            },
            "content": self._encrypt_content(content)
        }
        
        self._mail(data)
        
        try:
            self.server.settimeout(2.0)
            package, address = self.server.recvfrom(4096)
            self.server.settimeout(None)
            
            respuesta = json.loads(package.decode("utf-8"))
            return respuesta.get("users", [])
            
        except Exception as e:
            print(f"[ERROR DB] Error al obtener usuarios de la sala: {e}")
            return []
