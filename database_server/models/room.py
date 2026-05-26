from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Room(Base):
    __tablename__ = "rooms"

    id:        Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    status:    Mapped[str] = mapped_column(String(256), nullable=False)

    def __repr__(self) -> str:
        return f"<Room id={self.id} room_code={self.room_code!r} status={self.status!r}>"

    @classmethod
    def create(cls, session, room_code: str, status: str = "waiting") -> "Room":
        room = cls(room_code=room_code, status=status)
        session.add(room)
        session.commit()
        session.refresh(room)
        return room

    @classmethod
    def find(cls, session, room_id: int) -> "Room | None":
        return session.get(cls, room_id)

    @classmethod
    def find_by_code(cls, session, room_code: str) -> "Room | None":
        return session.query(cls).filter_by(room_code=room_code).first()

    @classmethod
    def all(cls, session) -> list["Room"]:
        return session.query(cls).all()

    @classmethod
    def active(cls, session) -> list["Room"]:
        return session.query(cls).filter_by(status="playing").all()

    def save(self, session) -> "Room":
        session.add(self)
        session.commit()
        session.refresh(self)
        return self

    def delete(self, session) -> None:
        session.delete(self)
        session.commit()

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "room_code": self.room_code,
            "status":    self.status,
        }