import asyncio
from collection.composer import jobs_govt_collector, trade_me_collector
from db.engine import db_context
from staging.composer import jobs_govt_nz_parser, trade_me_parser
from transformation.loaders import loader
from transformation.transform import transform
from utils.logging import get_logger 

logger = get_logger(__name__)

def run_jobs_govt_collector():
    with db_context() as db:
        jobs_govt_collector(db).collect()

def run_trade_me_collector():
    with db_context() as db:
        trade_me_collector(db).collect()

def run_jobs_govt_parser():
    with db_context() as db:
        jobs_govt_nz_parser(db).parse()

def run_trade_me_parser():
    with db_context() as db:
        trade_me_parser(db).parse()

def run_jobs_govt_loader():
    with db_context() as db:
        loader(db, "jobs_govt_nz_parsed.json")

def run_trade_me_loader():
    with db_context() as db:
        loader(db, "trade_me_parsed.json")

def run_transform():
    with db_context() as db:
        transform(db)
