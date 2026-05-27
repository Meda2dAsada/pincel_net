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

// Configuración del pincel
ctx.lineJoin = "round";
ctx.lineCap = "round";

// Actualizar indicador numérico de grosor
brushSize.addEventListener("input", (e) => {
    brushSizeVal.textContent = e.target.value;
});

// Obtener coordenadas relativas al canvas
function getMousePos(e) {
    const rect = canvas.getBoundingClientRect();

    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    return [
        Math.floor((e.clientX - rect.left) * scaleX),
        Math.floor((e.clientY - rect.top) * scaleY)
    ];
}

// Dibujar línea local o remota
function drawLine(startX, startY, endX, endY, color, size) {
    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(endX, endY);
    ctx.strokeStyle = color;
    ctx.lineWidth = size;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();
}

// Eventos de mouse
canvas.addEventListener("mousedown", (e) => {
    drawing = true;
    [lastX, lastY] = getMousePos(e);
});

canvas.addEventListener("mouseup", () => {
    drawing = false;
});

canvas.addEventListener("mouseout", () => {
    drawing = false;
});

canvas.addEventListener("mousemove", (e) => {
    if (!drawing) return;

    const [currentX, currentY] = getMousePos(e);
    const color = colorPicker.value;
    const size = brushSize.value;

    // 1. Dibujar localmente para que el pintor no tenga latencia
    drawLine(lastX, lastY, currentX, currentY, color, size);

    // 2. Enviar trazo a Flask
    fetch("/draw", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json" 
        },
        body: JSON.stringify({
            room_id: ROOM_ID,
            player: PLAYER_NAME,
            startX: lastX,
            startY: lastY,
            endX: currentX,
            endY: currentY,
            color: color,
            size: size
        })
    }).catch((error) => {
        console.log("Error enviando dibujo:", error);
    });

    [lastX, lastY] = [currentX, currentY];
});

// Borrar canvas local
clearBtn.addEventListener("click", () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    fetch("/clear", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json" 
        },
        body: JSON.stringify({
            room_id: ROOM_ID,
            player: PLAYER_NAME
        })
    }).catch((error) => {
        console.log("Error enviando clear:", error);
    });
});

// Envío de mensajes / intentos de palabra
function sendGuess() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();

    if (!message) return;

    // Render local del mensaje enviado
    appendMessage(PLAYER_NAME, message);

    fetch("/guess", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json" 
        },
        body: JSON.stringify({
            room_id: ROOM_ID,
            player: PLAYER_NAME,
            message: message
        })
    }).catch((error) => {
        console.log("Error enviando mensaje:", error);
    });

    input.value = "";
}

function handleKeyPress(e) {
    if (e.key === "Enter") {
        sendGuess();
    }
}

// Insertar mensajes en el chat
function appendMessage(user, msg) {
    const chatBox = document.getElementById("chatBox");
    const msgElement = document.createElement("div");

    msgElement.className = "chat-bubble";
    msgElement.innerHTML = `<strong style="color: var(--accent-color);">${user}:</strong> ${msg}`;

    chatBox.appendChild(msgElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Escuchar eventos en vivo desde Flask
const eventSource = new EventSource(`/events/${ROOM_ID}`);

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);

    if (data.type === "UPDATE_CANVAS") {
        // Evita que el jugador que dibuja redibuje su propio trazo
        if (data.player === PLAYER_NAME) return;

        drawLine(
            data.startX,
            data.startY,
            data.endX,
            data.endY,
            data.color,
            data.size
        );
    }

    if (data.type === "CLEAR_CANVAS") {
        // Evita procesar dos veces si el mismo jugador ya limpió localmente
        if (data.player === PLAYER_NAME) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    if (data.type === "CHAT_MESSAGE") {
        if (data.player === PLAYER_NAME) return;

        appendMessage(data.player, data.message);
    }
};

eventSource.onerror = function(error) {
    console.log("Error en conexión SSE:", error);
};