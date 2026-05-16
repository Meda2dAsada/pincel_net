const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

let drawing = false;

canvas.addEventListener("mousedown", () => {
    drawing = true;
});

canvas.addEventListener("mouseup", () => {
    drawing = false;
});

canvas.addEventListener("mousemove", (event) => {
    if (!drawing) return;

    const rect = canvas.getBoundingClientRect();

    const x = Math.floor(event.clientX - rect.left);
    const y = Math.floor(event.clientY - rect.top);

    ctx.fillRect(x, y, 4, 4);

    fetch("/draw", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            room_id: ROOM_ID,
            x: x,
            y: y,
            color: "black"
        })
    });
});

function sendGuess() {
    const input = document.getElementById("messageInput");
    const message = input.value;

    if (!message) return;

    fetch("/guess", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            room_id: ROOM_ID,
            message: message
        })
    });

    input.value = "";
}