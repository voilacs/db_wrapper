# **db_wrapper**
A database wrapper for Anvil that uses an `sqlite3` database instead of the Anvil DB.

## **Overview**
This wrapper allows you to use a local `sqlite3` database as a replacement for the default Anvil database, enabling local storage and more flexibility in handling data. Media files are stored in a directory alongside the server, and data migrations are performed seamlessly.

---

## **Setup and Usage**

### **1. Run the Migration Script**
When using the SQLite server for the first time, migrate your existing data from the Anvil DB to the local SQLite database.

python migration_script.py
The migration process may take 2-3 minutes depending on the size of your database.
Once the migration is complete, manually stop the process (Ctrl + C on most systems).

2. Start the Uplink Server
Run the Uplink server to handle database interactions and media file management.

python uplink_server.py

Steps:

Configure the following parameters in uplink_server.py:
UPLINK_KEY: Your Anvil Uplink key.
BASE_URL: The URL for accessing your server (e.g., http://localhost:8000 or your cloud-hosted server URL).
Ensure the media_files directory is in the same location as uplink_server.py. This directory will store media files uploaded to the database.
Start the server. The Uplink server will listen for requests from your Anvil app.
3. Update Your Anvil App
To use the SQLite wrapper in your Anvil app, replace all instances of the app_tables import with the wrapper.

Before:

from anvil.tables import app_tables
After:

from .wrapper import app_tables
This ensures that your app interacts with the SQLite database through the wrapper.

Features
SQLite Integration: Uses a local SQLite database instead of the Anvil DB for all data operations.
Media File Handling: Automatically stores and retrieves media files from a local directory (media_files).
Seamless Migration: Migrates existing data from the Anvil DB to SQLite with minimal setup.
Dynamic URL Management: Supports dynamic BASE_URL configuration for local and cloud environments.
Project Structure
migration_script.py: Migrates data from Anvil DB to the SQLite database.
uplink_server.py: Handles SQLite database interactions and serves media files.
wrapper.py: Provides a seamless interface for accessing the SQLite database as app_tables.
media_files/: Directory for storing media files (automatically created if not present).
Troubleshooting
Migration Taking Too Long: Ensure the Anvil DB connection is stable, and restart the process if necessary.

Media Files Not Accessible: Verify the BASE_URL configuration and ensure the media_files directory is present and writable.

Database Access Errors: Ensure the Uplink server is running and accessible by the Anvil app.

Contributors
Anmol Adarsh Kumar: anmol22081@iiitd.ac.in
License
Use as you want no license and guarantees
