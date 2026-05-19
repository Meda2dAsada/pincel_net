#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>  
#include <netdb.h>
#include "cJSON.h" 

#define MSGSIZE 2048 
#define PUERTO 5000  

void parse_server_json(const char *json_string) {
    cJSON *parsed_json = cJSON_Parse(json_string);
    if (parsed_json == NULL) {
        printf("Error parsing JSON!\n");
        return;
    }

    printf("\n--- Parsed JSON Data ---\n");
    
    cJSON *my_string = cJSON_GetObjectItemCaseSensitive(parsed_json, "string");
    if (cJSON_IsString(my_string)) {
        printf("String: %s\n", my_string->valuestring);
    }

    cJSON *my_bool = cJSON_GetObjectItemCaseSensitive(parsed_json, "bool");
    if (cJSON_IsBool(my_bool)) {
        printf("Bool: %s\n", cJSON_IsTrue(my_bool) ? "True" : "False");
    }

    cJSON *my_int = cJSON_GetObjectItemCaseSensitive(parsed_json, "int");
    if (cJSON_IsNumber(my_int)) {
        printf("Int: %d\n", my_int->valueint);
    }

    cJSON *my_array = cJSON_GetObjectItemCaseSensitive(parsed_json, "arr");
    if (cJSON_IsArray(my_array)) {
        printf("Array Items: ");
        cJSON *array_item = NULL;
        
        cJSON_ArrayForEach(array_item, my_array) {
            if (cJSON_IsString(array_item)) {
                printf("%s ", array_item->valuestring);
            }
        }
        printf("\n"); 
    }

    printf("------------------------\n");
    
    cJSON_Delete(parsed_json);
}

int main(int argc, char *argv[]) {
    int sd;        
    struct hostent *hp;        
    struct sockaddr_in pin;      
    char *host;      

    if (argc != 2) {
        fprintf(stderr,"Uso: %s <host_ip>\n", argv[0]);
        exit(1);
    }
    
    host = argv[1];

    if ((hp = gethostbyname(host)) == 0) {
        perror("gethostbyname");
        exit(1);
    }
    
    pin.sin_family = AF_INET;
    pin.sin_addr.s_addr = ((struct in_addr *) (hp->h_addr))->s_addr;
    pin.sin_port = htons(PUERTO);                    

    if ((sd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("socket");
        exit(1);
    }

    if (connect(sd, (struct sockaddr *)&pin, sizeof(pin)) == -1) {
        perror("connect");
        exit(1);
    }

    printf("Connected to server! Waiting for JSON...\n");

    char buffer[MSGSIZE];
    memset(buffer, 0, MSGSIZE);
    
    int n = recv(sd, buffer, MSGSIZE - 1, 0);
    
    if (n > 0) {
        buffer[n] = '\0';
        printf("Raw socket message received:\n%s\n", buffer);
        
        parse_server_json(buffer);
    } else {
        printf("Server closed connection or error occurred.\n");
    }

    close(sd);
    return 0;
}