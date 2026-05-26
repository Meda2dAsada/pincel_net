// gcc servidor.c -o servidor -lcrypto
// para compilar este archivo necesita tener instalado 
// el paquete de desarrollo de OpenSSL 
// (en Ubuntu/Debian es sudo apt install libssl-dev).

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
#define APP_KEY "Another day in paradise"

// Función auxiliar básica para extraer valores de un JSON plano sin usar librerías externas
void extract_json_value(const char *json, const char *key, char *output) {
    char search_key[64];
    snprintf(search_key, sizeof(search_key), "\"%s\": \"", key);

    char *start = strstr(json, search_key);
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

// Función auxiliar para decodificar Base64 usando OpenSSL
int base64_decode(const char* input, unsigned char* output) {
    BIO *bio, *b64;
    int decodeLen = strlen(input);
    
    b64 = BIO_new(BIO_f_base64());
    bio = BIO_new_mem_buf(input, decodeLen);
    bio = BIO_push(b64, bio);
    
    // Ignorar saltos de línea para procesar el JSON correctamente
    BIO_set_flags(bio, BIO_FLAGS_BASE64_NO_NL); 
    
    int len = BIO_read(bio, output, decodeLen);
    BIO_free_all(bio);
    return len; // Retorna la longitud de los bytes encriptados reales
}

// Inicializar llaves (SHA256 y MD5) y desencriptar AES-128-CBC
int decrypt_db_field(const char* b64_input, char* plaintext_output) {
    if (!b64_input || strlen(b64_input) == 0) {
        plaintext_output[0] = '\0';
        return -1;
    }

    // 1. Derivar Clave e IV a partir de la APP_KEY (igual que en Python)
    unsigned char key[16];
    unsigned char iv[16];
    unsigned char sha256_res[SHA256_DIGEST_LENGTH];
    
    // Clave: Primeros 16 bytes del SHA256
    SHA256((unsigned char*)APP_KEY, strlen(APP_KEY), sha256_res);
    memcpy(key, sha256_res, 16);
    
    // IV: Los 16 bytes del MD5
    MD5((unsigned char*)APP_KEY, strlen(APP_KEY), iv);

    // 2. Decodificar Base64
    unsigned char ciphertext[1024];
    int ciphertext_len = base64_decode(b64_input, ciphertext);
    if (ciphertext_len <= 0) return -1;

    // 3. Configurar OpenSSL para la desencriptación AES-128-CBC
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    int len = 0;
    int plaintext_len = 0;

    EVP_DecryptInit_ex(ctx, EVP_aes_128_cbc(), NULL, key, iv);
    EVP_DecryptUpdate(ctx, ciphertext, &len, ciphertext, ciphertext_len);
    plaintext_len = len;

    // EVP_DecryptFinal_ex remueve el relleno PKCS7
    if (EVP_DecryptFinal_ex(ctx, ciphertext + len, &len) <= 0) {
        EVP_CIPHER_CTX_free(ctx);
        return -1; // Retorna error si no estaba cifrado o la clave está mal
    }
    plaintext_len += len;
    EVP_CIPHER_CTX_free(ctx);

    // 4. Añadir terminación nula para string en C
    memcpy(plaintext_output, ciphertext, plaintext_len);
    plaintext_output[plaintext_len] = '\0'; 

    return plaintext_len;
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

    while (1) {
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
            perror("Error en accept");
            continue;
        }

        int read_size = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);
        if (read_size > 0) {
            buffer[read_size] = '\0'; 

            char type[32], raw_room_id[32], raw_player[64], raw_message[512];
            char dec_room_id[32], dec_player[64], dec_message[512];

            // Extraer strings crudos del JSON
            extract_json_value(buffer, "type", type);
            extract_json_value(buffer, "room_id", raw_room_id);
            extract_json_value(buffer, "player", raw_player);
            extract_json_value(buffer, "message", raw_message);

            // Intentar desencriptar. Si falla (< 0), se asume texto plano y se copia el original.
            if (decrypt_db_field(raw_room_id, dec_room_id) < 0) {
                strcpy(dec_room_id, raw_room_id);
            }
            if (decrypt_db_field(raw_player, dec_player) < 0) {
                strcpy(dec_player, raw_player);
            }
            if (decrypt_db_field(raw_message, dec_message) < 0) {
                strcpy(dec_message, raw_message);
            }

            // Mostrar el mensaje procesado
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