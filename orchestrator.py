from collector import main as collect
from parser import main as parse
from loaders.loader import main as load
from transform import main as transform

# will be on airflow or kestra soon, not now tho
def main():
    print("starting scraper")
    collect()
    print("starting parser")
    parse()
    print("starting loader")
    load()
    print("starting data quality check and transform")
    transform()


if __name__ == "__main__":
    main()
