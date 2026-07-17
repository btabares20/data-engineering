import json

from engine import get_db
from models import Staging
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy.dialects.postgresql import insert

db_context = contextmanager(get_db)
parsed_file = Path(__file__).resolve().parents[1] / "parsed.json"
def main():
    with db_context() as db:
        with open(parsed_file, 'r') as file:
            for line in file:
                if not line.strip():
                    continue
                    
                data = json.loads(line.strip())
                if "reference" in data:
                    data["external_reference_id"] = data.pop("reference")
                stmt = insert(Staging).values(**data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["external_reference_id"],
                    set_={
                        c.name: stmt.excluded[c.name]
                        for c in Staging.__table__.columns
                        if c.name != "id"
                    },
                )
                db.execute(stmt)
            db.commit()

if __name__ == "__main__":
    main()
