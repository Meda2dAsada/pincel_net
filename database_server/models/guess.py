from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Guess(Base):
    __tablename__ = "guesses"

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:    Mapped[str] = mapped_column(String(256), nullable=False)
    game_id:    Mapped[str] = mapped_column(String(256), nullable=False)
    guess:      Mapped[str] = mapped_column(String(256), nullable=False)
    is_correct: Mapped[str] = mapped_column(String(256), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Guess id={self.id} user_id={self.user_id} "
            f"game_id={self.game_id} correct={self.is_correct}>"
        )

    @classmethod
    def create(cls, session, user_id: str, game_id: str, guess: str, is_correct: str) -> "Guess":
        record = cls(user_id=user_id, game_id=game_id, guess=guess, is_correct=is_correct)
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @classmethod
    def find(cls, session, guess_id: int) -> "Guess | None":
        return session.get(cls, guess_id)

    @classmethod
    def by_user(cls, session, user_id: str) -> list["Guess"]:
        return session.query(cls).filter_by(user_id=user_id).all()

    @classmethod
    def by_game(cls, session, game_id: str) -> list["Guess"]:
        return session.query(cls).filter_by(game_id=game_id).all()

    @classmethod
    def all(cls, session) -> list["Guess"]:
        return session.query(cls).all()

    def save(self, session) -> "Guess":
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
            "user_id":    self.user_id,
            "game_id":    self.game_id,
            "guess":      self.guess,
            "is_correct": self.is_correct,
        }