class Database:
    def __init__(self, db_id):
        self.db_id = db_id
        self._kv = {}
        self._ttl = {}