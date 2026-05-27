import base64
import hashlib
import hmac as hmac_lib
import json
import socket
from enum import Enum

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, types


class State(Enum):
    IDLE = "idle"
    SAVE_USER = "save_user"
    SAVE_ROOM = "save_room"
    SAVE_GUESS = "save_guess"
    UPDATE_USER = "update_user"
    UPDATE_ROOM = "update_room"


class DBClient:
    def __init__(
        self,
        my_host="127.0.6.6",
        my_port=3306,
        db_host="127.0.6.7",
        db_port=3306,
        app_key=b"Another day in paradise",
        timeout=2.0,
    ):
        self.my_host = my_host
        self.my_port = my_port
        self.db_host = db_host
        self.db_port = db_port
        self.app_key = app_key
        self.timeout = timeout

        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.bind((self.my_host, self.my_port))
        self.server.settimeout(self.timeout)

        self.__private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.__public_key = self.__private_key.public_key()
        self.__db_pk = None

        self._exchange_pk()

    def _encrypt(self, message: bytes, pk: types.PUBLIC_KEY_TYPES) -> str:
        if isinstance(message, str):
            message = message.encode()
        ciphertext = pk.encrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(ciphertext).decode()

    def _decrypt(self, b64_ciphertext: str, lk=None) -> bytes:
        if lk is None:
            lk = self.__private_key
        ciphertext = base64.b64decode(b64_ciphertext)
        return lk.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

    def _make_hmac(self, address: str) -> str:
        return hmac_lib.new(self.app_key, address.encode(), hashlib.sha256).hexdigest()

    def _hmac_ok(self, address: str, received_hmac: str) -> bool:
        expected = self._make_hmac(address)
        return hmac_lib.compare_digest(expected, received_hmac)

    def _public_key_to_pem(self, pk) -> str:
        return pk.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def _public_key_from_pem(self, pem_str: str):
        return serialization.load_pem_public_key(pem_str.encode())

    def _encrypt_content(self, content: dict, key=None) -> dict:
        if key is None:
            key = self.__db_pk
        return {
            self._encrypt(key_name, key): self._encrypt(value, key)
            for key_name, value in content.items()
        }

    def _decrypt_content(self, content: dict, key=None) -> dict:
        if key is None:
            key = self.__private_key
        return {
            self._decrypt(key_name, key).decode(): self._decrypt(value, key).decode()
            for key_name, value in content.items()
        }

    def _mail(self, data: dict) -> int:
        package = json.dumps(data)
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            size = udp_socket.sendto(package.encode("utf-8"), (self.db_host, self.db_port))
            udp_socket.close()
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
        return {"status": 400}

    def _exchange_pk(self):
        data = {
            "headers": {
                "ip": self.my_host,
                "hmac": self._make_hmac(self.my_host),
            },
            "pk": self._public_key_to_pem(self.__public_key),
        }
        self._mail(data)

        package, address = self.server.recvfrom(4096)
        parsed = json.loads(package.decode("utf-8"))
        headers = parsed["headers"]

        if not self._hmac_ok(headers["ip"], headers["hmac"]):
            print("[ERROR] Handshake HMAC invalido")
            return

        self.__db_pk = self._public_key_from_pem(parsed["pk"])

    def _send_content(self, state, content):
        data = {
            "headers": {
                "ip": self.my_host,
                "hmac": self._make_hmac(self.my_host),
                "state": state.value,
            },
            "content": self._encrypt_content(content),
        }
        self._mail(data)
        package, address = self.server.recvfrom(4096)
        return self._unpack(package, address)

    def save_user(self, username: str):
        content = {
            "username": username,
            "score": "-1",
            "is_playing": "0",
            "room_id": "-1",
        }
        return self._send_content(State.SAVE_USER, content)

    def save_room(self, room_code, status):
        content = {
            "room_code": str(room_code),
            "status": str(status),
        }
        return self._send_content(State.SAVE_ROOM, content)

    def save_guess(self, user_id, game_id, guess, is_correct):
        content = {
            "user_id": str(user_id),
            "game_id": str(game_id),
            "guess": str(guess),
            "is_correct": str(is_correct),
        }
        return self._send_content(State.SAVE_GUESS, content)

    def update_user(self, username: str, score: str = None, is_playing: str = None, room_id: str = None):
        content = {"username": username}
        if score is not None:
            content["score"] = str(score)
        if is_playing is not None:
            content["is_playing"] = str(is_playing)
        if room_id is not None:
            content["room_id"] = str(room_id)
        return self._send_content(State.UPDATE_USER, content)

    def update_room(self, room_code: str, status: str):
        content = {
            "room_code": str(room_code),
            "status": str(status),
        }
        return self._send_content(State.UPDATE_ROOM, content)
