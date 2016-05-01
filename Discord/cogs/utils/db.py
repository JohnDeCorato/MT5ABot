import json
import asyncio
import os


def load_json_file(file_name):
    inp_file = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../../..",
        "ref",
        file_name))
    return inp_file

class Database:
    """The database object. Internally based on ''json''."""

    def __init__(self, name, **options):
        self.name = name
        self.object_hook = options.pop('object_hook', None)
        self.encoder = options.pop('encoder', None)
        self.loop = options.pop('loop', asyncio.get_event_loop())
        if options.pop('load_later', False):
            self.loop.create_task(self.load())
        else:
            self.load_from_file()

        self.lock = asyncio.Lock()

    def load_from_file(self):
        try:
            with open(self.name, 'r') as f:
                self._db = json.load(f, object_hook=self.object_hook)
        except FileNotFoundError:
            self._db = {}

    async def load(self):
        await self.loop.run_in_executor(None, self.load_from_file)

    def _dump(self):
        with open(self.name, 'w') as f:
            json.dump(self._db, f, ensure_ascii=True, cls=self.encoder, indent=4)

    async def save(self):
        await self.loop.run_in_executor(None, self._dump)

    def get(self, key, *args):
        return self._db.get(key, *args)

    async def put(self, key, value, *args):
        """Edits a config entry."""
        with await self.lock:
            self._db[key] = value
            await self.save()

    async def remove(self, key):
        """Removes a config entry."""
        with await self.lock:
            del self._db[key]
            await self.save()

    def __contains__(self, item):
        return self._db.__contains__(item)

    def __len__(self):
        return self._db.__len__()

    def all(self):
        return self._db