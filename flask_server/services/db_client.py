import socket
import json
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from enum import Enum

class State(Enum):
    IDLE = "idle",
    EXCHANGE_PK = "exchange_pk",
    SAVE_USER = "save_user",
    SAVE_ROOM = "save_room",
    SAVE_SCORE = "save_score",
    SAVE_GUESS = "save_guess",


STATE = State.IDLE

enum_status_dict = {item.name: item.value for item in State}
string_status_dict = {item.value: item.name for item in State}

# 1. Generate a private key
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

# 2. Extract the public key
public_key = private_key.public_key()


DB_HOST = "127.0.6.7"
DB_PORT = 3306
APP_KEY = 73

MY_HOST = "127.0.6.6"

def get_enum(value):    return enum_status_dict[value]
def get_string(name):   return string_status_dict[name]

def encrypt(message, pk = public_key):
    ciphertext = pk.encrypt(
        message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return ciphertext

def decrypt(ciphertext, lk = private_key):
    plaintext = lk.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return plaintext

def mail(data):
    package = json.dumps(data)
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.sendto(package.encode("utf-8"), (DB_HOST, DB_PORT))
        udp_socket.close()
        
        return True
    except Exception as e:
        print("[UDP ERROR]", e)
        return False
    

def exchange_pk():
    data = {
        "headers" : {
            "ip"    :   MY_HOST,
            "hmac"  :   encrypt(public_key, APP_KEY)
        },
        "message" : encrypt(public_key, APP_KEY)
    }

    mail(data)


def send(message, msg_STATE = STATE):
    data = {
        "headers" : {
            "ip"    :   MY_HOST,
            "hmac"  :   encrypt(MY_HOST, APP_KEY),
            "state" :   get_string(msg_STATE),
        },
        "message" : {encrypt(message, public_key)}
    }
    mail(data)
    
    
def save_user(id, username):
    data = {
        "headers" : {
                "ip"    :   MY_HOST,
                "hmac"  :   encrypt(MY_HOST, APP_KEY),
                "state" :   get_string(State.SAVE_USER),
        },
        "message" : {
                "id" : encrypt(str(id), public_key),
                "username" : encrypt(username, public_key),
        }
    }




if __name__ == "__main__":
    import socket
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((DB_HOST, DB_PORT))

    print(f"UDP server listening on {DB_HOST}:{DB_PORT}")

    while True:
        data, address = server.recvfrom(4096)
        print(f"[UDP RECEIVED] From {address}")
        
        match STATE:
            case State.IDLE:
                break;
            case State.EXCHANGE_PK:
                break;
            case _:
                break;