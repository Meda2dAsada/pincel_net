from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Guess(Base):
    """
    Representa un intento de adivinar de un jugador en una partida.

    Columnas:
        id          — clave primaria autoincremental
        user_id     — FK al usuario que realizó el intento
        game_id     — FK a la sala/partida donde ocurrió (room.id)
        guess       — valor que el jugador ingresó
        is_correct  — True si el intento fue correcto
    """

    __tablename__ = "guesses"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:    Mapped[int]  = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    game_id:    Mapped[int]  = mapped_column(Integer, ForeignKey("rooms.id"), nullable=False)
    guess:      Mapped[str]  = mapped_column(String(256), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    user: Mapped["User"] = relationship("User", back_populates="guesses")  # type: ignore[name-defined]
    room: Mapped["Room"] = relationship("Room", back_populates="guesses")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<Guess id={self.id} user_id={self.user_id} "
            f"game_id={self.game_id} correct={self.is_correct}>"
        )

    # ------------------------------------------------------------------
    # Métodos de acceso estilo ActiveRecord
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        session,
        user_id: int,
        game_id: int,
        guess: str,
        is_correct: bool,
    ) -> "Guess":
        """Crea y persiste un nuevo intento."""
        record = cls(
            user_id=user_id,
            game_id=game_id,
            guess=guess,
            is_correct=is_correct,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @classmethod
    def find(cls, session, guess_id: int) -> "Guess | None":
        """Busca un intento por ID. Retorna None si no existe."""
        return session.get(cls, guess_id)

    @classmethod
    def by_user(cls, session, user_id: int) -> list["Guess"]:
        """Retorna todos los intentos de un usuario."""
        return session.query(cls).filter_by(user_id=user_id).all()

    @classmethod
    def by_game(cls, session, game_id: int) -> list["Guess"]:
        """Retorna todos los intentos de una partida."""
        return session.query(cls).filter_by(game_id=game_id).all()

    @classmethod
    def correct_by_game(cls, session, game_id: int) -> list["Guess"]:
        """Retorna solo los intentos correctos de una partida."""
        return (
            session.query(cls)
            .filter_by(game_id=game_id, is_correct=True)
            .all()
        )

    @classmethod
    def all(cls, session) -> list["Guess"]:
        """Retorna todos los intentos."""
        return session.query(cls).all()

    def save(self, session) -> "Guess":
        """Persiste los cambios actuales del modelo."""
        session.add(self)
        session.commit()
        session.refresh(self)
        return self

    def delete(self, session) -> None:
        """Elimina el intento de la base de datos."""
        session.delete(self)
        session.commit()

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "user_id":    self.user_id,
            "game_id":    self.game_id,
            "guess":      self.guess,
            "is_correct": self.is_correct,
        }