#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <signal.h>
#include <sys/wait.h>

#define MAXLINE 1024
#define HEARTBEAT_PORT 5001     // Puerto donde el servidor TCP envía señales de vida
#define TCP_SERVER_PORT 15000   // Puerto donde escucha el servidor TCP
#define CLIENT_LISTEN_PORT 5002 // Puerto para recibir datos UDP externos
#define HEARTBEAT_TIMEOUT 5     // Segundos sin heartbeat antes de considerar caído
#define MAX_BEATS 3             // Número de heartbeats perdidos para revivir

pid_t tcp_server_pid = -1;

void revive_tcp_server() {
    printf("[HEARTBEAT] ¡Servidor TCP caído! Reviviendo servidor");
    system("../tcp_server/server \"ALIVE\" &");
}

// Monitor de heartbeat: recibe señales de vida del servidor TCP
void heartbeat_monitor(int listenfd) {
    struct sockaddr_in cliaddr;
    socklen_t len = sizeof(cliaddr);
    char buffer[MAXLINE];
    int n;
    int beats_missed = 0;
    struct timeval tv;
    
    tv.tv_sec = HEARTBEAT_TIMEOUT;
    tv.tv_usec = 0;
    setsockopt(listenfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    
    printf("[HEARTBEAT] Monitor activo en puerto %d\n", HEARTBEAT_PORT);
    printf("[HEARTBEAT] Esperando señales de vida cada %d segundos\n", HEARTBEAT_TIMEOUT);
    printf("[HEARTBEAT] Revivirá después de %d heartbeats perdidos\n", MAX_BEATS);
    
    while (1) {
        n = recvfrom(listenfd, buffer, MAXLINE - 1, 0, (struct sockaddr*)&cliaddr, &len);
        
        if (n < 0) {
            if (errno == EWOULDBLOCK || errno == EAGAIN) {
                beats_missed++;
                printf("[HEARTBEAT] Latido perdido (%d/%d)\n", beats_missed, MAX_BEATS);
                
                if (beats_missed >= MAX_BEATS) {
                    revive_tcp_server();
                    beats_missed = 0;
                }
            } else {
                perror("[HEARTBEAT] Error en recvfrom");
            }
        } else {
            buffer[n] = '\0';
            beats_missed = 0;
            printf("[HEARTBEAT] Latido recibido: %s\n", buffer);
        }
    }
}


// Puente UDP - TCP (recibe datos de clientes y los reenvía al servidor TCP)

void data_bridge_manager(int listenfd) {
    struct sockaddr_in cliaddr;
    socklen_t len = sizeof(cliaddr);
    char buffer[MAXLINE];
    int n;
    
    printf("[BRIDGE] Puente de datos activo en puerto %d\n", CLIENT_LISTEN_PORT);
    printf("[BRIDGE] Reenviará datos al servidor TCP en 127.0.0.1:%d\n", TCP_SERVER_PORT);
    
    while (1) {
        n = recvfrom(listenfd, buffer, MAXLINE - 1, 0, (struct sockaddr*)&cliaddr, &len);
        
        if (n > 0) {
            buffer[n] = '\0';
            printf("[BRIDGE] Recibido UDP (%d bytes): %s\n", n, buffer);
            
            // Intentar conectar al servidor TCP local
            int tcp_sock = socket(AF_INET, SOCK_STREAM, 0);
            if (tcp_sock >= 0) {
                struct sockaddr_in tcp_server_addr;
                memset(&tcp_server_addr, 0, sizeof(tcp_server_addr));
                tcp_server_addr.sin_family = AF_INET;
                tcp_server_addr.sin_port = htons(TCP_SERVER_PORT);
                tcp_server_addr.sin_addr.s_addr = inet_addr("127.0.0.1"); // Mismo contenedor
                
                // Timeout rápido
                struct timeval tv;
                tv.tv_sec = 2;
                tv.tv_usec = 0;
                setsockopt(tcp_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
                setsockopt(tcp_sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
                
                if (connect(tcp_sock, (struct sockaddr*)&tcp_server_addr, sizeof(tcp_server_addr)) == 0) {
                    int sent = send(tcp_sock, buffer, strlen(buffer), 0);
                    printf("[BRIDGE] Enviado %d bytes al servidor TCP\n", sent);
                    
                    // Opcional: recibir respuesta del servidor TCP
                    char response[MAXLINE];
                    int received = recv(tcp_sock, response, MAXLINE - 1, 0);
                    if (received > 0) {
                        response[received] = '\0';
                        printf("[BRIDGE] Respuesta del TCP: %s\n", response);
                        
                        // Reenviar respuesta al cliente UDP original
                        sendto(listenfd, response, received, 0, (struct sockaddr*)&cliaddr, len);
                    }
                } else {
                    printf("[BRIDGE] No se pudo conectar al servidor TCP (¿está caído?)\n");
                }
                close(tcp_sock);
            } else {
                perror("[BRIDGE] Error creando socket TCP");
            }
        }
    }
}

int create_udp_socket(int puerto) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) {
        perror("Error creando socket UDP");
        exit(EXIT_FAILURE);
    }
    
    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(puerto);
    
    if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        fprintf(stderr, "Error en bind del puerto %d: %s\n", puerto, strerror(errno));
        close(fd);
        exit(EXIT_FAILURE);
    }
    return fd;
}

int main() {
    int heartbeat_fd = create_udp_socket(HEARTBEAT_PORT);
    int bridge_fd = create_udp_socket(CLIENT_LISTEN_PORT);
        
    // Crear hijo para monitor de heartbeat
    pid_t heartbeat_pid = fork();
    if (heartbeat_pid == 0) {
        // Hijo heartbeat
        close(bridge_fd);
        heartbeat_monitor(heartbeat_fd);
        exit(0);
    }
    
    // Crear hijo para puente de datos
    pid_t bridge_pid = fork();
    if (bridge_pid == 0) {
        // Hijo bridge
        close(heartbeat_fd);
        data_bridge_manager(bridge_fd);
        exit(0);
    }
    
    // Proceso padre: cierra sockets y espera
    close(heartbeat_fd);
    close(bridge_fd);
    
    printf("[MAIN] Sistema operativo. Heartbeat PID: %d, Bridge PID: %d\n", heartbeat_pid, bridge_pid);
    printf("[MAIN] Servidor TCP inicial PID: %d\n", tcp_server_pid);
    printf("[MAIN] Presiona Ctrl+C para detener\n\n");
    
    // Mantener padre vivo y manejar señales
    while (1) {
        sleep(1);
    }
    
    return 0;
}