// static/game.js
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

const colorPicker = document.getElementById("colorPicker");
const brushSize = document.getElementById("brushSize");
const brushSizeVal = document.getElementById("brushSizeVal");
const clearBtn = document.getElementById("clearBtn");

const drawerName = document.getElementById("drawerName");
const timerValue = document.getElementById("timerValue");
const wordDisplay = document.getElementById("wordDisplay");
const scoreList = document.getElementById("scoreList");

let drawing = false;
let lastX = 0;
let lastY = 0;
let canDraw = false;
let currentRound = null;
let lastDrawWarningAt = 0;
let lastChatEventId = 0;

ctx.lineJoin = "round";
ctx.lineCap = "round";

brushSize.addEventListener("input", (e) => {
    brushSizeVal.textContent = e.target.value;
});

function getMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    return [
        Math.floor(e.clientX - rect.left),
        Math.floor(e.clientY - rect.top)
    ];
}

function updateGameStateUI(state) {
    if (!state) return;

    if (currentRound !== null && currentRound !== state.round_number) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        appendSystemMessage("Nuevo turno iniciado.");
    }
    currentRound = state.round_number;

    canDraw = Boolean(state.is_drawer);
    canvas.classList.toggle("canvas-disabled", !canDraw);

    drawerName.textContent = state.drawer || "-";
    timerValue.textContent = state.time_remaining ?? "-";
    wordDisplay.textContent = state.word_hint || "-";

    renderScores(state.scores || {});
}

function renderScores(scores) {
    scoreList.innerHTML = "";

    Object.entries(scores)
        .sort((a, b) => b[1] - a[1])
        .forEach(([player, score]) => {
            const row = document.createElement("div");
            row.className = "score-row";

            const nameEl = document.createElement("span");
            nameEl.textContent = player;

            const scoreEl = document.createElement("strong");
            scoreEl.textContent = `${score} pts`;

            row.appendChild(nameEl);
            row.appendChild(scoreEl);
            scoreList.appendChild(row);
        });
}

function drawLine(startX, startY, endX, endY, color, size) {
    ctx.beginPath();
    ctx.moveTo(Number(startX), Number(startY));
    ctx.lineTo(Number(endX), Number(endY));
    ctx.strokeStyle = color || "black";
    ctx.lineWidth = Number(size || 5);
    ctx.stroke();
}

async function refreshGameState() {
    try {
        const response = await fetch(`/state/${encodeURIComponent(ROOM_ID)}`);
        if (!response.ok) return;

        const state = await response.json();
        updateGameStateUI(state);
    } catch (error) {
        console.error("No se pudo actualizar el estado del juego", error);
    }
}

async function refreshChatMessages() {
    try {
        const response = await fetch(
            `/messages/${encodeURIComponent(ROOM_ID)}?after=${lastChatEventId}`
        );
        if (!response.ok) return;

        const data = await response.json();
        (data.events || []).forEach(renderChatEvent);

        if (typeof data.last_event_id === "number") {
            lastChatEventId = Math.max(lastChatEventId, data.last_event_id);
        }
    } catch (error) {
        console.error("No se pudieron actualizar los mensajes", error);
    }
}

function renderChatEvent(event) {
    if (!event || event.id <= lastChatEventId) return;

    if (event.type === "system") {
        appendSystemMessage(event.message);
    } else {
        appendMessage(event.player, event.message);
    }

    lastChatEventId = Math.max(lastChatEventId, event.id);
}

function showDrawWarning() {
    const now = Date.now();
    if (now - lastDrawWarningAt < 2500) return;

    lastDrawWarningAt = now;
    appendSystemMessage("No puedes dibujar en este turno.");
}

canvas.addEventListener("mousedown", (e) => {
    if (!canDraw) {
        showDrawWarning();
        return;
    }

    drawing = true;
    [lastX, lastY] = getMousePos(e);
});

canvas.addEventListener("mouseup", () => drawing = false);
canvas.addEventListener("mouseout", () => drawing = false);

canvas.addEventListener("mousemove", (e) => {
    if (!drawing || !canDraw) return;

    const [currentX, currentY] = getMousePos(e);
    const color = colorPicker.value;
    const size = brushSize.value;

    drawLine(lastX, lastY, currentX, currentY, color, size);

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
    }).then(async (response) => {
        if (response.ok) return;

        const data = await response.json();
        updateGameStateUI(data.state);
        appendSystemMessage(data.message || "No puedes dibujar en este turno.");
    }).catch((error) => {
        console.error("No se pudo enviar el dibujo", error);
    });

    [lastX, lastY] = [currentX, currentY];
});

clearBtn.addEventListener("click", () => {
    if (!canDraw) {
        showDrawWarning();
        return;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
});

async function sendGuess() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();

    if (!message) return;

    input.value = "";

    try {
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
        updateGameStateUI(data.state);

        if (!data.accepted) {
            appendSystemMessage(data.message || "Respuesta rechazada.");
            return;
        }

        if (data.correct) {
            appendSystemMessage(data.message || "Correcto.");
            refreshChatMessages();
            return;
        }

        refreshChatMessages();
    } catch (error) {
        console.error("No se pudo enviar la respuesta", error);
        appendSystemMessage("No se pudo enviar la respuesta.");
    }
}

function handleKeyPress(e) {
    if (e.key === "Enter") {
        sendGuess();
    }
}

function appendMessage(user, msg) {
    const chatBox = document.getElementById("chatBox");
    const msgElement = document.createElement("div");
    msgElement.className = "chat-bubble";

    const userEl = document.createElement("strong");
    userEl.style.color = "var(--accent-color)";
    userEl.textContent = `${user}: `;

    const textEl = document.createElement("span");
    textEl.textContent = msg;

    msgElement.appendChild(userEl);
    msgElement.appendChild(textEl);
    chatBox.appendChild(msgElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function appendSystemMessage(message) {
    const chatBox = document.getElementById("chatBox");
    const msgElement = document.createElement("div");
    msgElement.className = "chat-system";
    msgElement.textContent = message;

    chatBox.appendChild(msgElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

updateGameStateUI(INITIAL_GAME_STATE);
refreshChatMessages();
setInterval(refreshGameState, 1000);
setInterval(refreshChatMessages, 1000);
