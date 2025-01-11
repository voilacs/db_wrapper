import json
import anvil.server
from anvil.tables import query as q
from anvil.tables import app_tables as original_app_tables

# Flag to control replication to Anvil Data Tables
REPLICATE_TO_ANVIL = True  # Set to True to enable replication

# Obtain the types of query condition objects
_all_of_type = type(q.all_of())
_any_of_type = type(q.any_of())
_not_type = type(q.not_(None))
_less_than_type = type(q.less_than(0))
_greater_than_type = type(q.greater_than(0))
_less_than_or_equal_type = type(q.less_than_or_equal_to(0))
_greater_than_or_equal_type = type(q.greater_than_or_equal_to(0))

def get_id_field(table_name):
    """
    Returns the unique identifier field(s) based on the table name.
    For tables with composite keys, a list of fields is returned.
    For single-field primary keys, a string is returned.
    """
    id_fields = {
        'candidates': 'uid',  # Single-field primary key
        'org': ['proj_uid', 'task'],  # Composite key
        'projects': 'uid',    # Single-field primary key
        'users': 'email',     # Single-field primary key
        'questions': 'uid',   # Single-field primary key
        'candidateprojectmapping': ['candidate_uid', 'project_uid'],  # Composite key
        'projectrecord': ['candidate_uid', 'project_uid', 'task']  # Composite key
    }
    return id_fields.get(table_name, 'id')  # Default to 'id' (single-field primary key)

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

                # Also update original_app_tables if replication is enabled
                if REPLICATE_TO_ANVIL and self._table_name in dir(original_app_tables):
                    table = getattr(original_app_tables, self._table_name)
                    row = table.get(**{pk_fields: primary_key})
                    if row:
                        row[name] = value

            # Handle composite primary key
            elif isinstance(pk_fields, list):  # Composite primary key
                primary_key = {field: self._row_data[field] for field in pk_fields}
                print(f"Updating {self._table_name}: Composite key {primary_key}, {name} from {old_value} to {value}")
                anvil.server.call('update_row', self._table_name, primary_key, **{name: value})

                # Also update original_app_tables if replication is enabled
                if REPLICATE_TO_ANVIL and self._table_name in dir(original_app_tables):
                    table = getattr(original_app_tables, self._table_name)
                    row = table.get(**primary_key)
                    if row:
                        row[name] = value

    def __setitem__(self, key, value):
        """Allow setting values via subscriptable access (row['key'] = value)."""
        self.__setattr__(key, value)

    def delete(self):
        """Deletes this row from the database."""
        pk_fields = get_id_field(self._table_name)

        # Handle single-field primary key
        if isinstance(pk_fields, str):
            primary_key = self._row_data[pk_fields]
            print(f"Deleting row from {self._table_name} where {pk_fields}={primary_key}")
            anvil.server.call('delete_row', self._table_name, primary_key)

            # Also delete from original_app_tables if replication is enabled
            if REPLICATE_TO_ANVIL and self._table_name in dir(original_app_tables):
                table = getattr(original_app_tables, self._table_name)
                row = table.get(**{pk_fields: primary_key})
                if row:
                    row.delete()

        # Handle composite primary key
        elif isinstance(pk_fields, list):
            primary_key = {field: self._row_data[field] for field in pk_fields}
            print(f"Deleting row from {self._table_name} where composite key {primary_key}")
            anvil.server.call('delete_row', self._table_name, primary_key)

            # Also delete from original_app_tables if replication is enabled
            if REPLICATE_TO_ANVIL and self._table_name in dir(original_app_tables):
                table = getattr(original_app_tables, self._table_name)
                row = table.get(**primary_key)
                if row:
                    row.delete()

    def __getitem__(self, key):
        """Allow dictionary-style access to row data."""
        if key in self._row_data:
            value = self._row_data[key]

            # If it's a file path, build the URL string directly
            if isinstance(value, str) and value.startswith("media_files/"):
                base_url = anvil.server.call("get_base_url")  # Call the Uplink server function
                url = f"{base_url}/{value}"
                print(f"Media URL: {url}")
                return url  # Return the URL string directly to avoid serialization issues
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

class Table:
    """Represents a table in the database."""
    def __init__(self, table_name):
        self._table_name = table_name
        self._original_table = getattr(original_app_tables, table_name, None)

    def add_row(self, **kwargs):
        """Adds a new row to the table."""
        try:
            print(f"Adding row to {self._table_name} with data: {kwargs}")  # Debug log
            row_id = anvil.server.call('add_row', self._table_name, **kwargs)

            # Also add to original_app_tables if replication is enabled
            if REPLICATE_TO_ANVIL and self._table_name in dir(original_app_tables):
                table = getattr(original_app_tables, self._table_name)
                table.add_row(**kwargs)

            # Get primary key(s)
            pk_fields = get_id_field(self._table_name)

            # Handle single-field primary key
            if isinstance(pk_fields, str):
                return self.get(**{pk_fields: row_id})

            # Handle composite primary key
            elif isinstance(pk_fields, list):
                composite_key_values = {field: kwargs[field] for field in pk_fields if field in kwargs}
                return self.get(**composite_key_values)

        except Exception as e:
            print(f"Error adding row to {self._table_name}: {e}")
            raise

    def get(self, **conditions):
        """Fetches a single row matching the given conditions."""
        try:
            print(f"Fetching row from {self._table_name} with conditions: {conditions}")  # Debug log
            rows = self.search(**conditions)
            return rows[0] if rows else None
        except Exception as e:
            print(f"Error fetching row from {self._table_name}: {e}")
            raise

    def search(self, *args, **conditions):
        """Fetches all rows matching the given conditions."""
        try:
            print(f"Searching rows in {self._table_name} with conditions: {conditions} and args: {args}")  # Debug log
            all_rows = anvil.server.call('fetch_all_rows', self._table_name)
            filtered_rows = [
                LiveRow(self._table_name, row)
                for row in all_rows if self._matches_conditions(row, args, conditions)
            ]
            print(f"Found {len(filtered_rows)} matching rows in {self._table_name}")  # Debug log
            return filtered_rows
        except Exception as e:
            print(f"Error searching rows in {self._table_name}: {e}")
            raise

    def _matches_conditions(self, row, args, conditions):
        """Check if a row matches the provided positional and keyword conditions."""
        # First, evaluate positional conditions
        for condition in args:
            if not self._evaluate_condition_on_row(row, condition):
                return False
        # Next, evaluate keyword conditions
        for field, condition in conditions.items():
            field_value = row.get(field)
            if not self._evaluate_condition(field_value, condition):
                return False
        return True

    def _evaluate_condition_on_row(self, row, condition):
        """Recursively evaluate a condition that may involve multiple fields in the row."""
        condition_type_name = condition.__class__.__name__
        if condition_type_name == 'all_of':
            return all(self._evaluate_condition_on_row(row, sub_condition) for sub_condition in condition.args)
        elif condition_type_name == 'any_of':
            return any(self._evaluate_condition_on_row(row, sub_condition) for sub_condition in condition.args)
        elif condition_type_name == 'not_':
            return not self._evaluate_condition_on_row(row, condition.arg)
        elif isinstance(condition, dict):
            # Condition is a mapping from field names to conditions
            return self._evaluate_field_conditions(row, condition)
        else:
            raise ValueError(f"Unsupported condition format: {condition}")

    def _evaluate_field_conditions(self, row, field_conditions):
        """Evaluate conditions that are mappings from field names to conditions."""
        for field, condition in field_conditions.items():
            field_value = row.get(field)
            if not self._evaluate_condition(field_value, condition):
                return False
        return True

    def _evaluate_condition(self, field_value, condition):
        """Evaluate a condition on a specific field value."""
        if isinstance(condition, _less_than_type):
            return field_value < condition.arg
        elif isinstance(condition, _less_than_or_equal_type):
            return field_value <= condition.arg
        elif isinstance(condition, _greater_than_type):
            return field_value > condition.arg
        elif isinstance(condition, _greater_than_or_equal_type):
            return field_value >= condition.arg
        elif isinstance(condition, _not_type):
            # Apply not_ to a field condition
            return not self._evaluate_condition(field_value, condition.arg)
        elif isinstance(condition, list):
            # Condition is a list of possible values
            return field_value in condition
        else:
            # Treat condition as a simple value for equality check
            return field_value == condition

class AppTablesWrapper:
    """Dynamically wraps database tables to mimic Anvil's app_tables interface."""
    def __getattr__(self, table_name):
        return Table(table_name)

# Create a global app_tables instance
app_tables = AppTablesWrapper()
