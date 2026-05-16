import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="TU_PASSWORD",
        database="pincelnet"
    )

def insert_player(player_name):
    connection = get_connection()
    cursor = connection.cursor()

    query = "INSERT INTO players (name) VALUES (%s)"
    cursor.execute(query, (player_name,))

    connection.commit()
    cursor.close()
    connection.close()