// Compilar con: gcc TCPServer.c -o tcp.exe -lcrypto
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <time.h>
#include <arpa/inet.h>
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <openssl/bio.h>
#include <openssl/buffer.h>

#define PORT 15000
#define BUFFER_SIZE 2048
#define MAX_ROOMS 100
#define APP_KEY "Another day in paradise"

// Banco de palabras estático del servidor
const char* word_bank[] = {
    "perro", "gato", "computadora", "servidor", "pincel",
    "canvas", "manzana", "guitarra", "codigo", "internet"
};
#define WORD_BANK_SIZE 10

#define MAX_PLAYERS 10

typedef struct {
    char username[128];
    int score;
} PlayerScore;

// Estructura expandida para controlar el estado de juego por sala
typedef struct {
    char room_id[64];
    char current_word[128];
    char current_drawer[128];
    char status[32]; // "waiting", "playing", "round_finished"
    int word_length;
    int is_guessed;
    // Sincronización de chat
    char last_sender[128];
    char last_message[512];
    int msg_id;
    // Sistema de puntajes
    PlayerScore players[MAX_PLAYERS];
    int player_count;
} GameRoom;

GameRoom rooms[MAX_ROOMS];
int room_count = 0;

// Buscar o inicializar una sala
GameRoom* get_or_create_room(const char* room_id) {
    for (int i = 0; i < room_count; i++) {
        if (strcmp(rooms[i].room_id, room_id) == 0) {
            return &rooms[i];
        }
    }
    if (room_count < MAX_ROOMS) {
        strcpy(rooms[room_count].room_id, room_id);
        strcpy(rooms[room_count].status, "waiting");
        rooms[room_count].current_word[0] = '\0';
        rooms[room_count].current_drawer[0] = '\0';
        rooms[room_count].word_length = 0;
        rooms[room_count].is_guessed = 0;
        rooms[room_count].last_sender[0] = '\0';
        rooms[room_count].last_message[0] = '\0';
        rooms[room_count].msg_id = 0;
        rooms[room_count].player_count = 0; // INICIALIZAMOS EL CONTADOR DE JUGADORES
        return &rooms[room_count++];
    }
    return NULL;
}

// ──────────────────────────────────────────────
// Utilerías JSON de extracción lineal
// ──────────────────────────────────────────────
void extract_json_value(const char *json, const char *key, char *output) {
    char search_key[64];
    char *start = NULL;
    snprintf(search_key, sizeof(search_key), "\"%s\": \"", key);
    start = strstr(json, search_key);
    if (!start) {
        snprintf(search_key, sizeof(search_key), "\"%s\":\"", key);
        start = strstr(json, search_key);
    }
    if (start) {
        start += strlen(search_key);
        char *end = strchr(start, '\"');
        if (end) {
            int length = end - start;
            strncpy(output, start, length);
            output[length] = '\0';
            return;
        }
    }
    output[0] = '\0';
}

// Función para sumar puntos (o registrar jugador nuevo)
void add_points(GameRoom* room, const char* username, int points) {
    for (int i = 0; i < room->player_count; i++) {
        if (strcmp(room->players[i].username, username) == 0) {
            room->players[i].score += points;
            return;
        }
    }
    // Si no existe en la lista, lo creamos
    if (room->player_count < MAX_PLAYERS) {
        strcpy(room->players[room->player_count].username, username);
        room->players[room->player_count].score = points;
        room->player_count++;
    }
}

int main() {
    int server_fd, client_fd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len = sizeof(client_addr);
    char buffer[BUFFER_SIZE];
    srand(time(NULL)); // Inicializar semilla para palabras aleatorias

    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("Error al crear socket");
        exit(EXIT_FAILURE);
    }

    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT);

    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Error en bind");
        exit(EXIT_FAILURE);
    }

    if (listen(server_fd, 10) < 0) {
        perror("Error en listen");
        exit(EXIT_FAILURE);
    }

    printf("Servidor TCP (Game Master Autoritatvo) escuchando en el puerto %d...\n", PORT);

    while (1) {
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) continue;

        int read_size = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);
        if (read_size > 0) {
            buffer[read_size] = '\0';

            char type[32], room_id[64];
            extract_json_value(buffer, "type", type);
            extract_json_value(buffer, "room_id", room_id);

            GameRoom *room = get_or_create_room(room_id);

            // AMPLIAMOS el response a 2048 para que quepa el JSON de los scores
            char response[2048] = {0};

            if (room != NULL) {
                // ─── ACCIÓN: INICIAR RONDA / SELECCIONAR PALABRA RANDOM ───
                if (strcmp(type, "START_ROUND") == 0) {
                    char player[128];
                    extract_json_value(buffer, "player", player);
                    add_points(room, player, 0); // Registramos al que inicia la ronda

                    // Elegir palabra aleatoria del banco
                    int idx = rand() % WORD_BANK_SIZE;
                    strcpy(room->current_word, word_bank[idx]);
                    strcpy(room->current_drawer, player);
                    strcpy(room->status, "playing");
                    room->word_length = strlen(room->current_word);
                    room->is_guessed = 0;

                    printf("[Sala %s] Turno de %s. Palabra asignada: %s\n", room->room_id, room->current_drawer, room->current_word);

                    snprintf(response, sizeof(response),
                        "{\"status\": \"ok\", \"word\": \"%s\", \"drawer\": \"%s\"}",
                        room->current_word, room->current_drawer);
                    send(client_fd, response, strlen(response), 0);
                }

                // ─── ACCIÓN: PROCESAR INTENTO DE ADIVINAR (CHAT) ───
                else if (strcmp(type, "MESSAGE") == 0) {
                    char player[128], message[512];
                    extract_json_value(buffer, "player", player);
                    extract_json_value(buffer, "message", message);

                    // Registramos su presencia en el marcador por si acaba de unirse
                    add_points(room, player, 0);

                    // Guardamos el mensaje en la memoria de la sala para sincronizar a otros
                    strcpy(room->last_sender, player);
                    strcpy(room->last_message, message);
                    room->msg_id++;

                    // REGLA 1: El dibujante NO puede adivinar
                    if (strcmp(room->current_drawer, player) == 0) {
                        printf("[Sala %s] %s (Dibujante) dice: %s\n", room->room_id, player, message);
                        snprintf(response, sizeof(response), "{\"status\": \"drawer_chat\"}");
                    }
                    // REGLA NORMAL: Jugador normal adivina correctamente
                    else if (strcmp(room->status, "playing") == 0 && strcasecmp(room->current_word, message) == 0) {
                        room->is_guessed = 1;
                        strcpy(room->status, "round_finished");

                        // ¡PREMIO! Sumamos 10 puntos al jugador
                        add_points(room, player, 10);

                        printf("⭐ [Sala %s] ¡%s ADIVINÓ LA PALABRA (%s)! ⭐\n", room->room_id, player, room->current_word);

                        snprintf(response, sizeof(response),
                            "{\"status\": \"correct\", \"player\": \"%s\", \"word\": \"%s\"}",
                            player, room->current_word);
                    }
                    // REGLA NORMAL: Jugador falla, es solo un chat
                    else {
                        printf("[Sala %s] %s: %s\n", room->room_id, player, message);
                        snprintf(response, sizeof(response), "{\"status\": \"incorrect\"}");
                    }
                    send(client_fd, response, strlen(response), 0);
                }

                // ─── GETTER: CONSULTAR ESTADO DE LA SALA Y PUNTAJES ───
                else if (strcmp(type, "GET_STATE") == 0) {
                    // 1. Armamos el arreglo JSON de puntos a mano
                    char scores_json[1024] = "[";
                    for(int i = 0; i < room->player_count; i++) {
                        char temp[256];
                        snprintf(temp, sizeof(temp), "{\"name\":\"%s\",\"score\":%d}%s",
                            room->players[i].username, room->players[i].score,
                            (i < room->player_count - 1) ? "," : "");
                        strcat(scores_json, temp);
                    }
                    strcat(scores_json, "]");

                    // 2. Inyectamos el JSON de puntos en la respuesta final
                    snprintf(response, sizeof(response),
                        "{\"game_status\": \"%s\", \"drawer\": \"%s\", \"current_word\": \"%s\", \"word_length\": %d, \"is_guessed\": %d, \"last_sender\": \"%s\", \"last_message\": \"%s\", \"msg_id\": %d, \"scores\": %s}",
                        room->status, room->current_drawer, room->current_word, room->word_length, room->is_guessed,
                        room->last_sender, room->last_message, room->msg_id, scores_json);

                    send(client_fd, response, strlen(response), 0);
                }
            }
        }
        close(client_fd);
    }
    close(server_fd);
    return 0;
}