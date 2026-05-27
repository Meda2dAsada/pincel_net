#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <openssl/md5.h>
#include <openssl/bio.h>
#include <openssl/buffer.h>

#define PORT 15000
#define BUFFER_SIZE 2048
#define MAX_CLIENTS 50
#define DB_HOST "127.0.6.7" // IP del servidor DB segun db_client.py
#define DB_PORT 3306
#define APP_KEY "Another day in paradise"

// Funciones de Desencriptación (OpenSSL)
int base64_decode(const char *input, unsigned char *output) {
    BIO *bio, *b64;
    int input_len = strlen(input);
    b64 = BIO_new(BIO_f_base64());
    bio = BIO_new_mem_buf(input, input_len);
    bio = BIO_push(b64, bio);
    BIO_set_flags(bio, BIO_FLAGS_BASE64_NO_NL);
    int len = BIO_read(bio, output, input_len);
    BIO_free_all(bio);
    return len;
}

int decrypt_data(const char *b64_input, char *plaintext_output) {
    if (!b64_input || strlen(b64_input) == 0) return -1;

    unsigned char key[16], iv[16];
    unsigned int md_len;
    
    // Generar Key usando SHA256 (Compatible con OpenSSL 3.0)
    unsigned char sha256_res[SHA256_DIGEST_LENGTH];
    EVP_MD_CTX *mdctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(mdctx, EVP_sha256(), NULL);
    EVP_DigestUpdate(mdctx, APP_KEY, strlen(APP_KEY));
    EVP_DigestFinal_ex(mdctx, sha256_res, &md_len);
    EVP_MD_CTX_free(mdctx);
    memcpy(key, sha256_res, 16);

    // Generar IV usando MD5 (Compatible con OpenSSL 3.0)
    mdctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(mdctx, EVP_md5(), NULL);
    EVP_DigestUpdate(mdctx, APP_KEY, strlen(APP_KEY));
    EVP_DigestFinal_ex(mdctx, iv, &md_len);
    EVP_MD_CTX_free(mdctx);

    unsigned char ciphertext[1024];
    int ciphertext_len = base64_decode(b64_input, ciphertext);
    if (ciphertext_len <= 0) return -1;

    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    unsigned char plaintext[1024 + EVP_MAX_BLOCK_LENGTH];
    int len = 0, plaintext_len = 0;

    EVP_DecryptInit_ex(ctx, EVP_aes_128_cbc(), NULL, key, iv);
    EVP_DecryptUpdate(ctx, plaintext, &len, ciphertext, ciphertext_len);
    plaintext_len = len;
    if (EVP_DecryptFinal_ex(ctx, plaintext + len, &len) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }
    plaintext_len += len;
    EVP_CIPHER_CTX_free(ctx);

    memcpy(plaintext_output, plaintext, plaintext_len);
    plaintext_output[plaintext_len] = '\0';
    return plaintext_len;
}

// Extracción de JSON mejorada
void extract_json_value(const char *json, const char *key, char *output) {
    char search_key[64];
    // Buscamos el patrón "clave": "
    snprintf(search_key, sizeof(search_key), "\"%s\": \"", key);
    char *start = strstr(json, search_key);
    
    if (!start) { // Reintento sin espacio tras los dos puntos
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

// Función para solicitar historial al DB Server (UDP) y reenviar al cliente
void sync_history_with_db(const char *room_id, int client_fd) {
    int udp_fd;
    struct sockaddr_in db_addr, from_addr;
    socklen_t addr_len = sizeof(from_addr);
    char request[512], response[BUFFER_SIZE];

    if ((udp_fd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) return;

    // Timeout para no bloquearse si la DB no responde
    struct timeval tv;
    tv.tv_sec = 1; tv.tv_usec = 0;
    setsockopt(udp_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    db_addr.sin_family = AF_INET;
    db_addr.sin_port = htons(DB_PORT);
    inet_pton(AF_INET, DB_HOST, &db_addr.sin_addr);

    snprintf(request, sizeof(request), "{\"headers\":{\"state\":\"get_guesses\",\"ip\":\"127.0.0.1\",\"hmac\":\"none\"},\"room_id\":\"%s\"}", room_id);
    sendto(udp_fd, request, strlen(request), 0, (struct sockaddr *)&db_addr, sizeof(db_addr));
    
    int n = recvfrom(udp_fd, response, BUFFER_SIZE - 1, 0, (struct sockaddr *)&from_addr, &addr_len);
    if (n > 0) {
        response[n] = '\0';
        // Enviar historial recuperado al cliente TCP
        send(client_fd, response, n, 0);
    }

    close(udp_fd);
}

int main() {
    int server_fd, client_fd, max_sd, sd, activity;
    int client_sockets[MAX_CLIENTS] = {0};
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len = sizeof(client_addr);
    char buffer[BUFFER_SIZE];
    fd_set readfds;

  
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("Error al crear socket");
        exit(EXIT_FAILURE);
    }

    
    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT); // 6000, como lo define tcp_client.py
    printf("Iniciando OpenSSL y Servidor...\n");
   
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
        FD_ZERO(&readfds);
        FD_SET(server_fd, &readfds);
        max_sd = server_fd;

        for (int i = 0; i < MAX_CLIENTS; i++) {
            sd = client_sockets[i];
            if (sd > 0) FD_SET(sd, &readfds);
            if (sd > max_sd) max_sd = sd;
        }

        activity = select(max_sd + 1, &readfds, NULL, NULL, NULL);

        if (FD_ISSET(server_fd, &readfds)) {
            client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
            for (int i = 0; i < MAX_CLIENTS; i++) {
                if (client_sockets[i] == 0) {
                    client_sockets[i] = client_fd;
                    break;
                }
            }
        }

        for (int i = 0; i < MAX_CLIENTS; i++) {
            sd = client_sockets[i];
            if (FD_ISSET(sd, &readfds)) {
                int read_size = recv(sd, buffer, BUFFER_SIZE - 1, 0);
                if (read_size <= 0) {
                    close(sd);
                    client_sockets[i] = 0;
                } else {
                    buffer[read_size] = '\0';
                    char type[32], raw_room[64], raw_player[128], raw_msg[512];
                    char dec_room[64], dec_player[128], dec_msg[512];

                    extract_json_value(buffer, "type", type);
                    extract_json_value(buffer, "room_id", raw_room);
                    extract_json_value(buffer, "player", raw_player);
                    extract_json_value(buffer, "message", raw_msg);

                    if (decrypt_data(raw_room, dec_room) < 0) strcpy(dec_room, raw_room);
                    if (decrypt_data(raw_player, dec_player) < 0) strcpy(dec_player, raw_player);
                    if (decrypt_data(raw_msg, dec_msg) < 0) strcpy(dec_msg, raw_msg);

                    if (strcmp(type, "MESSAGE") == 0 || strcmp(type, "GUESS") == 0) {
                        printf("[Sala %s] %s: %s\n", dec_room, dec_player, dec_msg);
                        // Broadcast: Enviar a todos los demás
                        for (int j = 0; j < MAX_CLIENTS; j++) {
                            if (client_sockets[j] != 0) {
                                send(client_sockets[j], buffer, read_size, 0);
                            }
                        }
                    } else if (strcmp(type, "SYNC") == 0) {
                        sync_history_with_db(dec_room, sd);
                    }
                }
            }
        }
    }

    close(server_fd);
    return 0;
}