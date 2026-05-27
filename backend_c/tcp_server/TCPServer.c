#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <unistd.h>
#include <pthread.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <cjson/cJSON.h>

#define TCP_PORT 15000
#define HEARTBEAT_PORT 5001
#define BUFFER_SIZE 4096
#define MAX_LINES 10000
#define STATE_FILE "server_tcp.json"

/*
    TCPServer.c oficial para PincelNet

    Funciones:
    - Recibe mensajes TCP desde Flask.
    - Procesa chat: MESSAGE.
    - Procesa dibujo: UPDATE_CANVAS.
    - Procesa limpieza de canvas: CLEAR_CANVAS.
    - Guarda estado del canvas en server_tcp.json.
    - Recupera estado si es revivido por UDPserver.c.
    - Manda heartbeat UDP al servidor de disponibilidad.
    - Atiende múltiples clientes usando pthread.
*/

typedef struct {
    char room_id[64];
    char player[64];
    int startX;
    int startY;
    int endX;
    int endY;
    char color[32];
    int size;
} DrawLine;

DrawLine canvas_lines[MAX_LINES];
int canvas_count = 0;

pthread_mutex_t state_mutex = PTHREAD_MUTEX_INITIALIZER;

/* =========================================================
   Guardar estado del canvas en JSON
   ========================================================= */
void save_state() {
    pthread_mutex_lock(&state_mutex);

    cJSON *root = cJSON_CreateObject();
    cJSON_AddNumberToObject(root, "canvas_count", canvas_count);

    cJSON *canvas = cJSON_CreateArray();

    for (int i = 0; i < canvas_count; i++) {
        cJSON *line = cJSON_CreateObject();

        cJSON_AddStringToObject(line, "room_id", canvas_lines[i].room_id);
        cJSON_AddStringToObject(line, "player", canvas_lines[i].player);
        cJSON_AddNumberToObject(line, "startX", canvas_lines[i].startX);
        cJSON_AddNumberToObject(line, "startY", canvas_lines[i].startY);
        cJSON_AddNumberToObject(line, "endX", canvas_lines[i].endX);
        cJSON_AddNumberToObject(line, "endY", canvas_lines[i].endY);
        cJSON_AddStringToObject(line, "color", canvas_lines[i].color);
        cJSON_AddNumberToObject(line, "size", canvas_lines[i].size);

        cJSON_AddItemToArray(canvas, line);
    }

    cJSON_AddItemToObject(root, "canvas", canvas);

    char *json_string = cJSON_Print(root);

    FILE *file = fopen(STATE_FILE, "w");
    if (file != NULL) {
        fputs(json_string, file);
        fclose(file);
    } else {
        perror("[ERROR] No se pudo escribir server_tcp.json");
    }

    free(json_string);
    cJSON_Delete(root);

    pthread_mutex_unlock(&state_mutex);
}

/* =========================================================
   Recuperar estado del canvas desde JSON
   ========================================================= */
void load_state() {
    pthread_mutex_lock(&state_mutex);

    FILE *file = fopen(STATE_FILE, "r");

    if (file == NULL) {
        printf("[RECOVERY] No se encontró %s. Iniciando estado limpio.\n", STATE_FILE);
        canvas_count = 0;
        pthread_mutex_unlock(&state_mutex);
        return;
    }

    fseek(file, 0, SEEK_END);
    long length = ftell(file);
    fseek(file, 0, SEEK_SET);

    if (length <= 0) {
        printf("[RECOVERY] Archivo de estado vacío. Iniciando limpio.\n");
        fclose(file);
        canvas_count = 0;
        pthread_mutex_unlock(&state_mutex);
        return;
    }

    char *data = malloc(length + 1);
    if (data == NULL) {
        perror("[RECOVERY] Error asignando memoria");
        fclose(file);
        pthread_mutex_unlock(&state_mutex);
        return;
    }

    fread(data, 1, length, file);
    data[length] = '\0';
    fclose(file);

    cJSON *root = cJSON_Parse(data);
    free(data);

    if (root == NULL) {
        printf("[RECOVERY] Error parseando %s. Iniciando limpio.\n", STATE_FILE);
        canvas_count = 0;
        pthread_mutex_unlock(&state_mutex);
        return;
    }

    cJSON *canvas = cJSON_GetObjectItemCaseSensitive(root, "canvas");

    canvas_count = 0;

    if (cJSON_IsArray(canvas)) {
        int total = cJSON_GetArraySize(canvas);

        for (int i = 0; i < total && i < MAX_LINES; i++) {
            cJSON *line = cJSON_GetArrayItem(canvas, i);

            cJSON *room_id = cJSON_GetObjectItemCaseSensitive(line, "room_id");
            cJSON *player = cJSON_GetObjectItemCaseSensitive(line, "player");
            cJSON *startX = cJSON_GetObjectItemCaseSensitive(line, "startX");
            cJSON *startY = cJSON_GetObjectItemCaseSensitive(line, "startY");
            cJSON *endX = cJSON_GetObjectItemCaseSensitive(line, "endX");
            cJSON *endY = cJSON_GetObjectItemCaseSensitive(line, "endY");
            cJSON *color = cJSON_GetObjectItemCaseSensitive(line, "color");
            cJSON *size = cJSON_GetObjectItemCaseSensitive(line, "size");

            strncpy(
                canvas_lines[canvas_count].room_id,
                cJSON_IsString(room_id) ? room_id->valuestring : "unknown",
                sizeof(canvas_lines[canvas_count].room_id) - 1
            );

            strncpy(
                canvas_lines[canvas_count].player,
                cJSON_IsString(player) ? player->valuestring : "anonymous",
                sizeof(canvas_lines[canvas_count].player) - 1
            );

            canvas_lines[canvas_count].startX = cJSON_IsNumber(startX) ? startX->valueint : 0;
            canvas_lines[canvas_count].startY = cJSON_IsNumber(startY) ? startY->valueint : 0;
            canvas_lines[canvas_count].endX = cJSON_IsNumber(endX) ? endX->valueint : 0;
            canvas_lines[canvas_count].endY = cJSON_IsNumber(endY) ? endY->valueint : 0;

            strncpy(
                canvas_lines[canvas_count].color,
                cJSON_IsString(color) ? color->valuestring : "#000000",
                sizeof(canvas_lines[canvas_count].color) - 1
            );

            canvas_lines[canvas_count].size = cJSON_IsNumber(size) ? size->valueint : 5;

            canvas_count++;
        }
    }

    cJSON_Delete(root);

    printf("[RECOVERY] Estado recuperado. Trazos cargados: %d\n", canvas_count);

    pthread_mutex_unlock(&state_mutex);
}

/* =========================================================
   Heartbeat UDP hacia UDPserver.c
   ========================================================= */
void* send_heartbeat(void* arg) {
    int sockfd;
    struct sockaddr_in udp_server_addr;
    char *message = "ALIVE";

    sockfd = socket(AF_INET, SOCK_DGRAM, 0);

    if (sockfd < 0) {
        perror("[HEARTBEAT] Error creando socket UDP");
        pthread_exit(NULL);
    }

    memset(&udp_server_addr, 0, sizeof(udp_server_addr));
    udp_server_addr.sin_family = AF_INET;
    udp_server_addr.sin_port = htons(HEARTBEAT_PORT);
    udp_server_addr.sin_addr.s_addr = inet_addr("127.0.0.1");

    while (1) {
        sendto(
            sockfd,
            message,
            strlen(message),
            0,
            (struct sockaddr *)&udp_server_addr,
            sizeof(udp_server_addr)
        );

        sleep(2);
    }

    close(sockfd);
    pthread_exit(NULL);
}

/* =========================================================
   Procesar mensaje de chat
   ========================================================= */
void handle_message(cJSON *json) {
    cJSON *room_id = cJSON_GetObjectItemCaseSensitive(json, "room_id");
    cJSON *player = cJSON_GetObjectItemCaseSensitive(json, "player");
    cJSON *message = cJSON_GetObjectItemCaseSensitive(json, "message");

    const char *r = cJSON_IsString(room_id) ? room_id->valuestring : "Desconocida";
    const char *p = cJSON_IsString(player) ? player->valuestring : "Anonimo";
    const char *m = cJSON_IsString(message) ? message->valuestring : "";

    if (strcmp(m, "__CLEAR_CANVAS__") == 0) {
        pthread_mutex_lock(&state_mutex);
        canvas_count = 0;
        pthread_mutex_unlock(&state_mutex);

        save_state();

        printf("[LIENZO] Canvas limpiado desde mensaje especial. Sala: %s | Jugador: %s\n", r, p);
        return;
    }

    printf("[CHAT] [Sala %s] %s: %s\n", r, p, m);
}

/* =========================================================
   Procesar actualización del canvas
   ========================================================= */
void handle_canvas_update(cJSON *json) {
    cJSON *room_id = cJSON_GetObjectItemCaseSensitive(json, "room_id");
    cJSON *player = cJSON_GetObjectItemCaseSensitive(json, "player");
    cJSON *startX = cJSON_GetObjectItemCaseSensitive(json, "startX");
    cJSON *startY = cJSON_GetObjectItemCaseSensitive(json, "startY");
    cJSON *endX = cJSON_GetObjectItemCaseSensitive(json, "endX");
    cJSON *endY = cJSON_GetObjectItemCaseSensitive(json, "endY");
    cJSON *color = cJSON_GetObjectItemCaseSensitive(json, "color");
    cJSON *size = cJSON_GetObjectItemCaseSensitive(json, "size");

    pthread_mutex_lock(&state_mutex);

    if (canvas_count >= MAX_LINES) {
        printf("[LIENZO] Límite de trazos alcanzado. No se guardó el trazo.\n");
        pthread_mutex_unlock(&state_mutex);
        return;
    }

    strncpy(
        canvas_lines[canvas_count].room_id,
        cJSON_IsString(room_id) ? room_id->valuestring : "unknown",
        sizeof(canvas_lines[canvas_count].room_id) - 1
    );

    strncpy(
        canvas_lines[canvas_count].player,
        cJSON_IsString(player) ? player->valuestring : "anonymous",
        sizeof(canvas_lines[canvas_count].player) - 1
    );

    canvas_lines[canvas_count].startX = cJSON_IsNumber(startX) ? startX->valueint : 0;
    canvas_lines[canvas_count].startY = cJSON_IsNumber(startY) ? startY->valueint : 0;
    canvas_lines[canvas_count].endX = cJSON_IsNumber(endX) ? endX->valueint : 0;
    canvas_lines[canvas_count].endY = cJSON_IsNumber(endY) ? endY->valueint : 0;

    strncpy(
        canvas_lines[canvas_count].color,
        cJSON_IsString(color) ? color->valuestring : "#000000",
        sizeof(canvas_lines[canvas_count].color) - 1
    );

    if (cJSON_IsNumber(size)) {
        canvas_lines[canvas_count].size = size->valueint;
    } else if (cJSON_IsString(size)) {
        canvas_lines[canvas_count].size = atoi(size->valuestring);
        if (canvas_lines[canvas_count].size <= 0) {
            canvas_lines[canvas_count].size = 5;
        }
    } else {
        canvas_lines[canvas_count].size = 5;
    }

    printf(
        "[LIENZO] Trazo guardado: sala=%s jugador=%s (%d,%d) -> (%d,%d) color=%s size=%d total=%d\n",
        canvas_lines[canvas_count].room_id,
        canvas_lines[canvas_count].player,
        canvas_lines[canvas_count].startX,
        canvas_lines[canvas_count].startY,
        canvas_lines[canvas_count].endX,
        canvas_lines[canvas_count].endY,
        canvas_lines[canvas_count].color,
        canvas_lines[canvas_count].size,
        canvas_count + 1
    );

    canvas_count++;

    pthread_mutex_unlock(&state_mutex);

    save_state();
}

/* =========================================================
   Procesar limpieza del canvas
   ========================================================= */
void handle_clear_canvas(cJSON *json) {
    cJSON *room_id = cJSON_GetObjectItemCaseSensitive(json, "room_id");
    cJSON *player = cJSON_GetObjectItemCaseSensitive(json, "player");

    const char *r = cJSON_IsString(room_id) ? room_id->valuestring : "unknown";
    const char *p = cJSON_IsString(player) ? player->valuestring : "anonymous";

    pthread_mutex_lock(&state_mutex);
    canvas_count = 0;
    pthread_mutex_unlock(&state_mutex);

    save_state();

    printf("[LIENZO] Canvas limpiado. Sala: %s | Jugador: %s\n", r, p);
}

/* =========================================================
   Hilo para atender a cada cliente TCP
   ========================================================= */
void* handle_client(void* arg) {
    int client_fd = *(int*)arg;
    free(arg);

    char buffer[BUFFER_SIZE];

    int read_size = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);

    if (read_size > 0) {
        buffer[read_size] = '\0';

        cJSON *json = cJSON_Parse(buffer);

        if (json == NULL) {
            printf("[TCP] JSON inválido recibido:\n%s\n", buffer);
            send(client_fd, "ERROR JSON\n", strlen("ERROR JSON\n"), 0);
            close(client_fd);
            pthread_exit(NULL);
        }

        cJSON *type = cJSON_GetObjectItemCaseSensitive(json, "type");

        if (cJSON_IsString(type)) {
            if (strcmp(type->valuestring, "MESSAGE") == 0) {
                handle_message(json);
            }
            else if (strcmp(type->valuestring, "UPDATE_CANVAS") == 0) {
                handle_canvas_update(json);
            }
            else if (strcmp(type->valuestring, "CLEAR_CANVAS") == 0) {
                handle_clear_canvas(json);
            }
            else {
                printf("[TCP] Tipo desconocido: %s\n", type->valuestring);
            }
        } else {
            printf("[TCP] Mensaje sin campo type:\n%s\n", buffer);
        }

        cJSON_Delete(json);

        /*
            Muy importante:
            El UDPserver.c, cuando hace bridge UDP -> TCP, puede esperar respuesta.
            Este ACK evita que el bridge se quede esperando hasta timeout.
        */
        send(client_fd, "OK\n", strlen("OK\n"), 0);
    }

    close(client_fd);
    pthread_exit(NULL);
}

/* =========================================================
   Main
   ========================================================= */
int main(int argc, char *argv[]) {
    int server_fd;
    struct sockaddr_in server_addr;
    int opt = 1;

    if (argc > 1 && strcmp(argv[1], "ALIVE") == 0) {
        printf("[SISTEMA] Servidor TCP revivido por UDPserver. Recuperando estado...\n");
    } else {
        printf("[SISTEMA] Servidor TCP iniciado normalmente.\n");
    }

    load_state();

    pthread_t heartbeat_thread;

    if (pthread_create(&heartbeat_thread, NULL, send_heartbeat, NULL) != 0) {
        perror("[HEARTBEAT] No se pudo crear el hilo de heartbeat");
        exit(EXIT_FAILURE);
    }

    pthread_detach(heartbeat_thread);

    server_fd = socket(AF_INET, SOCK_STREAM, 0);

    if (server_fd < 0) {
        perror("[TCP] Error creando socket");
        exit(EXIT_FAILURE);
    }

    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(TCP_PORT);

    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("[TCP] Error en bind");
        close(server_fd);
        exit(EXIT_FAILURE);
    }

    if (listen(server_fd, 20) < 0) {
        perror("[TCP] Error en listen");
        close(server_fd);
        exit(EXIT_FAILURE);
    }

    printf("[TCP] Servidor escuchando en puerto %d\n", TCP_PORT);
    printf("[TCP] Soporta: MESSAGE, UPDATE_CANVAS, CLEAR_CANVAS\n");
    printf("[TCP] Heartbeat UDP activo hacia puerto %d\n", HEARTBEAT_PORT);

    while (1) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);

        int *client_fd = malloc(sizeof(int));

        if (client_fd == NULL) {
            perror("[TCP] Error asignando memoria para cliente");
            continue;
        }

        *client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);

        if (*client_fd < 0) {
            perror("[TCP] Error en accept");
            free(client_fd);
            continue;
        }

        pthread_t client_thread;

        if (pthread_create(&client_thread, NULL, handle_client, client_fd) != 0) {
            perror("[TCP] Error creando hilo del cliente");
            close(*client_fd);
            free(client_fd);
            continue;
        }

        pthread_detach(client_thread);
    }

    close(server_fd);
    return 0;
}