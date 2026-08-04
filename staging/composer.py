from sqlalchemy.orm import Session
from staging.base import Parser
from staging.parsers import JobsGovtParser, JobsParser, TradeMeParser
from storage.local import LocalStorage


def trade_me_parser(db: Session)->JobsParser:
    parser = JobsParser(
        parser=TradeMeParser(),
        storage=LocalStorage(),
        source="trade_me",
        db=db
    )
    return parser

def jobs_govt_nz_parser(db: Session)->JobsParser:
    parser = JobsParser(
        parser=JobsGovtParser(),
        storage=LocalStorage(),
        source="jobs_govt_nz",
        db=db
    )
    return parser
