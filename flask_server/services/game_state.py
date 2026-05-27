from dataclasses import dataclass, field
import random
import time
import unicodedata
from threading import RLock


TURN_DURATION_SECONDS = 100
POINTS_PER_SECOND = 10

WORDS = [
    "avion",
    "bicicleta",
    "casa",
    "computadora",
    "guitarra",
    "hamburguesa",
    "lapiz",
    "montana",
    "perro",
    "pizza",
    "robot",
    "telefono",
]


@dataclass
class RoomState:
    players: list = field(default_factory=list)
    current_turn_index: int = 0
    current_word: str = ""
    turn_started_at: float = field(default_factory=time.monotonic)
    guessed_players: set = field(default_factory=set)
    scores: dict = field(default_factory=dict)
    chat_events: list = field(default_factory=list)
    next_event_id: int = 1
    round_number: int = 0


class GameState:
    def __init__(self):
        self._rooms = {}
        self._lock = RLock()

    def ensure_room(self, room_id, players):
        with self._lock:
            clean_players = self._clean_players(players)

            if room_id not in self._rooms:
                self._rooms[room_id] = RoomState(players=clean_players)
                if clean_players:
                    self._start_round_locked(room_id, advance_turn=False)
            else:
                state = self._rooms[room_id]
                for player in clean_players:
                    if player not in state.players:
                        state.players.append(player)
                    state.scores.setdefault(player, 0)

                if state.players and not state.current_word:
                    self._start_round_locked(room_id, advance_turn=False)

            return self._rooms[room_id]

    def get_player_state(self, room_id, player, players):
        with self._lock:
            self.ensure_room(room_id, players)
            self._advance_if_expired_locked(room_id)
            return self._public_state_locked(room_id, player)

    def add_chat_event(self, room_id, event_type, player, message, players):
        with self._lock:
            state = self.ensure_room(room_id, players)
            event = {
                "id": state.next_event_id,
                "type": event_type,
                "player": player,
                "message": str(message or ""),
                "created_at": time.time(),
            }
            state.next_event_id += 1
            state.chat_events.append(event)
            state.chat_events = state.chat_events[-100:]
            return dict(event)

    def get_chat_events(self, room_id, after_id, players):
        with self._lock:
            state = self.ensure_room(room_id, players)
            events = [
                dict(event)
                for event in state.chat_events
                if event["id"] > after_id
            ]
            last_event_id = state.chat_events[-1]["id"] if state.chat_events else after_id
            return {
                "events": events,
                "last_event_id": last_event_id,
            }

    def can_player_draw(self, room_id, player, players):
        with self._lock:
            state = self.ensure_room(room_id, players)
            self._advance_if_expired_locked(room_id)

            if not state.players:
                return False, "No hay jugadores en la sala."

            if player != self._drawer_locked(state):
                return False, "Solo el jugador en turno puede dibujar."

            return True, "El jugador puede dibujar."

    def submit_guess(self, room_id, player, guess, players):
        with self._lock:
            state = self.ensure_room(room_id, players)
            self._advance_if_expired_locked(room_id)

            result = {
                "accepted": False,
                "correct": False,
                "points": 0,
                "round_finished": False,
                "message": "",
                "state": self._public_state_locked(room_id, player),
            }

            if not state.players:
                result["message"] = "No hay jugadores en la sala."
                return result

            if player == self._drawer_locked(state):
                result["message"] = "El jugador que dibuja no puede adivinar."
                return result

            if player in state.guessed_players:
                result["message"] = "Ya adivinaste esta palabra."
                return result

            if not str(guess or "").strip():
                result["message"] = "La respuesta esta vacia."
                return result

            result["accepted"] = True
            result["correct"] = self._normalize(guess) == self._normalize(state.current_word)

            if not result["correct"]:
                result["message"] = "Respuesta enviada."
                result["state"] = self._public_state_locked(room_id, player)
                return result

            elapsed = max(0, time.monotonic() - state.turn_started_at)
            result["points"] = self._calculate_points(elapsed)
            state.guessed_players.add(player)
            state.scores[player] = state.scores.get(player, 0) + result["points"]
            result["message"] = f"Correcto. Ganaste {result['points']} puntos."

            if self._all_guessers_finished_locked(state):
                result["round_finished"] = True
                self._start_round_locked(room_id, advance_turn=True)

            result["state"] = self._public_state_locked(room_id, player)
            return result

    def _start_round_locked(self, room_id, advance_turn):
        state = self._rooms[room_id]
        if not state.players:
            return

        if advance_turn:
            state.current_turn_index = (state.current_turn_index + 1) % len(state.players)
        else:
            state.current_turn_index = state.current_turn_index % len(state.players)

        state.current_word = random.choice(WORDS)
        state.turn_started_at = time.monotonic()
        state.guessed_players.clear()
        state.round_number += 1

        for player in state.players:
            state.scores.setdefault(player, 0)

    def _advance_if_expired_locked(self, room_id):
        state = self._rooms[room_id]
        if not state.players or not state.current_word:
            return

        if self._elapsed_locked(state) >= TURN_DURATION_SECONDS:
            self._start_round_locked(room_id, advance_turn=True)

    def _public_state_locked(self, room_id, player):
        state = self._rooms[room_id]
        drawer = self._drawer_locked(state) if state.players else None
        is_drawer = player == drawer
        time_remaining = max(0, TURN_DURATION_SECONDS - int(self._elapsed_locked(state)))

        return {
            "room_id": room_id,
            "players": list(state.players),
            "drawer": drawer,
            "is_drawer": is_drawer,
            "word": state.current_word if is_drawer else None,
            "word_hint": state.current_word if is_drawer else self._mask_word(state.current_word),
            "time_remaining": time_remaining,
            "turn_duration": TURN_DURATION_SECONDS,
            "scores": dict(state.scores),
            "guessed_players": sorted(state.guessed_players),
            "round_number": state.round_number,
        }

    def _drawer_locked(self, state):
        if not state.players:
            return None
        return state.players[state.current_turn_index % len(state.players)]

    def _elapsed_locked(self, state):
        return time.monotonic() - state.turn_started_at

    def _calculate_points(self, elapsed_seconds):
        remaining = max(0, TURN_DURATION_SECONDS - elapsed_seconds)
        return int(remaining * POINTS_PER_SECOND)

    def _all_guessers_finished_locked(self, state):
        guessers = [player for player in state.players if player != self._drawer_locked(state)]
        return bool(guessers) and all(player in state.guessed_players for player in guessers)

    def _clean_players(self, players):
        clean_players = []
        for player in players or []:
            player = str(player or "").strip()
            if player and player not in clean_players:
                clean_players.append(player)
        return clean_players

    def _normalize(self, value):
        text = str(value or "").strip().lower()
        text = unicodedata.normalize("NFD", text)
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        text = "".join(char for char in text if char.isalnum() or char.isspace())
        return " ".join(text.split())

    def _mask_word(self, word):
        parts = str(word or "").split()
        return " / ".join(" ".join("_" for _ in part) for part in parts)


game_state = GameState()
