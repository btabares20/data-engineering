from abc import ABC, abstractmethod
from typing import Type, TypeVar
from sqlalchemy.orm.session import Session
from sqlalchemy.dialects.postgresql import insert
from utils.logging import get_logger 

logger = get_logger(__name__)

ModelT = TypeVar("ModelT")

class Storage(ABC):
    @abstractmethod
    def save(self, job: dict) -> bool:
        ...

class PostgreSQLRawStorage[ModelT](Storage):
    def __init__(
        self, 
        session: Session, 
        save_model: Type[ModelT], 
        conflict_columns: list[str]
    ) -> None:
        self.session = session
        self.save_model = save_model
        self.conflict_columns = conflict_columns

    def save(self, job: dict) -> bool:
        stmt = insert(self.save_model).values(**job)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=self.conflict_columns
        )

        result = self.session.execute(stmt)
        self.session.commit()
        rowcount = result.rowcount
        logger.debug(f"Saved {job}")
        
        return True if rowcount > 0 else False
