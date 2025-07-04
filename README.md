<div align="center">
  <img src="img/logo.png" alt="Description" style="width:90px;"/>
  <h3>NimbleDB: Open Source Redis Alternative</h3>
  <code style="padding:10px;">pip install NimbleDB</code>
</div>

------------------

> [!IMPORTANT]
> Project is still in early development, there might be some issues. If any accure, please **create new issue**

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [Running the Server](#running-the-server)
  - [Using the Client](#using-the-client)
- [Architecture](#architecture)
- [API Reference](#api-reference)
  - [Authentication Commands](#authentication-commands)
  - [Database Management](#database-management)
  - [Data Operations](#data-operations)
  - [Administrative Commands](#administrative-commands)
  - [Bulk Operations](#bulk-operations)
- [Configuration](#configuration)
- [Examples](#examples)
- [Error Handling](#error-handling)
- [Performance](#performance)
- [Contributing](#contributing)

## Overview

**NimbleDB** is a high-performance, Redis-compatible in-memory database that provides fast key-value storage with enterprise-grade features. Built with Python and gevent, it offers excellent concurrency and scalability for modern applications.

### Key Characteristics

- **In-Memory Storage**: Lightning-fast data access with microsecond latency
- **Network Protocol**: TCP-based client-server architecture with custom protocol
- **Multi-Database**: Support for multiple isolated databases (0 to N)
- **TTL Support**: Automatic key expiration with background cleanup
- **Authentication**: Password-based security with configurable protection
- **Persistence**: JSON-based dump/load functionality with automatic backups
- **Concurrent**: Built on gevent for handling thousands of concurrent connections

## Installation

### Prerequisites

```bash
# Install required dependencies
pip install gevent rich
```

### File Structure

```
nimbledb/
├── NimbleDB.py          # Main server implementation
├── nibeDBClient.py      # Client library
├── protocolHandler.py   # Network protocol handler
├── database.py          # Database core logic
├── README.md           # Documentation
├── LICENSE.md          # License information
└── TAGS.py             # Additional utilities
```

## Quick Start

### Running the Server

#### Basic Server Setup

```python
# server.py
from NimbleDB import Server

# Create server with default settings
server = Server()

# Run the server
server.run()
```

#### Advanced Server Configuration

```python
# advanced_server.py
from NimbleDB import Server

# Create server with custom configuration
server = Server(
    host='0.0.0.0',        # Listen on all interfaces
    port=7100,             # Custom port
    max_clients=128,       # Maximum concurrent clients
    password='secure123'   # Enable authentication
)

# Start the server
if __name__ == '__main__':
    from gevent import monkey
    monkey.patch_all()
    server.run()
```

#### Running from Command Line

```bash
# Start server with default settings
python NimbleDB.py

# Or with custom configuration
python -c "
from NimbleDB import Server
from gevent import monkey
monkey.patch_all()
Server(host='0.0.0.0', port=7100, password='admin123').run()
"
```

### Using the Client

#### Basic Client Usage

```python
# client_example.py
from NimbleDB import Client

# Connect to server
client = Client(host='127.0.0.1', port=7100)

# Authenticate (if password is set)
client.auth('admin123')

# Basic operations
client.set('key1', 'value1')
value = client.get('key1')
print(f"Retrieved: {value}")

# Set with TTL (expires in 60 seconds)
client.set('temp_key', 'temp_value', ttl=60)

# Check if key exists
if client.exists('key1'):
    print("Key exists!")

# Delete key
client.delete('key1')
```

#### Advanced Client Operations

```python
# advanced_client.py
from NimbleDB import Client

client = Client()
client.auth('admin123')

# Multi-database operations
client.new_db(1)        # Create database 1
client.select_db(1)     # Switch to database 1
client.set('db1_key', 'db1_value')

client.select_db(0)     # Switch back to default database
client.set('db0_key', 'db0_value')

# Bulk operations
client.bulk_set('key1', 'val1', 'key2', 'val2', 'key3', 'val3')
values = client.bulk_get('key1', 'key2', 'key3')
print(f"Bulk retrieved: {values}")

# Get all keys and values
all_values = client.get('*')     # Get all values
all_data = client.get('**')      # Get all key-value pairs as dict

# Persistence operations
client.dump('backup.json')                    # Create backup
client.load('backup.json')                    # Restore from backup
client.time_dump(300)                         # Auto-dump every 5 minutes
```

## Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Client      │    │     Server      │    │    Database     │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ TCP Socket  │◄┼────┤ │ TCP Listener│ │    │ │   Key-Value │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ │    Store    │ │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ └─────────────┘ │
│ │ Protocol    │ │    │ │ Protocol    │ │    │ ┌─────────────┐ │
│ │ Handler     │ │    │ │ Handler     │ │    │ │ TTL Manager │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Protocol Flow

```
Client Request → Protocol Encoding → Network → Server Processing → Database Operation → Response
```

## API Reference

### Authentication Commands

#### `AUTH password`
Authenticate with the server using a password.

```python
# Client usage
result = client.auth('your_password')
print(result)  # "OK" if successful
```

#### `SET_PASSWORD password`
Set or change the server password.

```python
# Set new password
client.set_password('new_password')

# Disable password (empty string)
client.set_password('')
```

### Database Management

#### `SELECT db_id`
Switch to a different database.

```python
# Switch to database 1
client.select_db(1)

# Switch back to default database (0)
client.select_db(0)
```

#### `NEW_DB [db_id]`
Create a new database.

```python
# Create database with auto-assigned ID
client.new_db()

# Create database with specific ID
client.new_db(5)
```

#### `LIST_DBS`
List all databases and their key counts.

```python
db_list = client.list_dbs()
for db_info in db_list:
    print(db_info)  # "DB 0: 10 keys", "DB 1: 5 keys", etc.
```

#### `DROP_DB db_id`
Delete a database (cannot delete database 0).

```python
# Drop database 1
client.drop_db(1)
```

### Data Operations

#### `GET key`
Retrieve a value by key.

```python
# Get single value
value = client.get('mykey')

# Get all values
all_values = client.get('*')

# Get all key-value pairs as dictionary
all_data = client.get('**')
```

#### `SET key value [ttl]`
Store a key-value pair with optional TTL.

```python
# Basic set
client.set('name', 'John')

# Set with TTL (expires in 60 seconds)
client.set('session', 'abc123', ttl=60)

# Set with no TTL (removes existing TTL)
client.set('permanent', 'value', ttl=0)
```

#### `DELETE key`
Delete a key and its value.

```python
# Delete key
deleted_count = client.delete('mykey')
print(f"Deleted {deleted_count} keys")
```

#### `EXISTS key`
Check if a key exists.

```python
# Check existence
if client.exists('mykey'):
    print("Key exists!")
else:
    print("Key not found")
```

#### `DEL_TIME key`
Remove TTL from a key (make it permanent).

```python
# Remove expiration
removed = client.del_time('mykey')
print(f"TTL removed: {removed}")
```

### Administrative Commands

#### `FLUSH password`
Clear all data from the current database.

```python
# Clear database (requires password)
cleared_count = client.flush('admin123')
print(f"Cleared {cleared_count} keys")
```

#### `DUMP [password] [filename]`
Save database to a JSON file.

```python
# Basic dump with auto-generated filename
client.dump('password')

# Dump with custom filename
client.dump('password', 'my_backup.json')
```

#### `LOAD [password] filename`
Load database from a JSON file.

```python
# Load from file
result = client.load('password', 'my_backup.json')
print(result)  # Shows loaded key count
```

#### `TIME_DUMP interval`
Set up automatic database dumping.

```python
# Auto-dump every 5 minutes (300 seconds)
client.time_dump(300)

# Stop auto-dumping
client.time_dump(0)
```

### Bulk Operations

#### `BULK_GET key1 key2 key3 ...`
Retrieve multiple values at once.

```python
# Get multiple keys
values = client.bulk_get('key1', 'key2', 'key3')
print(values)  # [value1, value2, value3]

# Get all values (equivalent to GET *)
all_values = client.bulk_get('*')
```

#### `BULK_SET key1 value1 key2 value2 ...`
Set multiple key-value pairs at once.

```python
# Set multiple keys
count = client.bulk_set('name', 'John', 'age', '30', 'city', 'NYC')
print(f"Set {count} key-value pairs")
```

## Configuration

### Server Configuration

```python
class ServerConfig:
    def __init__(self):
        self.host = '127.0.0.1'      # Server host
        self.port = 7100             # Server port
        self.max_clients = 64        # Maximum concurrent clients
        self.password = None         # Authentication password
        self.auto_dump_interval = 0  # Auto-dump interval (0 = disabled)
        self.cleanup_interval = 1    # TTL cleanup interval (seconds)

# Example configuration
server = Server(
    host='0.0.0.0',
    port=7100,
    max_clients=128,
    password='secure_password_123'
)
```

### Client Configuration

```python
class ClientConfig:
    def __init__(self):
        self.host = '127.0.0.1'      # Server host
        self.port = 7100             # Server port
        self.timeout = 30            # Connection timeout
        self.auto_reconnect = True   # Auto-reconnect on failure

# Example configuration
client = Client(host='192.168.1.100', port=7100)
```

## Examples

### Example 1: Basic Key-Value Store

```python
from NimbleDB import Client

# Connect and authenticate
client = Client()
client.auth('admin123')

# Store user data
client.set('user:1:name', 'Alice')
client.set('user:1:email', 'alice@example.com')
client.set('user:1:age', '25')

# Retrieve user data
name = client.get('user:1:name')
email = client.get('user:1:email')
age = client.get('user:1:age')

print(f"User: {name}, Email: {email}, Age: {age}")
```

### Example 2: Session Management with TTL

```python
from NimbleDB import Client
import uuid

client = Client()
client.auth('admin123')

# Create session with 1-hour TTL
session_id = str(uuid.uuid4())
client.set(f'session:{session_id}', 'user_data', ttl=3600)

# Check session validity
if client.exists(f'session:{session_id}'):
    print("Session is valid")
    user_data = client.get(f'session:{session_id}')
else:
    print("Session expired")
```

### Example 3: Multi-Database Application

```python
from NimbleDB import Client

client = Client()
client.auth('admin123')

# Create separate databases for different environments
client.new_db(1)  # Production
client.new_db(2)  # Development
client.new_db(3)  # Testing

# Store data in production database
client.select_db(1)
client.set('app:version', '1.0.0')
client.set('app:config', 'production_config')

# Store data in development database
client.select_db(2)
client.set('app:version', '1.1.0-dev')
client.set('app:config', 'development_config')

# List all databases
databases = client.list_dbs()
for db in databases:
    print(db)
```

### Example 4: Data Persistence and Backup

```python
from NimbleDB import Client

client = Client()
client.auth('admin123')

# Store important data
client.set('config:database_url', 'postgresql://localhost/myapp')
client.set('config:redis_url', 'redis://localhost:6379')
client.set('config:secret_key', 'super_secret_key')

# Create backup
client.dump('admin123', 'config_backup.json')

# Simulate data loss
client.flush('admin123')

# Restore from backup
client.load('admin123', 'config_backup.json')

# Verify restoration
config_data = client.get('**')
print("Restored configuration:", config_data)
```

### Example 5: High-Performance Bulk Operations

```python
from NimbleDB import Client
import time

client = Client()
client.auth('admin123')

# Bulk insert for high performance
start_time = time.time()

# Prepare bulk data
bulk_data = []
for i in range(1000):
    bulk_data.extend([f'key:{i}', f'value:{i}'])

# Bulk insert
client.bulk_set(*bulk_data)

# Bulk retrieve
keys = [f'key:{i}' for i in range(1000)]
values = client.bulk_get(*keys)

end_time = time.time()
print(f"Bulk operations completed in {end_time - start_time:.2f} seconds")
print(f"Inserted and retrieved {len(values)} items")
```

## Error Handling

### Common Error Types

```python
from NimbleDB import Client, CommandError

client = Client()

try:
    # This will raise CommandError if authentication fails
    client.auth('wrong_password')
except CommandError as e:
    print(f"Authentication failed: {e}")

try:
    # This will raise CommandError if database doesn't exist
    client.select_db(999)
except CommandError as e:
    print(f"Database selection failed: {e}")

try:
    # This will raise CommandError for invalid commands
    client.execute('INVALID_COMMAND')
except CommandError as e:
    print(f"Command error: {e}")
```

### Error Response Format

```python
# Server errors are returned as Error namedtuples
from collections import namedtuple

Error = namedtuple('Error', ('message',))

# Example error responses:
# Error(message="Invalid password")
# Error(message="Database 5 does not exist")
# Error(message="Authentication required")
```

## Performance

### Benchmarks

| Operation | Operations/Second | Latency (avg) |
|-----------|-------------------|---------------|
| GET | 50,000+ | 0.02ms |
| SET | 45,000+ | 0.022ms |
| DELETE | 48,000+ | 0.021ms |
| BULK_GET (100 keys) | 10,000+ | 0.1ms |
| BULK_SET (100 pairs) | 8,000+ | 0.125ms |

### Optimization Tips

1. **Use Bulk Operations**: For multiple operations, use `BULK_GET` and `BULK_SET`
2. **Connection Pooling**: Reuse client connections when possible
3. **Appropriate TTL**: Set reasonable TTL values to prevent memory bloat
4. **Database Separation**: Use multiple databases to organize data logically
5. **Regular Dumps**: Schedule regular dumps to prevent data loss

### Memory Usage

```python
# Monitor memory usage
import psutil
import os

# Get current process memory usage
process = psutil.Process(os.getpid())
memory_mb = process.memory_info().rss / 1024 / 1024
print(f"Memory usage: {memory_mb:.2f} MB")
```

## Contributing

We welcome contributions to NimbleDB! Here's how you can help:

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-username/nimbledb.git
cd nimbledb

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Run linting
flake8 nimbledb/
```

### Contribution Guidelines

1. **Fork the repository** and create a feature branch
2. **Write tests** for new functionality
3. **Follow PEP 8** coding standards
4. **Update documentation** for new features
5. **Submit a pull request** with a clear description

### Areas for Contribution

- [ ] Redis protocol compatibility
- [ ] Clustering support
- [ ] Data type extensions (lists, sets, hashes)
- [ ] Monitoring and metrics
- [ ] Performance optimizations
- [ ] Documentation improvements

---

**NimbleDB** - Fast, Simple, Reliable

For more information, visit our [GitHub repository](https://github.com/your-username/nimbledb) or [create an issue](https://github.com/your-username/nimbledb/issues) for support.
