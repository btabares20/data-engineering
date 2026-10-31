from sqlalchemy import text
from db.engine import engine


STATEMENTS = (
    "ALTER TABLE staging ADD COLUMN IF NOT EXISTS job_description TEXT",
    "ALTER TABLE staging ADD COLUMN IF NOT EXISTS description_kind VARCHAR(32)",
    "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS job_description TEXT",
    "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS description_kind VARCHAR(32)",
    "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS skills_mentioned JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS skills_required JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS skills_evidence JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS skills_taxonomy_version VARCHAR(32)",
)


def upgrade_job_descriptions():
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))


if __name__ == "__main__":
    upgrade_job_descriptions()
