from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Room(Base):
    """
    Representa una sala de juego.

    Columnas:
        id          — clave primaria autoincremental
        room_code   — código único visible para los jugadores (ej. "A3F9")
        status      — estado de la sala: 'waiting', 'playing', 'finished'
    """

    __tablename__ = "rooms"

    id:        Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    status:    Mapped[str] = mapped_column(String(32), default="waiting", nullable=False)

    # Relación: una sala puede tener muchos guesses
    guesses: Mapped[list["Guess"]] = relationship(  # type: ignore[name-defined]
        "Guess", back_populates="room", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Room id={self.id} room_code={self.room_code!r} status={self.status!r}>"

    # ------------------------------------------------------------------
    # Métodos de acceso estilo ActiveRecord
    # ------------------------------------------------------------------

    @classmethod
    def create(cls, session, room_code: str, status: str = "waiting") -> "Room":
        """Crea y persiste una nueva sala."""
        room = cls(room_code=room_code, status=status)
        session.add(room)
        session.commit()
        session.refresh(room)
        return room

    @classmethod
    def find(cls, session, room_id: int) -> "Room | None":
        """Busca una sala por ID. Retorna None si no existe."""
        return session.get(cls, room_id)

    @classmethod
    def find_by_code(cls, session, room_code: str) -> "Room | None":
        """Busca una sala por su código."""
        return session.query(cls).filter_by(room_code=room_code).first()

    @classmethod
    def all(cls, session) -> list["Room"]:
        """Retorna todas las salas."""
        return session.query(cls).all()

    @classmethod
    def active(cls, session) -> list["Room"]:
        """Retorna las salas en estado 'playing'."""
        return session.query(cls).filter_by(status="playing").all()

    def save(self, session) -> "Room":
        """Persiste los cambios actuales del modelo."""
        session.add(self)
        session.commit()
        session.refresh(self)
        return self

    def delete(self, session) -> None:
        """Elimina la sala de la base de datos."""
        session.delete(self)
        session.commit()

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "room_code": self.room_code,
            "status":    self.status,
        }