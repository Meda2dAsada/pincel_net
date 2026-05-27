// static/game.js
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

// Controladores de UI
const colorPicker = document.getElementById("colorPicker");
const brushSize = document.getElementById("brushSize");
const brushSizeVal = document.getElementById("brushSizeVal");
const clearBtn = document.getElementById("clearBtn");

let drawing = false;
let lastX = 0;
let lastY = 0;
let isDrawer = false; 
let lastMsgId = 0;


canvas.addEventListener("mousedown", (e) => {
    // REGLA 2: Si no eres el dibujante, el mouse no hace nada
    if (!isDrawer) return; 
    
    drawing = true;
    [lastX, lastY] = getMousePos(e);
});

// Configuración de renderizado del pincel para trazos orgánicos
ctx.lineJoin = "round";
ctx.lineCap = "round";

// Actualizar indicador numérico de grosor en tiempo real
brushSize.addEventListener("input", (e) => {
    brushSizeVal.textContent = e.target.value;
});

// Obtener coordenadas exactas relativas al lienzo escalar
function getMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    return [
        Math.floor(e.clientX - rect.left),
        Math.floor(e.clientY - rect.top)
    ];
}

// Eventos de Mouse
canvas.addEventListener("mousedown", (e) => {
    drawing = true;
    [lastX, lastY] = getMousePos(e);
});

canvas.addEventListener("mouseup", () => drawing = false);
canvas.addEventListener("mouseout", () => drawing = false);

canvas.addEventListener("mousemove", (e) => {
    if (!drawing) return;

    const [currentX, currentY] = getMousePos(e);
    const color = colorPicker.value;
    const size = brushSize.value;

    // Dibujo Local Inmediato
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(currentX, currentY);
    ctx.strokeStyle = color;
    ctx.lineWidth = size;
    ctx.stroke();

    // Enviar a Flask
    fetch("/draw", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            room_id: ROOM_ID,
            startX: lastX,
            startY: lastY,
            endX: currentX,
            endY: currentY,
            color: color,
            size: size
        })
    });

    [lastX, lastY] = [currentX, currentY];
});

// Limpieza del lienzo
clearBtn.addEventListener("click", () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
});

// Envío de Mensajes / Intentos de palabra
// --- REEMPLAZA TU sendGuess ACTUAL CON ESTA ---
async function sendGuess() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();

    if (!message) return;

    // 1. Mostramos lo que el usuario escribió (gris normal)
    appendMessage(PLAYER_NAME, message);
    input.value = ""; // Limpiamos la caja rápido

    try {
        // 2. Le preguntamos a Flask (y Flask al TCP en C)
        const response = await fetch("/guess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                room_id: ROOM_ID,
                player: PLAYER_NAME,
                message: message
            })
        });
        
        const data = await response.json();
        
        // 3. ¡Si el Game Master dice que está bien, celebramos en el chat!
        if (data.status === "correct") {
            appendSystemMessage(`🌟 ¡ADIVINASTE LA PALABRA! (${data.word}) 🌟`);
        }
    } catch (error) {
        console.error("Error al validar la palabra:", error);
    }
}


function appendSystemMessage(msg) {
    const chatBox = document.getElementById("chatBox");
    const msgElement = document.createElement("div");
    
    msgElement.className = "chat-bubble system-bubble";
    msgElement.style.backgroundColor = "#2a1b38";
    msgElement.style.color = "#00ffcc";
    msgElement.style.fontWeight = "bold";
    msgElement.style.textAlign = "center";
    msgElement.style.border = "1px solid #00ffcc";
    
    msgElement.innerHTML = msg;
    
    chatBox.appendChild(msgElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function handleKeyPress(e) {
    if (e.key === "Enter") {
        sendGuess();
    }
}

// Insertar globos de chat dinámicos
function appendMessage(user, msg) {
    const chatBox = document.getElementById("chatBox");
    const msgElement = document.createElement("div");
    msgElement.className = "chat-bubble";
    msgElement.innerHTML = `<strong style="color: var(--accent-color);">${user}:</strong> ${msg}`;
    
    chatBox.appendChild(msgElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ──────────────────────────────────────────────
// LÓGICA DEL JUEGO CONECTADA AL SERVIDOR C
// ──────────────────────────────────────────────

async function startGame() {
    try {
        const response = await fetch("/game/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ room_id: ROOM_ID })
        });
        const data = await response.json();
        console.log("El Game Master en C inició la ronda:", data);
        
        const btn = document.getElementById("btn-start");
        if(btn) btn.style.display = "none";
    } catch (error) {
        console.error("Error al iniciar:", error);
    }
}

// Polling: Le preguntamos a Flask (y Flask al C) el estado del juego cada segundo
// Polling: Le preguntamos a Flask (y Flask al C) el estado del juego cada segundo
setInterval(async () => {
    try {
        const response = await fetch(`/game/state/${ROOM_ID}`);
        const state = await response.json();
        
        const display = document.getElementById("word-display");
        if (!display) return;

        if (state.game_status === "playing") {
            if (state.drawer === PLAYER_NAME) {
                isDrawer = true; // Desbloquea la pizarra internamente
                display.innerText = `¡Es tu turno! Dibuja: ${state.current_word}`;
                canvas.style.cursor = "crosshair";
            } else {
                isDrawer = false; // Bloquea la pizarra internamente
                let guiones = "_ ".repeat(state.word_length);
                display.innerText = `Turno de ${state.drawer}. Adivina: ${guiones}`;
                canvas.style.cursor = "not-allowed"; // Cambia el cursor a prohibido
            }
        } 
        else if (state.game_status === "round_finished") {
            isDrawer = false; // Nadie dibuja cuando acaba la ronda
            display.innerText = `¡Ronda terminada! Alguien adivinó.`;
            const btn = document.getElementById("btn-start");
            if(btn) btn.style.display = "block";
        }

        // REGLA 3: SINCRONIZACIÓN DE CHAT PARA TODOS
       // REGLA 3: SINCRONIZACIÓN DE CHAT PARA TODOS
        if (state.msg_id > lastMsgId) {
            lastMsgId = state.msg_id;
            
            // Le quitamos el "window." para que lea la variable const correctamente
            if (state.last_sender !== "" && state.last_sender !== PLAYER_NAME) {
                appendMessage(state.last_sender, state.last_message);
                
                // Si el mensaje ajeno fue la respuesta correcta, celebramos
                if (state.game_status === "round_finished" && state.is_guessed === 1) {
                     appendSystemMessage(`🌟 ¡${state.last_sender} ADIVINÓ LA PALABRA! 🌟`);
                }
            }
        }
// REGLA 4: RENDERIZAR LA TABLA DE PUNTOS
        if (state.scores) {
            const playersContainer = document.getElementById("playersContainer");
            if (playersContainer) {
                playersContainer.innerHTML = ""; // Limpiamos la lista anterior
                
                // Ordenar a los jugadores de mayor a menor puntuación
                state.scores.sort((a, b) => b.score - a.score);

                state.scores.forEach(p => {
                    const div = document.createElement("div");
                    // Diseño del bloque del jugador
                    div.style.display = "flex";
                    div.style.justifyContent = "space-between";
                    div.style.alignItems = "center";
                    div.style.padding = "10px";
                    div.style.background = "#2a2c41";
                    div.style.marginBottom = "8px";
                    div.style.borderRadius = "6px";
                    
                    // Si el jugador soy yo, le pongo un borde brilloso
                    if(p.name === PLAYER_NAME) {
                        div.style.border = "1px solid #00ffcc";
                    }

                    div.innerHTML = `
                        <span style="font-weight: bold; color: var(--accent-color);">${p.name}</span>
                        <span style="background: #d11a7e; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.85rem; font-weight: bold;">
                            ${p.score} pts
                        </span>
                    `;
                    playersContainer.appendChild(div);
                });
            }
        }

    } catch (error) {
        // Silenciado para evitar spam en consola si Flask se retrasa
    }
}, 1000);