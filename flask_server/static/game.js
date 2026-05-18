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

    // Dibujo Local Inmediato para evitar latencia visual
    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(currentX, currentY);
    ctx.strokeStyle = color;
    ctx.lineWidth = size;
    ctx.stroke();

    // Empaquetar vectores de trayectoria para enviar a Flask (middleware hacia el Socket en C)
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
    // Opcional: fetch('/clear', {...}) para propagar borrado distribuido
});

// Envío de Mensajes / Intentos de palabra
function sendGuess() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();

    if (!message) return;

    // Renderizado local del mensaje enviado
    appendMessage(PLAYER_NAME, message);

    fetch("/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            room_id: ROOM_ID,
            player: PLAYER_NAME,
            message: message
        })
    });

    input.value = "";
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
    chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll al fondo
}