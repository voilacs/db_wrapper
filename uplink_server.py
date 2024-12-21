import anvil.server
import sqlite3
import json
from flask import Flask, send_from_directory, abort
import threading
import os
import socket



# Flask app setup
app = Flask(__name__)
MEDIA_DIR = "media_files"
os.makedirs(MEDIA_DIR, exist_ok=True)

@app.route('/media_files/<path:filename>', methods=['GET'])
def serve_media(filename):
    """Serve media files."""
    try:
        return send_from_directory(MEDIA_DIR, filename)
    except FileNotFoundError:
        abort(404)

@app.route('/')
def home():
    return "Media server and Uplink are running."

# Flask server in a separate thread
def run_flask():
    app.run(host="0.0.0.0", port=8000)

# Replace with your Uplink key
UPLINK_KEY = "6KUJ6DMX7YKU4WZESHXOQ4H4-2U6IUMDW77ZIX6OY"
# Path to your SQLite database
DB_PATH = "local.db"

# Connect to Anvil's Uplink
anvil.server.connect(UPLINK_KEY)

def get_connection():
    """Returns a new connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # To allow dict-like row access
    return conn

def get_id_field(table_name):
    """
    Returns the unique identifier field(s) based on the table name.
    For tables with composite keys, a list of fields is returned.
    For single-field primary keys, a string is returned.
    """
    id_fields = {
        'candidates': 'uid',  # Single-field primary key
        'org': ['proj_uid', 'task'],  # Composite key: proj_uid and task
        'projects': 'uid',    # Single-field primary key
        'users': 'email',     # Single-field primary key
        'questions': 'uid',   # Single-field primary key
        'candidateprojectmapping': ['candidate_uid', 'project_uid'],  # Composite key
        'projectrecord': ['candidate_uid', 'project_uid', 'task']  # Composite key
    }
    return id_fields.get(table_name, 'id')  # Default to 'id' (single-field primary key)


@anvil.server.callable
def fetch_all_rows(table_name):
    """Fetches all rows from the given table."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()
    # Deserialize JSON fields if applicable
    return [{k: json.loads(v) if isinstance(v, str) and v.startswith('{') else v for k, v in dict(row).items()} for row in rows]


import os
import json
import anvil.server

# Ensure media storage directory exists
MEDIA_DIR = "media_files"
os.makedirs(MEDIA_DIR, exist_ok=True)

@anvil.server.callable
def add_row(table_name, **kwargs):
    """Adds a new row to the given table, including handling media files."""
    conn = get_connection()
    columns = ', '.join(kwargs.keys())
    placeholders = ', '.join('?' for _ in kwargs)

    # Process values and handle media
    processed_values = []
    for key, value in kwargs.items():
        if isinstance(value, anvil.Media):
            # Save media file and store file path in the database
            file_name = f"{table_name}_{key}_{value.name}"
            file_path = os.path.join(MEDIA_DIR, file_name)
            with open(file_path, "wb") as f:
                f.write(value.get_bytes())
            processed_values.append(file_path)
        elif isinstance(value, (dict, list)):
            # Serialize complex types
            processed_values.append(json.dumps(value))
        else:
            processed_values.append(value)

    query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    cur = conn.cursor()

    try:
        print(f"Executing Query: {query} | Values: {processed_values}")  # Debug log
        cur.execute(query, processed_values)
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        print(f"Error while adding row: {e}")
        raise
    finally:
        conn.close()



@anvil.server.callable
def update_row(table_name, primary_key, **new_data):
    """
    Updates all columns of an existing row identified by its primary key(s),
    serializing any complex data types like lists or dictionaries.
    Supports both single-field and composite primary keys.
    """
    conn = get_connection()
    id_fields = get_id_field(table_name)  # May return a single field or multiple fields

    try:
        cur = conn.cursor()

        # Get all columns dynamically
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cur.fetchall()]  # Column names are in the second field

        # Prepare update query dynamically
        updates = []
        values = []

        for column in columns:  # Iterate over all columns
            if column in new_data:
                value = new_data[column]

                # Serialize complex types like lists or dictionaries
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)

                updates.append(f"{column} = ?")
                values.append(value)

        # Handle primary keys
        if isinstance(id_fields, str):  # Single-field primary key
            where_clause = f"{id_fields} = ?"
            if isinstance(primary_key, (list, tuple)):  # Extract single value from list/tuple if needed
                primary_key = primary_key[0]
            values.append(primary_key)
        elif isinstance(id_fields, list):  # Composite primary key
            where_clause = " AND ".join([f"{field} = ?" for field in id_fields])

            # Ensure `primary_key` is a tuple containing all necessary field values
            if not isinstance(primary_key, (tuple, list)) or len(primary_key) != len(id_fields):
                raise ValueError("For composite keys, primary_key must be a tuple with values for all key fields.")

            values.extend(primary_key)

        # Build the query
        query = f"UPDATE {table_name} SET {', '.join(updates)} WHERE {where_clause}"

        # Debug log
        print(f"Executing Query: {query} | Values: {values}")

        # Execute the query
        cur.execute(query, values)
        conn.commit()
        print("Row updated successfully.")

    except Exception as e:
        print(f"Primary Key Value: {primary_key}, Type: {type(primary_key)}")
        print(f"Error while updating row: {e}")
        raise
    finally:
        conn.close()




@anvil.server.callable
def delete_row(table_name, row_id):
    """
    Deletes a row by its unique identifier (primary key).
    Supports both single-field and composite primary keys.
    """
    conn = get_connection()
    id_fields = get_id_field(table_name)  # May return a single field or multiple fields

    try:
        cur = conn.cursor()

        # Handle single-field primary key
        if isinstance(id_fields, str):  # Single-field primary key
            if isinstance(row_id, (list, tuple)):  # Extract single value from list/tuple if needed
                row_id = row_id[0]
            query = f"DELETE FROM {table_name} WHERE {id_fields} = ?"
            print(f"Executing DELETE Query: {query}")
            print(f"With Value: {row_id}")
            cur.execute(query, (row_id,))

        # Handle composite primary key
        elif isinstance(id_fields, list):  # Composite primary key
            if not isinstance(row_id, (tuple, list)) or len(row_id) != len(id_fields):
                raise ValueError("For composite keys, row_id must be a tuple with values for all key fields.")

            conditions = " AND ".join([f"{field} = ?" for field in id_fields])
            query = f"DELETE FROM {table_name} WHERE {conditions}"
            print(f"Executing DELETE Query: {query}")
            print(f"With Values: {row_id}")
            cur.execute(query, tuple(row_id))

        conn.commit()
        print("Row deleted successfully.")

    except Exception as e:
        print(f"Row ID Value: {row_id}, Type: {type(row_id)}")
        print(f"Error while deleting row: {e}")
        raise

    finally:
        conn.close()




@anvil.server.callable
def get_row_by_id(table_name, row_id):
    """
    Fetches a row by its unique identifier (primary key).
    Supports both single-field and composite primary keys.
    """
    conn = get_connection()
    id_fields = get_id_field(table_name)  # May return a single field or multiple fields

    try:
        cur = conn.cursor()

        # Handle single-field primary key
        if len(id_fields) == 1:
            query = f"SELECT * FROM {table_name} WHERE {id_fields[0]} = ?"
            cur.execute(query, (row_id,))
        # Handle composite primary key
        else:
            conditions = " AND ".join([f"{field} = ?" for field in id_fields])
            query = f"SELECT * FROM {table_name} WHERE {conditions}"

            # Ensure `row_id` is a tuple containing all necessary field values
            if not isinstance(row_id, (tuple, list)) or len(row_id) != len(id_fields):
                raise ValueError("For composite keys, row_id must be a tuple with values for all key fields.")

            cur.execute(query, tuple(row_id))

        # Fetch the result
        row = cur.fetchone()

        # Deserialize JSON fields if applicable
        return {k: json.loads(v) if isinstance(v, str) and v.startswith('{') else v for k, v in dict(row).items()} if row else None

    except Exception as e:
        print(f"Error while fetching row: {e}")
        raise

    finally:
        conn.close()

@anvil.server.callable
def get_base_url(port=8000):
    """
    Returns the base URL of the server dynamically.
    - If an environment variable `BASE_URL` is set, it uses that.
    - Otherwise, falls back to the local machine's hostname or IP.
    """
    # Check if a custom base URL is set via environment variable
    base_url = "http://127.0.0.1:8000"
    if base_url:
        return base_url

    # Fallback to the local machine's hostname or IP
    hostname = socket.gethostbyname(socket.gethostname())
    return f"http://{hostname}:{port}"

# Main function to start both servers
if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True  # Stops Flask when the main thread exits
    flask_thread.start()

    print("Flask server running on http://127.0.0.1:8000")

    # Start the Anvil Uplink server
    print("Anvil Uplink server is running...")
    anvil.server.wait_forever()

print("SQLite Uplink server is running...")
anvil.server.wait_forever()
