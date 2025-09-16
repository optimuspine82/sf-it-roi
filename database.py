# database.py
import sqlite3
import pandas as pd
import streamlit as st
import datetime

DB_FILE = "portfolio.db"

# --- HELPER: Rebuild Tables ---
def rebuild_applications_table(con):
    cur = con.cursor()
    cur.execute("ALTER TABLE applications RENAME TO applications_old")
    cur.execute("""
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, it_unit_id INTEGER, vendor_id INTEGER,
            renewal_date TEXT, annual_cost REAL, service_type_id INTEGER, category_id INTEGER,
            integrations TEXT, description TEXT, similar_applications TEXT, service_owner TEXT
        )
    """)
    cur.execute("""
        INSERT INTO applications (id, name, it_unit_id, vendor_id, renewal_date, annual_cost,
                                  service_type_id, category_id, integrations, description,
                                  similar_applications, service_owner)
        SELECT id, name, it_unit_id, vendor_id, renewal_date, annual_cost,
               service_type_id, category_id, integrations,
               COALESCE(description, other_units),
               similar_applications, service_owner
        FROM applications_old
    """)
    cur.execute("DROP TABLE applications_old")
    con.commit()

def rebuild_services_table(con):
    """Safely rebuilds the it_services table to remove the UNIQUE constraint on the name column."""
    cur = con.cursor()
    cur.execute("ALTER TABLE it_services RENAME TO it_services_old")
    cur.execute("""
        CREATE TABLE it_services (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT, it_unit_id INTEGER, 
            fte_count INTEGER, dependencies TEXT, service_owner TEXT, status TEXT, 
            sla_level_id INTEGER, service_method_id INTEGER, budget_allocation REAL
        )
    """)
    cur.execute("""
        INSERT INTO it_services (id, name, description, it_unit_id, fte_count, dependencies, 
                                 service_owner, status, sla_level_id, service_method_id, budget_allocation)
        SELECT id, name, description, it_unit_id, fte_count, dependencies, 
               service_owner, status, sla_level_id, service_method_id, budget_allocation
        FROM it_services_old
    """)
    cur.execute("DROP TABLE it_services_old")
    con.commit()


# --- DATABASE SETUP & MIGRATION ---
def init_db():
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()

        # --- IT Units Table ---
        cur.execute("CREATE TABLE IF NOT EXISTS it_units (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        cur.execute("PRAGMA table_info(it_units)")
        existing_columns = [info[1] for info in cur.fetchall()]
        required_it_unit_columns = { "contact_person": "TEXT", "contact_email": "TEXT", "notes": "TEXT", "total_fte": "INTEGER", "budget_amount": "REAL" }
        for col, col_type in required_it_unit_columns.items():
            if col not in existing_columns:
                cur.execute(f"ALTER TABLE it_units ADD COLUMN {col} {col_type}")

        # --- Lookup Tables ---
        for table in ['vendors', 'service_types', 'categories', 'sla_levels', 'service_methods']:
            cur.execute(f'''CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')

        # --- Applications Table ---
        cur.execute("CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        cur.execute("PRAGMA table_info(applications)")
        app_columns = [info[1] for info in cur.fetchall()]
        if 'other_units' in app_columns and 'description' in app_columns:
            rebuild_applications_table(con)
        elif 'other_units' in app_columns and 'description' not in app_columns:
            cur.execute("ALTER TABLE applications RENAME COLUMN other_units TO description")
        
        cur.execute("PRAGMA table_info(applications)")
        app_columns_final = [info[1] for info in cur.fetchall()]
        required_app_columns = { "it_unit_id": "INTEGER", "vendor_id": "INTEGER", "renewal_date": "TEXT", "annual_cost": "REAL", "service_type_id": "INTEGER", "category_id": "INTEGER", "integrations": "TEXT", "description": "TEXT", "similar_applications": "TEXT", "service_owner": "TEXT" }
        for col, col_type in required_app_columns.items():
            if col not in app_columns_final:
                cur.execute(f"ALTER TABLE applications ADD COLUMN {col} {col_type}")

        # --- IT Services Table ---
        cur.execute("CREATE TABLE IF NOT EXISTS it_services (id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT)")
        cur.execute("PRAGMA index_list('it_services')")
        indexes = [row[1] for row in cur.fetchall() if row[1].startswith('sqlite_autoindex_it_services')]
        if indexes: # If an auto-index for a UNIQUE constraint exists
            rebuild_services_table(con)

        cur.execute("PRAGMA table_info(it_services)")
        it_services_columns = [info[1] for info in cur.fetchall()]
        required_it_services_columns = { "it_unit_id": "INTEGER", "fte_count": "INTEGER", "dependencies": "TEXT", "service_owner": "TEXT", "status": "TEXT", "sla_level_id": "INTEGER", "service_method_id": "INTEGER", "budget_allocation": "REAL" }
        for col, col_type in required_it_services_columns.items():
            if col not in it_services_columns:
                cur.execute(f"ALTER TABLE it_services ADD COLUMN {col} {col_type}")

        # --- Infrastructure Table ---
        cur.execute("CREATE TABLE IF NOT EXISTS infrastructure (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        cur.execute("PRAGMA table_info(infrastructure)")
        infra_columns = [info[1] for info in cur.fetchall()]
        if 'notes' in infra_columns and 'description' not in infra_columns:
            cur.execute("ALTER TABLE infrastructure RENAME COLUMN notes TO description")
        
        cur.execute("PRAGMA table_info(infrastructure)")
        infra_columns_final = [info[1] for info in cur.fetchall()]
        required_infra_columns = { "it_unit_id": "INTEGER", "vendor_id": "INTEGER", "location": "TEXT", "status": "TEXT", "purchase_date": "TEXT", "warranty_expiry": "TEXT", "annual_maintenance_cost": "REAL", "description": "TEXT" }
        for col, col_type in required_infra_columns.items():
            if col not in infra_columns_final:
                cur.execute(f"ALTER TABLE infrastructure ADD COLUMN {col} {col_type}")
        
        # --- Audit Log Table ---
        cur.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, user_email TEXT NOT NULL,
                action TEXT NOT NULL, item_type TEXT NOT NULL, item_name TEXT NOT NULL, details TEXT
            )''')

        con.commit()
    except sqlite3.Error as e:
        st.error(f"Database error during initialization: {e}")
    finally:
        if con:
            con.close()

# The rest of the database.py file remains the same...
def get_connection():
    return sqlite3.connect(DB_FILE)
# ... all other CRUD functions (add_it_unit, get_applications, etc.) are unchanged.