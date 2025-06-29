from TAGS import *
from 
import os 
import shlex
from rich.console import Console 
from rich.traceback import install

# Enable rich traceback
install()

tag = tags()
console = Console()

def print_return(message): 
    console.print(f"[bold cyan]{message}")
    return f"{message}"

def parse_command(input_string):
    """Parse command with proper handling of quoted strings"""
    try:
        # Use shlex to properly parse quoted strings
        return shlex.split(input_string)
    except ValueError as e:
        # If shlex fails (e.g., unmatched quotes), fall back to simple split
        console.print(f"[bold yellow]Warning:[/bold yellow] {e}, using simple parsing")
        return input_string.split()

def select():
    command = client.select_db(tag.tag_index[1])
    print_return(command)
    
def list():
    command = client.list_dbs()
    print_return(command)

def new_db():
    try:
        name = tag.tag_index[1]
        command = client.new_db(name)
        print_return(command)
    except IndexError:
        command = client.new_db()
        print_return(command)
        
def drop_db():
    index = tag.tag_index[1]
    command = client.drop_db(index)
    print_return(command)
    
    
def flush(): 
    index = tag.tag_index[1]
    command = client.flush_db(index)
    print_return(command)
    
def delete():
    key = tag.tag_index[1]
    command = client.delete(key)
    print_return(command)
        
def set_password():
    try:
        password = tag.tag_index[1]
        command = client.set_password(password)
        print_return(command)
    except IndexError:
        command = client.set_password()
        print_return(command) 

def set(): 
    try:
        key = tag.tag_index[1]
        value = tag.tag_index[2]
        command = client.set(key, value)
        print_return(command)
    except IndexError:
        error("SET command requires both key and value")
    
def get(): 
    key = tag.tag_index[1]
    command = client.get(key)
    print_return(command)


def exists():
    key = tag.tag_index[1]
    command = client.exists(key)
    print_return(command)
    
def dump():
    try:
        dump_name = tag.tag_index[1]
        command = client.dump(dump_name)
        print_return(command)
    except IndexError:
        command = client.dump()
        print_return(command)
        
def time_dump():
    try:
        waiting_time = tag.tag_index[1]
        command = client.dump(waiting_time)
        print_return(command)
    except IndexError:
        command = client.dump(0)
        print_return(command)

def load():
    try: 
        load_name = tag.tag_index[1]
        command = client.load(load_name)
        print_return(command)
    except IndexError: 
        print_return("[bold red]Error:[/bold red] Did not mention dump name")

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def error(e): 
    console.print(f"[bold red]Error:[/bold red] {e}")

def auth():
    pass

def BETA_HELP():
    print(commands)

commands = {
    'help': BETA_HELP,
    'password': set_password,
    'connect': select,
    'new_db': new_db, 
    "dbs": list,
    "drop": drop_db,
    "get": get,
    "set": set, 
    "delete": delete,
    "exist": exists,
    "flush": flush,
    'dump': dump,
    'load': load,
    'tdump': time_dump,
    'clear': clear,
}

def main_loop():
    while True:
        x = input(">>").strip()
        if x in ["", " "] or x[0] in ["/", "#"]:
            continue
        if x in ["^c", "^z"]:
            break

        # Parse the command properly handling quoted strings
        parsed_args = parse_command(x)
        
        # Update tag.tag_index with properly parsed arguments
        tag.tag_index = parsed_args
        
        cmd = tag.tag_index[0] if tag.tag_index else ""
        try:
            commands.get(cmd, lambda: error(f"Unknown command: {cmd}"))()
        except Exception as e:
            error(e)

if __name__ == "__main__":
    try:
        client = Client()
        console.print("[bold green]Database Connected[/bold green]")
        main_loop()
    except Exception as e:
        console.print(f"[bold red]Failed to connect to database:[/bold red] {e}")