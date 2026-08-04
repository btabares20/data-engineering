import json

class LocalStorage:
    def save(self, filename: str, jobs: list[dict]):
        with open(filename, 'w+') as file:
            for job in jobs:
                file.write(json.dumps(job) + "\n")
