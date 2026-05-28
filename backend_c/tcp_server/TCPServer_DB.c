// gcc servidor.c -o servidor -lcrypto
// Necesita el paquete de desarrollo de OpenSSL
// (en Ubuntu/Debian: sudo apt install libssl-dev).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <openssl/md5.h>
#include <openssl/bio.h>
#include <openssl/hmac.h>
#include <openssl/buffer.h>

#define PORT 15000
#define BUFFER_SIZE 2048
#define APP_KEY "Another day in paradise"

// Extrae valores de un JSON plano. Tolera espacio opcional tras los dos puntos.
void extract_json_value(const char *json, const char *key, char *output) {
    char search_key[64];
    char *start = NULL;

    // Intento 1: "clave": " (con espacio)
    snprintf(search_key, sizeof(search_key), "\"%s\": \"", key);
    start = strstr(json, search_key);

    // Intento 2: "clave":" (sin espacio)
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

// Decodifica Base64 usando OpenSSL. Retorna la longitud decodificada o -1 en error.
int base64_decode(const char *input, unsigned char *output) {
    BIO *bio, *b64;
    int input_len = strlen(input);

    b64 = BIO_new(BIO_f_base64());
    bio = BIO_new_mem_buf(input, input_len);
    bio = BIO_push(b64, bio);

    // IMPORTANTE: la bandera debe ponerse ANTES de leer.
    BIO_set_flags(bio, BIO_FLAGS_BASE64_NO_NL);

    int len = BIO_read(bio, output, input_len);
    BIO_free_all(bio);
    return len;
}

// Deriva llave/IV de la APP_KEY y desencripta AES-128-CBC.
int decrypt_db_field(const char *b64_input, char *plaintext_output) {
    if (!b64_input || strlen(b64_input) == 0) {
        plaintext_output[0] = '\0';
        return -1;
    }

    // 1. Derivar Clave e IV a partir de la APP_KEY (igual que en Python)
    unsigned char key[16];
    unsigned char iv[16];
    unsigned char sha256_res[SHA256_DIGEST_LENGTH];

    // Clave: primeros 16 bytes del SHA-256 de la APP_KEY
    SHA256((unsigned char *)APP_KEY, strlen(APP_KEY), sha256_res);
    memcpy(key, sha256_res, 16);

    // IV: los 16 bytes del MD5 de la APP_KEY
    MD5((unsigned char *)APP_KEY, strlen(APP_KEY), iv);

    // 2. Decodificar Base64
    unsigned char ciphertext[1024];
    int ciphertext_len = base64_decode(b64_input, ciphertext);
    if (ciphertext_len <= 0) return -1;

    // 3. Desencriptar AES-128-CBC
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    if (!ctx) return -1;

    // Buffer de salida separado, con margen para un bloque extra.
    unsigned char plaintext[1024 + EVP_MAX_BLOCK_LENGTH];
    int len = 0;
    int plaintext_len = 0;

    if (EVP_DecryptInit_ex(ctx, EVP_aes_128_cbc(), NULL, key, iv) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }

    if (EVP_DecryptUpdate(ctx, plaintext, &len, ciphertext, ciphertext_len) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        return -1;
    }
    plaintext_len = len;

    // EVP_DecryptFinal_ex remueve el relleno PKCS7
    if (EVP_DecryptFinal_ex(ctx, plaintext + len, &len) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        return -1; // No estaba cifrado o la clave/IV no coinciden
    }
    plaintext_len += len;
    EVP_CIPHER_CTX_free(ctx);

    // 4. Terminación nula para string en C
    memcpy(plaintext_output, plaintext, plaintext_len);
    plaintext_output[plaintext_len] = '\0';

    return plaintext_len;
}

// Calcula el HMAC SHA256 necesario para que db_server.py acepte el paquete.
void calculate_hmac_local(const char* data, char* output) {
    unsigned char hash[32];
    unsigned int len = 32;
    HMAC(EVP_sha256(), APP_KEY, strlen(APP_KEY), (unsigned char*)data, strlen(data), hash, &len);
    for(int i = 0; i < 32; i++) sprintf(output + (i * 2), "%02x", hash[i]);
    output[64] = '\0';
}

// Se comunica con db_server.py (UDP:5002) para obtener y mostrar las salas.
void fetch_and_print_active_rooms() {
    int sockfd;
    struct sockaddr_in db_addr;
    char payload[1024];
    char hmac_res[65];

    memset(&db_addr, 0, sizeof(db_addr));
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) return;

    // Timeout de 3 segundos para dar margen a la consulta en MariaDB
    struct timeval tv;
    tv.tv_sec = 3; tv.tv_usec = 0;
    setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    db_addr.sin_family = AF_INET;
    db_addr.sin_port = htons(5003);
    db_addr.sin_addr.s_addr = inet_addr("127.0.0.1");

    calculate_hmac_local("127.0.0.1", hmac_res);

    // Construimos el JSON de petición con el estado 'get_rooms'
    snprintf(payload, sizeof(payload), 
        "{\"headers\": {\"ip\": \"127.0.0.1\", \"hmac\": \"%s\", \"state\": \"get_rooms\"}, \"content\": {}}",
        hmac_res);

    printf("\n[SISTEMA_DB] Solicitando lista de salas a db_server.py (127.0.0.1:5003)...\n");
    int sent = sendto(sockfd, payload, strlen(payload), 0, (struct sockaddr *)&db_addr, sizeof(db_addr));
    if (sent < 0) {
        perror("[SISTEMA_DB] Error al enviar paquete UDP");
        close(sockfd);
        return;
    }

    char buffer[4096];
    socklen_t addr_len = sizeof(db_addr);
    int n = recvfrom(sockfd, buffer, sizeof(buffer) - 1, 0, (struct sockaddr *)&db_addr, &addr_len);
    
    if (n > 0) {
        buffer[n] = '\0';
        printf("[SISTEMA_DB] Salas encontradas en MariaDB:\n%s\n\n", buffer);
    } else {
        printf("[SISTEMA_DB] Error: No se pudo conectar con db_server.py (UDP Timeout).\n\n");
    }
    close(sockfd);
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
    server_addr.sin_port = htons(PORT);

    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("Error en bind");
        exit(EXIT_FAILURE);
    }

    if (listen(server_fd, 10) < 0) {
        perror("Error en listen");
        exit(EXIT_FAILURE);
    }

    printf("Servidor TCP (Modo Chat con Desencriptación) escuchando en el puerto %d...\n", PORT);

    // Al iniciar, realizamos una auditoría de las salas para ver los datos de HeidiSQL
    fetch_and_print_active_rooms();

    while (1) {
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
            perror("Error en accept");
            continue;
        }

        int read_size = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);
        if (read_size > 0) {
            buffer[read_size] = '\0';

            char type[32], raw_room_id[64], raw_player[128], raw_message[1024];
            char dec_room_id[64], dec_player[128], dec_message[1024];

            extract_json_value(buffer, "type", type);
            extract_json_value(buffer, "room_id", raw_room_id);
            extract_json_value(buffer, "player", raw_player);
            extract_json_value(buffer, "message", raw_message);

            // Si la desencriptación falla (< 0), se asume texto plano.
            if (decrypt_db_field(raw_room_id, dec_room_id) < 0) {
                strcpy(dec_room_id, raw_room_id);
            }
            if (decrypt_db_field(raw_player, dec_player) < 0) {
                strcpy(dec_player, raw_player);
            }
            if (decrypt_db_field(raw_message, dec_message) < 0) {
                strcpy(dec_message, raw_message);
            }

            if (strcmp(type, "MESSAGE") == 0) {
                printf("[Sala %s] %s: %s\n", dec_room_id, dec_player, dec_message);
            } else {
                printf("[JSON Raw]: %s\n", buffer);
            }
        }

        close(client_fd);
    }

    close(server_fd);
    return 0;
}