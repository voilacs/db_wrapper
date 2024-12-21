import sqlite3
import anvil.server
import json
from anvil.tables import app_tables
import os

# Define constants
MEDIA_STORAGE_DIR = "media_files"  # Directory to store media files

# Ensure the media storage directory exists
os.makedirs(MEDIA_STORAGE_DIR, exist_ok=True)

def save_media_to_file(media_obj, column_name, row_id):
    """
    Save the media object to a local file and return the file path.
    """
    if media_obj is not None:
        # Generate a unique file name using the row ID and column name
        file_name = f"{row_id}_{column_name}_{media_obj.name}"
        file_path = os.path.join(MEDIA_STORAGE_DIR, file_name)

        # Write the media content to the file
        with open(file_path, "wb") as f:
            f.write(media_obj.get_bytes())
        
        return file_path
    return None

# Connect to Anvil Uplink
UPLINK_KEY = "6KUJ6DMX7YKU4WZESHXOQ4H4-2U6IUMDW77ZIX6OY"
anvil.server.connect(UPLINK_KEY)

# Local SQLite Database Path
LOCAL_DB_PATH = "local.db"


# Hard-coded list of tables to be migrated
TABLES_TO_MIGRATE = ["projects","users","candidateprojectmapping","candidates","org","projectrecord","questions","users"]  # Replace with your actual table names

@anvil.server.callable
def sync_schema_with_anvil(table_name):
    """
    Synchronize the schema of a specific Anvil table with the local SQLite database.
    """
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()

    # Get Anvil table schema and data
    anvil_table = getattr(app_tables, table_name)
    anvil_schema = {col['name']: col['type'] for col in anvil_table.list_columns()}

    # Get local table schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    local_schema = {row[1]: row[2] for row in cursor.fetchall()}  # {column_name: column_type}

    # If the table doesn't exist or is incomplete, recreate or modify it
    if not local_schema:
        columns = ", ".join(f"{col} {dtype}" for col, dtype in anvil_schema.items())
        cursor.execute(f"CREATE TABLE {table_name} ({columns})")
        print(f"Created table '{table_name}' with schema: {anvil_schema}")
    else:
        # Add missing columns
        for col, dtype in anvil_schema.items():
            if col not in local_schema:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {dtype}")
                print(f"Added column '{col}' to table '{table_name}'.")

    conn.commit()
    conn.close()

@anvil.server.callable
def migrate_table_data(table_name):
    """
    Migrate all data from a specific Anvil table to the local SQLite database.
    """
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()

    try:
        # Dynamically access the Anvil table using getattr
        anvil_table = getattr(app_tables, table_name)
        rows = [dict(row) for row in anvil_table.search()]

        if rows:
            # Get column names and prepare SQL for insertion
            columns = ", ".join(rows[0].keys())
            placeholders = ", ".join("?" for _ in rows[0])

            # Clear the local table
            cursor.execute(f"DELETE FROM {table_name}")

            # Insert data into the local table
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            for row_id, row in enumerate(rows, start=1):
                processed_row = []

                for column, value in row.items():
                    # Handle media files
                    if isinstance(value, anvil.Media):
                        file_path = save_media_to_file(value, column, row_id)
                        processed_row.append(file_path)
                    # Serialize unsupported types
                    elif isinstance(value, (dict, list)):
                        processed_row.append(json.dumps(value))
                    else:
                        processed_row.append(value)
                
                # Insert the processed row into the local database
                cursor.execute(query, tuple(processed_row))
            
            print(f"Migrated {len(rows)} rows to table '{table_name}'.")

        else:
            print(f"No data found in table '{table_name}' to migrate.")

        # Commit changes
        conn.commit()

    except Exception as e:
        print(f"Error while migrating table '{table_name}': {e}")
    print(f"Data migrated for table '{table_name}'.")
    conn.commit()
    conn.close()
    

@anvil.server.callable
def migrate_selected_tables(tables):
    """
    Migrate only the selected tables from Anvil to the local SQLite database.
    """
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()

    for table_name in tables:
        print(f"Processing table: {table_name}")

        # Sync schema
        sync_schema_with_anvil(table_name)

        # Migrate data
        migrate_table_data(table_name)

    conn.close()
    print("Migration for selected tables completed successfully.")

# Call the functions directly within the script
if __name__ == "__main__":
    print("Starting migration process for selected tables...")

    # Call the migration for the specified tables
    migrate_selected_tables(TABLES_TO_MIGRATE)

    print("Migration process completed successfully.")
    
    # Example: Print data from a specific table (optional)
    # print_table_data("example_table_name")

# Wait forever to keep the server alive for remote calls (optional)
anvil.server.wait_forever()