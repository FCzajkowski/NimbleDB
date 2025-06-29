import socket, time, json, os
from gevent.pool import Pool
from gevent.server import StreamServer
from collections import namedtuple
from io import BytesIO
import gevent
from rich.console import Console 
from rich.table import Table


from protocolHandler import *
from database import * 


class CommandError(Exception): pass 
class Disconnect(Exception): pass 
class AuthError(Exception): pass

Error = namedtuple('Error', ('message', ))
DEFAULT_PORT = 7100
DEFAULT_PASSWORD = "admin123" 
console = Console()


class Client:
    def __init__(self, host='127.0.0.1', port=DEFAULT_PORT):
        self._protocol = ProtocolHandler()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((host, port))
        self._fh = self._socket.makefile('rwb')
        self._authenticated = False
        self._current_db = 0

    def execute(self, *args):
        self._protocol.write_response(self._fh, args)
        resp = self._protocol.handle_request(self._fh)
        if isinstance(resp, Error):
            raise CommandError(resp.message)
        return resp

    # Authentication
    def auth(self, password):
        result = self.execute('AUTH', password)
        if result == "OK":
            self._authenticated = True
        return result

    def set_password(self, password):
        return self.execute('SET_PASSWORD', password)

    # Database selection
    def select_db(self, db_id):
        result = self.execute('SELECT', str(db_id))
        if result == "OK":
            self._current_db = db_id
        return result

    def new_db(self, db_id=None):
        if db_id is not None:
            return self.execute('NEW_DB', str(db_id))
        return self.execute('NEW_DB')

    def list_dbs(self):
        return self.execute('LIST_DBS')

    def drop_db(self, db_id):
        return self.execute('DROP_DB', str(db_id))

    # Basic commands
    def get(self, key):
        return self.execute('GET', key)

    def set(self, key, value, ttl=None):
        if ttl is not None:
            return self.execute('SET', key, value, str(ttl))
        return self.execute('SET', key, value)

    def delete(self, key):
        return self.execute('DELETE', key)

    # Additional custom commands
    def exists(self, key):
        return self.execute('EXISTS', key)

    def del_time(self, key):
        return self.execute('DEL_TIME', key)

    def flush(self, password=None):
        if password is not None:
            return self.execute('FLUSH', password)
        return self.execute('FLUSH')

    def dump(self, filename=None, password=None):
        if password is not None:
            if filename is not None:
                return self.execute('DUMP', password, filename)
            else:
                return self.execute('DUMP', password)
        else:
            # If no password provided, server must not require authentication
            if filename is not None:
                return self.execute('DUMP', filename)
            else:
                return self.execute('DUMP')

    def load(self, filename, password=None):
        """
        Load database from dump file
        Args:
            filename: Required filename to load from
            password: Required if server has password protection
        """
        if password is not None:
            return self.execute('LOAD', password, filename)
        else:
            # If no password provided, server must not require authentication
            return self.execute('LOAD', filename)

    def time_dump(self, interval):
        return self.execute('TIME_DUMP', str(interval))

    # Bulk operations
    def bulk_get(self, *keys):
        return self.execute('BULK_GET', *keys)

    def bulk_set(self, *items):
        return self.execute('BULK_SET', *items)

class Server(object):
    def __init__(self, host='127.0.0.1', port=DEFAULT_PORT, max_clients=64, password=None):
        self._pool = Pool(max_clients)
        self._server = StreamServer(
            (host, port),
            self.connection_handler,
            spawn=self._pool)

        self._protocol = ProtocolHandler()
        self._password = password  # None means no password required
        
        # Multi-database support
        self._databases = {0: Database(0)}  # Default database
        self._next_db_id = 1
        
        self._commands = self.get_commands()
        self._time_dump_greenlet = None
        self._time_dump_interval = None
        
        # Start the TTL cleanup thread
        self._cleanup_greenlet = gevent.spawn(self._cleanup_expired_keys)

    def get_commands(self):
        return { 
            "AUTH": self.auth,
            "SET_PASSWORD": self.set_password,
            "SELECT": self.select_db,
            "NEW_DB": self.new_db,
            "LIST_DBS": self.list_dbs,
            "DROP_DB": self.drop_db,
            "GET": self.get, 
            "SET": self.set, 
            "DELETE": self.delete,
            "EXISTS": self.exists,
            "DEL_TIME": self.del_time,
            "FLUSH": self.flush, 
            "DUMP": self.dump,
            "LOAD": self.load,
            "TIME_DUMP": self.time_dump,
            "BULK_GET": self.bulk_get,
            "BULK_SET": self.bulk_set
        }

    def _cleanup_expired_keys(self):
        """Background task to clean up expired keys across all databases"""
        while True:
            current_time = time.time()
            
            for db in self._databases.values():
                expired_keys = []
                
                for key, expire_time in db._ttl.items():
                    if current_time >= expire_time:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    if key in db._kv:
                        del db._kv[key]
                    if key in db._ttl:
                        del db._ttl[key]
            
            gevent.sleep(1)  # Check every second

    def _is_expired(self, db, key):
        """Check if a key has expired in specific database"""
        if key in db._ttl:
            if time.time() >= db._ttl[key]:
                # Key has expired, remove it
                if key in db._kv:
                    del db._kv[key]
                del db._ttl[key]
                return True
        return False

    def _get_next_available_db_id(self):
        """Find the next available database ID"""
        db_id = 0
        while db_id in self._databases:
            db_id += 1
        return db_id

    # Authentication
    def auth(self, password):
        if self._password is None:
            return Error("No password set on server")
        if password == self._password:
            return "OK"
        return Error("Invalid password")

    def set_password(self, new_password):
        self._password = new_password if new_password else None
        if self._password is None:
            return "Password disabled"
        return f"Password set"

    # Database management
    def select_db(self, db_id_str):
        try:
            db_id = int(db_id_str)
            if db_id in self._databases:
                return "OK"
            return Error(f"Database {db_id} does not exist")
        except ValueError:
            return Error("Database ID must be an integer")

    def new_db(self, db_id_str=None):
        if db_id_str is None:
            # Auto-assign next available ID
            db_id = self._get_next_available_db_id()
        else:
            try:
                db_id = int(db_id_str)
                if db_id < 0:
                    return Error("Database ID must be non-negative")
                if db_id in self._databases:
                    return Error(f"Database {db_id} already exists")
            except ValueError:
                return Error("Database ID must be an integer")
        
        self._databases[db_id] = Database(db_id)
        return f"Database {db_id} created"

    def list_dbs(self):
        db_list = []
        for db_id, db in self._databases.items():
            key_count = len(db._kv)
            db_list.append(f"DB {db_id}: {key_count} keys")
        return db_list

    def drop_db(self, db_id_str):
        try:
            db_id = int(db_id_str)
            if db_id == 0:
                return Error("Cannot drop default database (0)")
            if db_id not in self._databases:
                return Error(f"Database {db_id} does not exist")
            
            del self._databases[db_id]
            return f"Database {db_id} dropped"
        except ValueError:
            return Error("Database ID must be an integer")

    # Data operations (now work with session database)
    def get(self, key, db_id=0):
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        
        if self._is_expired(db, key):
            return None
            
        if key == "*":
            # Filter out expired keys
            valid_values = []
            for k, v in db._kv.items():
                if not self._is_expired(db, k):
                    valid_values.append(v)
            return valid_values
        elif key == "**":
            # Filter out expired keys
            valid_dict = {}
            for k, v in db._kv.items():
                if not self._is_expired(db, k):
                    valid_dict[k] = v
            return valid_dict
        
        return db._kv.get(key)

    def set(self, key, value, ttl=None, db_id=0):
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        db._kv[key] = value
        
        if ttl is not None:
            try:
                ttl_seconds = int(ttl)
                if ttl_seconds > 0:
                    db._ttl[key] = time.time() + ttl_seconds
                elif key in db._ttl:
                    # Remove TTL if ttl is 0 or negative
                    del db._ttl[key]
            except (ValueError, TypeError):
                pass  # Invalid TTL, ignore it
        
        return 1

    def exists(self, key, db_id=0):
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        if self._is_expired(db, key):
            return 0
        return 1 if key in db._kv else 0

    def del_time(self, key, db_id=0):
        """Remove expiration time from a key"""
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        if key in db._ttl:
            del db._ttl[key]
            return 1
        return 0

    def delete(self, key, db_id=0):
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        deleted = 0
        if key in db._kv:
            del db._kv[key]
            deleted = 1
        if key in db._ttl:
            del db._ttl[key]
        return deleted

    def flush(self, password, db_id=0):
        if password != self._password:
            return Error("Invalid password")
        
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        kvlen = len(db._kv)
        db._kv.clear()
        db._ttl.clear()
        return kvlen

    def dump(self, password, filename=None, db_id=0):
        """Save database to file"""
        if password != self._password:
            return Error("Invalid password")
        
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        
        if filename is None:
            filename = f"reddb_dump_db{db_id}_{int(time.time())}.json"
        
        try:
            # Prepare data for dumping (filter out expired keys)
            current_time = time.time()
            dump_data = {
                'database_id': db_id,
                'data': {},
                'ttl': {},
                'timestamp': current_time
            }
            
            for key, value in db._kv.items():
                if not self._is_expired(db, key):
                    dump_data['data'][key] = value
                    if key in db._ttl:
                        # Store remaining TTL seconds
                        remaining_ttl = db._ttl[key] - current_time
                        if remaining_ttl > 0:
                            dump_data['ttl'][key] = remaining_ttl
            
            with open(filename, 'w') as f:
                json.dump(dump_data, f, indent=2)
            
            return f"Database {db_id} dumped to {filename}"
        except Exception as e:
            return Error(f"Failed to dump database: {str(e)}")

    def load(self, password, filename, db_id=0):
        """Load database from dump file"""
        if password != self._password:
            return Error("Invalid password")
        
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        
        try:
            if not os.path.exists(filename):
                return Error(f"File not found: {filename}")
            
            with open(filename, 'r') as f:
                dump_data = json.load(f)
            
            # Validate dump file format
            if not isinstance(dump_data, dict):
                return Error("Invalid dump file format: root must be object")
            
            if 'data' not in dump_data:
                return Error("Invalid dump file format: missing 'data' field")
            
            # Clear current database
            old_count = len(db._kv)
            db._kv.clear()
            db._ttl.clear()
            
            # Load data
            current_time = time.time()
            loaded_count = 0
            
            for key, value in dump_data['data'].items():
                db._kv[key] = value
                loaded_count += 1
                
                # Restore TTL if present
                if 'ttl' in dump_data and key in dump_data['ttl']:
                    try:
                        remaining_ttl = float(dump_data['ttl'][key])
                        if remaining_ttl > 0:
                            db._ttl[key] = current_time + remaining_ttl
                    except (ValueError, TypeError):
                        pass  # Skip invalid TTL values
            
            source_db = dump_data.get('database_id', 'unknown')
            return f"Database loaded from {filename} (source DB: {source_db}). Replaced {old_count} keys with {loaded_count} keys in DB {db_id}."
            
        except json.JSONDecodeError as e:
            return Error(f"Invalid JSON in dump file: {str(e)}")
        except Exception as e:
            return Error(f"Failed to load database: {str(e)}")

    def time_dump(self, interval):
        """Set up automatic database dumping every interval seconds"""
        try:
            interval_seconds = int(interval)
            if interval_seconds <= 0:
                # Stop time dumping
                if self._time_dump_greenlet:
                    self._time_dump_greenlet.kill()
                    self._time_dump_greenlet = None
                self._time_dump_interval = None
                return "Time dump stopped"
            
            # Stop existing time dump if running
            if self._time_dump_greenlet:
                self._time_dump_greenlet.kill()
            
            self._time_dump_interval = interval_seconds
            self._time_dump_greenlet = gevent.spawn(self._time_dump_worker)
            
            return f"Time dump started with interval {interval_seconds} seconds"
        except (ValueError, TypeError):
            return Error("Invalid interval value")

    def _time_dump_worker(self):
        """Background worker for time-based dumps"""
        while True:
            try:
                gevent.sleep(self._time_dump_interval)
                # Dump all databases
                for db_id in self._databases:
                    filename = f"reddb_auto_dump_db{db_id}_{int(time.time())}.json"
                    self.dump(self._password, filename, db_id)
                    console.print(f"Auto-dump completed: {filename}")
            except Exception as e:
                console.print(f"Auto-dump failed: {e}")

    def bulk_get(self, *keys, db_id=0):
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        if len(keys) == 1 and keys[0] == "*":
            return self.get("*", db_id)
        elif len(keys) == 1 and keys[0] == "**":
            return self.get("**", db_id)
        
        db = self._databases[db_id]
        result = []
        for key in keys:
            if self._is_expired(db, key):
                result.append(None)
            else:
                result.append(db._kv.get(key))
        return result

    def bulk_set(self, *items, db_id=0):
        if db_id not in self._databases:
            return Error(f"Database {db_id} does not exist")
        
        db = self._databases[db_id]
        data = list(zip(items[::2], items[1::2]))
        for key, value in data:
            db._kv[key] = value
        return len(data)
    
    def get_response(self, data, session_state):
        if not isinstance(data, list):
            try:
                data = data.split()
            except:
                raise CommandError('Request must be list or simple string.')

        if not data:
            raise CommandError('Missing command')

        command = data[0].upper()
        
        # Check authentication for protected commands (only if password is set)
        protected_commands = ['FLUSH', 'DUMP', 'LOAD']
        if self._password is not None and command in protected_commands and not session_state.get('authenticated', False):
            return Error("Authentication required")
        
        # Authentication doesn't require being authenticated
        if command == 'AUTH':
            if len(data) < 2:
                return Error("Missing password")
            result = self.auth(data[1])
            if result == "OK":
                session_state['authenticated'] = True
            return result
        
        # Set password command
        if command == 'SET_PASSWORD':
            if len(data) < 2:
                return Error("Missing password")
            return self.set_password(data[1])
        
        # Database selection
        if command == 'SELECT':
            if len(data) < 2:
                return Error("Missing database ID")
            result = self.select_db(data[1])
            if result == "OK":
                session_state['current_db'] = int(data[1])
            return result
        
        if command not in self._commands:
            raise CommandError('Unrecognized command: %s' % command)

        # Get current database for this session
        current_db = session_state.get('current_db', 0)
        
        # Route commands to appropriate database
        if command in ['GET', 'SET', 'DELETE', 'EXISTS', 'DEL_TIME', 'BULK_GET', 'BULK_SET']:
            if command == 'SET':
                if len(data) < 3:  # SET key value [ttl]
                    return Error("SET requires at least key and value")
                key, value = data[1], data[2]
                ttl = data[3] if len(data) > 3 else None
                return self.set(key, value, ttl, current_db)
            elif command in ['GET', 'DELETE', 'EXISTS', 'DEL_TIME'] and len(data) >= 2:
                return self._commands[command](data[1], current_db)
            elif command == 'BULK_GET' and len(data) >= 2:
                return self.bulk_get(*data[1:], db_id=current_db)
            elif command == 'BULK_SET' and len(data) >= 3:
                return self.bulk_set(*data[1:], db_id=current_db)
            else:
                return Error(f"Invalid arguments for {command}")
        elif command in ['FLUSH', 'DUMP', 'LOAD']:
            if command == 'FLUSH':
                password = data[1] if len(data) > 1 and self._password is not None else None
                return self.flush(password, current_db)
            elif command == 'DUMP':
                if self._password is not None:
                    if len(data) < 2:
                        return Error("Password required for DUMP")
                    password = data[1]
                    filename = data[2] if len(data) > 2 else None
                else:
                    password = None
                    filename = data[1] if len(data) > 1 else None
                return self.dump(password, filename, current_db)
            elif command == 'LOAD':
                if self._password is not None:
                    if len(data) < 3:
                        return Error("Password and filename required for LOAD")
                    password, filename = data[1], data[2]
                else:
                    if len(data) < 2:
                        return Error("Filename required for LOAD")
                    password = None
                    filename = data[1]
                return self.load(password, filename, current_db)
        else:
            return self._commands[command](*data[1:])
    
    def connection_handler(self, conn, address):
        socket_file = conn.makefile('rwb')
        session_state = {'authenticated': False, 'current_db': 0}

        try:
            while True: 
                try: 
                    data = self._protocol.handle_request(socket_file)
                except Disconnect:
                    break 

                try: 
                    resp = self.get_response(data, session_state)
                except CommandError as exc:
                    resp = Error(exc.args[0])

                self._protocol.write_response(socket_file, resp)
        finally:
            socket_file.close()

    def run(self):
        import datetime
        for i in range(10):console.print("")
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        
        table = Table(title="[bold red]RedDB[/bold red] is running..")
        table.add_row("Start Time:", f"[bold blue]{current_time}[/bold blue]")
        table.add_row("Port:", f"[bold yellow]127.0.0.1:[/bold yellow][bold green]{DEFAULT_PORT}[/bold green]")
        table.add_row(
            "Password protection:",
            "[bold green]Enabled[/bold green]" if self._password else "[bold red]Disabled[/bold red]"
        )
        table.add_row("Databases:", f"[bold cyan]{len(self._databases)}[/bold cyan]")
        
        console.print(table)
        #print(f"Features: TTL, EXISTS, DUMP, LOAD, TIME_DUMP, PASSWORD, MULTI-DB")
        for i in range(10):console.print("")
        self._server.serve_forever()

if __name__ == '__main__':
    from gevent import monkey
    monkey.patch_all()
    Server().run()
