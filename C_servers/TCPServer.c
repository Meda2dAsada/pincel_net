#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>

#define PORT 15000
#define BUFFER_SIZE 2048

// Función auxiliar básica para extraer valores de un JSON plano sin usar librerías externas
void extract_json_value(const char *json, const char *key, char *output) {
    char search_key[64];
    // Buscamos el patrón "clave": "
    snprintf(search_key, sizeof(search_key), "\"%s\": \"", key);

    char *start = strstr(json, search_key);
    if (start) {
        start += strlen(search_key); // Avanzamos el puntero hasta el valor
        char *end = strchr(start, '\"'); // Buscamos las comillas de cierre
        if (end) {
            int length = end - start;
            strncpy(output, start, length);
            output[length] = '\0';
            return;
        }
    }
    output[0] = '\0'; // Si falla, dejamos el string vacío
}

int main() {
    int server_fd, client_fd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len = sizeof(client_addr);
    char buffer[BUFFER_SIZE];

  
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("Error al crear socket");
        exit(EXIT_FAILURE);
    }

    
    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT); // 6000, como lo define tcp_client.py

   
    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Error en bind");
        exit(EXIT_FAILURE);
    }

    
    if (listen(server_fd, 10) < 0) {
        perror("Error en listen");
        exit(EXIT_FAILURE);
    }

    printf("Servidor TCP (Modo Chat Simple) escuchando en el puerto %d...\n", PORT);

    
    while (1) {
        
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
            perror("Error en accept");
            continue;
        }

        
        int read_size = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);
        if (read_size > 0) {
            buffer[read_size] = '\0'; 

            char type[32], room_id[32], player[64], message[512];

            extract_json_value(buffer, "type", type);
            extract_json_value(buffer, "room_id", room_id);
            extract_json_value(buffer, "player", player);
            extract_json_value(buffer, "message", message);

            if (strcmp(type, "MESSAGE") == 0) {
                printf("[Sala %s] %s: %s\n", room_id, player, message);
            } else {
                printf("[JSON Raw]: %s\n", buffer);
            }
        }

        close(client_fd);
    }

    close(server_fd);
    return 0;
}