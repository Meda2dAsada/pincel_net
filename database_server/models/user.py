from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username:   Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    score:      Mapped[str] = mapped_column(String(256), nullable=False)
    is_playing: Mapped[str] = mapped_column(String(256), nullable=False)
    room_id:    Mapped[str] = mapped_column(String(256), nullable=False) # Se queda String por si guardas la sala encriptada

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} username={self.username!r} "
            f"score={self.score} is_playing={self.is_playing}>"
        )

    @classmethod
    def create(cls, session, username: str, score: str, is_playing: str, room_id: str) -> "User":
        user = cls(username=username, score=score, is_playing=is_playing, room_id=room_id)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @classmethod
    def find(cls, session, user_id: int) -> "User | None":
        return session.get(cls, user_id)

    @classmethod
    def find_by_username(cls, session, username: str) -> "User | None":
        return session.query(cls).filter_by(username=username).first()

    @classmethod
    def all(cls, session) -> list["User"]:
        return session.query(cls).all()

    def save(self, session) -> "User":
        session.add(self)
        session.commit()
        session.refresh(self)
        return self

    def delete(self, session) -> None:
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