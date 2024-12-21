# Place this wrapper inside your anvil application and replace all app_tables import statements 
# to use the app_tables from this file instead

import anvil.server
import json
import anvil.server
import json
class MediaURL:
    """Wrapper for media URLs to provide a .url attribute."""
    def __init__(self, url):
        self._url = url

    @property
    def url(self):
        return self._url

    def __str__(self):
        return self._url  # Fallback for string representation
class LiveRow:
    """Represents a live row object that synchronizes with the database."""

    def __init__(self, table_name, row_data):
        self._table_name = table_name
        self._row_data = self._deserialize(row_data)

    def __getattr__(self, name):
        """Allow attribute-style access."""
        if name in self._row_data:
            return self._row_data[name]
        raise AttributeError(f"{name} not found in row")

    def __setattr__(self, name, value):
        """Update value and sync to the database."""
        if name in ['_table_name', '_row_data']:
            super().__setattr__(name, value)
        else:
            old_value = self._row_data.get(name, None)  # Get old value
            self._row_data[name] = value
    
            # Get primary key(s)
            pk_fields = get_id_field(self._table_name)
    
            # Handle single-field primary key
            if isinstance(pk_fields, str):  # Single primary key field
                primary_key = self._row_data[pk_fields]
                print(f"Updating {self._table_name}: {pk_fields}={primary_key}, {name} from {old_value} to {value}")
                anvil.server.call('update_row', self._table_name, primary_key, **{name: value})
    
            # Handle composite primary key
            elif isinstance(pk_fields, list):  # Composite primary key
                primary_key = tuple(self._row_data[field] for field in pk_fields)
                print(f"Updating {self._table_name}: Composite key {pk_fields}={primary_key}, {name} from {old_value} to {value}")
                anvil.server.call('update_row', self._table_name, primary_key, **{name: value})


    def __setitem__(self, key, value):
        """Allow setting values via subscriptable access (row['key'] = value)."""
        old_value = self._row_data.get(key, None)  # Fetch the current value of the key
    
        # Update local copy of the row data
        self._row_data[key] = value
    
        # Determine the primary key(s) and its value(s)
        pk_fields = get_id_field(self._table_name)
    
        # Handle single-field primary key
        if isinstance(pk_fields, str):  # Single primary key
            primary_key = self._row_data[pk_fields]
            print(f"Updating {self._table_name}: {pk_fields}={primary_key}, {key} from {old_value} to {value}")
            anvil.server.call('update_row', self._table_name, primary_key, **self._row_data)
    
        # Handle composite primary key
        elif isinstance(pk_fields, list):  # Composite primary key
            primary_key = tuple(self._row_data[field] for field in pk_fields)
            print(f"Updating {self._table_name}: Composite key {pk_fields}={primary_key}, {key} from {old_value} to {value}")
            anvil.server.call('update_row', self._table_name, primary_key, **self._row_data)






    # Remaining methods unchanged...


    def delete(self):
        """Deletes this row from the database."""
        pk_fields = get_id_field(self._table_name)  # Get primary key(s)
    
        # Handle single-field primary key
        if isinstance(pk_fields, str):
            primary_key = self._row_data[pk_fields]
            print(f"Deleting row from {self._table_name} where {pk_fields}={primary_key}")
            anvil.server.call('delete_row', self._table_name, primary_key)
    
        # Handle composite primary key
        elif isinstance(pk_fields, list):
            primary_key = tuple(self._row_data[field] for field in pk_fields)
            print(f"Deleting row from {self._table_name} where composite key {pk_fields}={primary_key}")
            anvil.server.call('delete_row', self._table_name, primary_key)


    def __getitem__(self, key):
        """Allow dictionary-style access to row data."""
        if key in self._row_data:
            value = self._row_data[key]

            # If it's a file path, convert it to a MediaURL object
            if isinstance(value, str) and value.startswith("media_files/"):
                base_url = anvil.server.call("get_base_url")  # Call the Uplink server function
                url = f"{base_url}/{value}"
                print(url)
                return MediaURL(url)
            return value
        raise KeyError(f"Key {key} not found in row")

    def __iter__(self):
        """Allow iteration over the row's attributes and values."""
        return iter(self._row_data.items())

    def items(self):
        """Returns the items of the row as key-value pairs."""
        return self._row_data.items()

    def keys(self):
        """Returns the keys of the row."""
        return self._row_data.keys()

    def values(self):
        """Returns the values of the row."""
        return self._row_data.values()

    def __repr__(self):
        """Custom string representation for easier inspection."""
        return f"LiveRow({self._table_name}, {self._row_data})"

    def __len__(self):
        """Returns the number of keys in the row."""
        return len(self._row_data)

    def to_dict(self):
        """Explicitly converts the LiveRow to a dictionary."""
        return dict(self._row_data)

    def _deserialize(self, row_data):
        """
        Recursively convert serialized strings in row_data to dictionaries, where applicable.
        """
        for key, value in row_data.items():
            if isinstance(value, str):
                try:
                    # Attempt to load the string as JSON (to handle dictionaries stored as JSON strings)
                    row_data[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # If not JSON, leave it as-is (i.e., treat it as a string)
                    pass
            elif isinstance(value, dict):
                # Recursively deserialize dictionaries
                row_data[key] = self._deserialize(value)
        return row_data


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




class Table:
    """Represents a table in the database."""
    def __init__(self, table_name):
        self._table_name = table_name

    def add_row(self, **kwargs):
        """Adds a new row to the table."""
        # Add a new row using the provided data
        row_id = anvil.server.call('add_row', self._table_name, **kwargs)
    
        # Get primary key(s)
        pk_fields = get_id_field(self._table_name)
    
        # Handle single-field primary key
        if isinstance(pk_fields, str):
            return self.get(**{pk_fields: row_id})
    
        # Handle composite primary key
        elif isinstance(pk_fields, list):
            # Extract the primary key values from `kwargs` using the composite fields
            composite_key_values = {field: kwargs[field] for field in pk_fields if field in kwargs}
    
            # Return the row based on the composite primary key values
            return self.get(**composite_key_values)


    def get(self, **conditions):
        """Fetches a single row matching the given conditions."""
        rows = self.search(**conditions)
        return rows[0] if rows else None

    def search(self, **conditions):
        """Fetches all rows matching the given conditions."""
        all_rows = anvil.server.call('fetch_all_rows', self._table_name)
        filtered_rows = [
            row for row in all_rows if all(row.get(k) == v for k, v in conditions.items())
        ]
        return [LiveRow(self._table_name, row) for row in filtered_rows]


class AppTablesWrapper:
    """Dynamically wraps database tables to mimic Anvil's app_tables interface."""
    def __getattr__(self, table_name):
        return Table(table_name)


# Create a global `app_tables` instance
app_tables = AppTablesWrapper()
