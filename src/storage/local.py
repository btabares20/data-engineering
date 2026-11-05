import json
import os
from pathlib import Path
import tempfile

class LocalStorage:
    def save(self, filename: str, jobs: list[dict]):
        return self._write(filename, (json.dumps(job, ensure_ascii=False) + "\n" for job in jobs))

    def save_json(self, filename, data):
        self._write(filename, [json.dumps(data, ensure_ascii=False)])

    def _write(self, filename, chunks):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                count = 0
                for chunk in chunks:
                    stream.write(chunk)
                    count += 1
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
            return count
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
