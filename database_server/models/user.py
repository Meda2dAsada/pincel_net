from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    """
    Representa un jugador registrado en el sistema.

    Columnas:
        id          — clave primaria autoincremental
        username    — nombre único del jugador
        score       — puntuación acumulada (-1 = sin puntuación aún)
        is_playing  — True si el jugador está actualmente en una partida
        room_id     — ID de la sala en la que está (-1 = sin sala)
    """

    __tablename__ = "users"

    id:         Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    username:   Mapped[str]  = mapped_column(String(64), unique=True, nullable=False)
    score:      Mapped[int]  = mapped_column(Integer, default=-1, nullable=False)
    is_playing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    room_id:    Mapped[int]  = mapped_column(Integer, default=-1, nullable=False)

    # Relación: un usuario puede tener muchos guesses
    guesses: Mapped[list["Guess"]] = relationship(  # type: ignore[name-defined]
        "Guess", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} username={self.username!r} "
            f"score={self.score} is_playing={self.is_playing}>"
        )

    # ------------------------------------------------------------------
    # Métodos de acceso estilo ActiveRecord
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, session, username: str) -> "User":
        """Crea y persiste un nuevo usuario."""
        user = cls(username=username)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @classmethod
    def find(cls, session, user_id: int) -> "User | None":
        """Busca un usuario por ID. Retorna None si no existe."""
        return session.get(cls, user_id)

    @classmethod
    def find_by_username(cls, session, username: str) -> "User | None":
        """Busca un usuario por nombre de usuario."""
        return session.query(cls).filter_by(username=username).first()

    @classmethod
    def all(cls, session) -> list["User"]:
        """Retorna todos los usuarios."""
        return session.query(cls).all()

    def save(self, session) -> "User":
        """Persiste los cambios actuales del modelo."""
        session.add(self)
        session.commit()
        session.refresh(self)
        return self

    def delete(self, session) -> None:
        """Elimina el usuario de la base de datos."""
        session.delete(self)
        session.commit()

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "username":   self.username,
            "score":      self.score,
            "is_playing": self.is_playing,
            "room_id":    self.room_id,
        }