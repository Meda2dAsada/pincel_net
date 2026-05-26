#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <unistd.h>
#include <pthread.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <cjson/cJSON.h>

#define PORT 15000
#define UDP_PORT 5001
#define BUFFER_SIZE 2048

// --- VARIABLES GLOBALES DEL JUEGO A RESTAURAR ---
bool gameStarted = false;
int server_time = 0;
char server_word[256] = "";

int player_count = 0;
char player_names[10][50]; 
int player_ids[10];
int player_points[10];
bool player_answerCorrectly[10];

int painter_id = 0;
int painter_points[5000][2]; 
int painter_points_count = 0;
char painter_colors[5000][20]; 
int painter_colors_count = 0;

void* send_heartbeat(void* arg) {
    int sockfd;
    struct sockaddr_in wake_server_addr;
    char *message = "ALIVE";

    if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("Socket UDP para heartbeat falló");
        pthread_exit(NULL);
    }

    memset(&wake_server_addr, 0, sizeof(wake_server_addr));
    wake_server_addr.sin_family = AF_INET;
    wake_server_addr.sin_port = htons(UDP_PORT);
    wake_server_addr.sin_addr.s_addr = inet_addr("127.0.0.1");

    while (1) {
        sendto(sockfd, (const char *)message, strlen(message), 0, 
               (const struct sockaddr *)&wake_server_addr, sizeof(wake_server_addr));
        sleep(2); 
    }

    close(sockfd);
    pthread_exit(NULL);
}

// --- FUNCIÓN PARA CARGAR LA MEMORIA DEL JSON ---
void recuperar_servidor() {
    FILE *file = fopen("server_tcp.json", "r");
    if (file == NULL) {
        perror("[ERROR] No se pudo abrir server_tcp.json");
        return;
    }

    fseek(file, 0, SEEK_END);
    long length = ftell(file);
    fseek(file, 0, SEEK_SET);
    char *data = malloc(length + 1);
    fread(data, 1, length, file);
    data[length] = '\0';
    fclose(file);

    cJSON *root = cJSON_Parse(data);
    free(data); 

    if (root == NULL) {
        printf("[ERROR] Error de parseo en el archivo server_tcp.json\n");
        return;
    }

    cJSON *started = cJSON_GetObjectItemCaseSensitive(root, "gameStarted");
    if (cJSON_IsBool(started)) {
        gameStarted = cJSON_IsTrue(started);
    }

    cJSON *config = cJSON_GetObjectItemCaseSensitive(root, "config");
    if (config != NULL) {
        
        cJSON *server = cJSON_GetObjectItemCaseSensitive(config, "server");
        if (server != NULL) {
            cJSON *time = cJSON_GetObjectItemCaseSensitive(server, "time");
            cJSON *word = cJSON_GetObjectItemCaseSensitive(server, "word");
            
            if (cJSON_IsNumber(time)) server_time = time->valueint;
            if (cJSON_IsString(word)) strncpy(server_word, word->valuestring, sizeof(server_word) - 1);
        }

        cJSON *players = cJSON_GetObjectItemCaseSensitive(config, "players");
        if (players != NULL) {
            cJSON *count = cJSON_GetObjectItemCaseSensitive(players, "count");
            if (cJSON_IsNumber(count)) player_count = count->valueint;

            cJSON *names = cJSON_GetObjectItemCaseSensitive(players, "names");
            cJSON *ids = cJSON_GetObjectItemCaseSensitive(players, "ids");
            cJSON *points = cJSON_GetObjectItemCaseSensitive(players, "points");
            cJSON *answers = cJSON_GetObjectItemCaseSensitive(players, "answerCorrectly");

            for (int i = 0; i < player_count; i++) {
                cJSON *name_item = cJSON_GetArrayItem(names, i);
                cJSON *id_item = cJSON_GetArrayItem(ids, i);
                cJSON *point_item = cJSON_GetArrayItem(points, i);
                cJSON *ans_item = cJSON_GetArrayItem(answers, i);

                if (cJSON_IsString(name_item)) strncpy(player_names[i], name_item->valuestring, 49);
                if (cJSON_IsNumber(id_item)) player_ids[i] = id_item->valueint;
                if (cJSON_IsNumber(point_item)) player_points[i] = point_item->valueint;
                if (cJSON_IsBool(ans_item)) player_answerCorrectly[i] = cJSON_IsTrue(ans_item);
            }
        }

        cJSON *painter = cJSON_GetObjectItemCaseSensitive(config, "painter");
        if (painter != NULL) {
            cJSON *p_id = cJSON_GetObjectItemCaseSensitive(painter, "id");
            if (cJSON_IsNumber(p_id)) painter_id = p_id->valueint;

            cJSON *points_array = cJSON_GetObjectItemCaseSensitive(painter, "points");
            painter_points_count = cJSON_GetArraySize(points_array);
            for (int i = 0; i < painter_points_count; i++) {
                cJSON *sub_point = cJSON_GetArrayItem(points_array, i); 
                if (cJSON_GetArraySize(sub_point) == 2) {
                    painter_points[i][0] = cJSON_GetArrayItem(sub_point, 0)->valueint; 
                    painter_points[i][1] = cJSON_GetArrayItem(sub_point, 1)->valueint; 
                }
            }

            cJSON *colors_array = cJSON_GetObjectItemCaseSensitive(painter, "colors");
            painter_colors_count = cJSON_GetArraySize(colors_array);
            for (int i = 0; i < painter_colors_count; i++) {
                cJSON *color_item = cJSON_GetArrayItem(colors_array, i);
                if (cJSON_IsString(color_item)) {
                    strncpy(painter_colors[i], color_item->valuestring, 19);
                }
            }
        }
    }

    cJSON_Delete(root);
    printf("[SISTEMA] Recuerdos recuperados con éxito. Palabra: '%s', Tiempo restante: %ds, Jugadores: %d\n", 
            server_word, server_time, player_count);
}

int main(int argc, char* argv[]) {
    int server_fd, client_fd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len = sizeof(client_addr);
    char buffer[BUFFER_SIZE];
    int opt = 1;

    // --- DETECTAR SI ES UN REINICIO POR CAIDA ---
    if (argc > 1 && strcmp(argv[1], "ALIVE") == 0) {
        printf("[SISTEMA] Servidor iniciado en modo recuperación. Cargando estado...\n");
        recuperar_servidor();  
    } else {
        printf("[SISTEMA] Servidor iniciado normalmente.\n");
    }

    // --- INICIO DEL HILO DEL HEARTBEAT ---
    pthread_t thread_id;
    if (pthread_create(&thread_id, NULL, send_heartbeat, NULL) != 0) {
        perror("No se pudo crear el hilo del heartbeat");
        exit(EXIT_FAILURE);
    }
    pthread_detach(thread_id);
    printf("[HILO] Monitoreo de Heartbeat UDP activado de fondo.\n");

    // --- CONFIGURACIÓN DEL SOCKET TCP ---
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("Error al crear socket TCP");
        exit(EXIT_FAILURE);
    }

    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT);

    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Error en bind TCP");
        exit(EXIT_FAILURE);
    }

    if (listen(server_fd, 10) < 0) {
        perror("Error en listen TCP");
        exit(EXIT_FAILURE);
    }

    printf("Servidor TCP (Modo Chat con cJSON) escuchando en el puerto %d...\n", PORT);

    // --- BUCLE PRINCIPAL TCP ---
    while (1) {
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
            perror("Error en accept");
            continue;
        }

        int read_size = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);

        if (read_size > 0) {
            buffer[read_size] = '\0'; 

            cJSON *json = cJSON_Parse(buffer);
            
            if (json == NULL) {
                printf("[Error de Parseo] JSON inválido recibido.\n");
                printf("[JSON Raw]: %s\n", buffer);
            } else {
                cJSON *type = cJSON_GetObjectItemCaseSensitive(json, "type");
                cJSON *room_id = cJSON_GetObjectItemCaseSensitive(json, "room_id");
                cJSON *player = cJSON_GetObjectItemCaseSensitive(json, "player");
                cJSON *message = cJSON_GetObjectItemCaseSensitive(json, "message");

                if (cJSON_IsString(type) && strcmp(type->valuestring, "MESSAGE") == 0) {
                    const char *r_id = cJSON_IsString(room_id) ? room_id->valuestring : "Desconocida";
                    const char *ply  = cJSON_IsString(player)  ? player->valuestring  : "Anónimo";
                    const char *msg  = cJSON_IsString(message) ? message->valuestring : "";

                    printf("[Sala %s] %s: %s\n", r_id, ply, msg);
                } else {
                    printf("[JSON Recibido (Otro Tipo o Estructura)]: %s\n", buffer);
                }

                cJSON_Delete(json);
            }
        }
        close(client_fd);
    }

    close(server_fd);
    return 0;
}