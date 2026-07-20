import asyncio

from collectors.jobs_govt_nz import main as jobs_govt_nz_collector
from collectors.trade_me import main as trade_me_collector 
from parsers.jobs_govt_nz import main as jobs_govt_nz_parse
from parsers.trade_me import main as trade_me_parse 
from loaders.jobs_govt_nz_loader import main as jobs_govt_nz_load
from loaders.trade_me_loader import main as trade_me_load
from transform import main as transform

# will be on airflow or kestra soon, not now tho
async def main():
    print("Starting scrapers...")
    await asyncio.gather(
        asyncio.to_thread(jobs_govt_nz_collector),
        asyncio.to_thread(trade_me_collector),
    )

    print("Starting parsers...")
    await asyncio.gather(
        asyncio.to_thread(jobs_govt_nz_parse),
        asyncio.to_thread(trade_me_parse),
    )

    print("Starting loaders...")
    await asyncio.gather(
        asyncio.to_thread(jobs_govt_nz_load),
        asyncio.to_thread(trade_me_load),
    )

    print("Starting data quality check and transform...")
    await asyncio.to_thread(transform)

if __name__ == "__main__":
    asyncio.run(main())
