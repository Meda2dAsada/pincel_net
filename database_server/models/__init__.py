def __init__(self, my_host="127.0.6.6", my_port=3306, db_host="127.0.6.7", db_port=3306, app_key=b"Another day in paradise"):
        self.my_host = my_host
        self.my_port = my_port
        self.db_host = db_host
        self.db_port = db_port
        self.app_key = app_key

        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.bind((self.my_host, self.my_port))
        
        # 👇 AGREGA ESTA LÍNEA DE AQUÍ 👇
        self.server.settimeout(2.0)