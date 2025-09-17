# database.py
import sqlite3
import pandas as pd
import streamlit as st
import datetime

DB_FILE = "portfolio.db"

# --- HELPER: Rebuild Tables ---
def rebuild_applications_table(con):
    """Safely rebuilds the applications table."""
    cur = con.cursor()
    cur.execute("ALTER TABLE applications RENAME TO applications_old")
    cur.execute("""
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, it_unit_id INTEGER, vendor_id INTEGER,
            renewal_date TEXT, annual_cost REAL, service_type_id INTEGER, category_id INTEGER,
            integrations TEXT, description TEXT, similar_applications TEXT, service_owner TEXT,
            status TEXT
        )
    """)
    cur.execute("""
        INSERT INTO applications (id, name, it_unit_id, vendor_id, renewal_date, annual_cost,
                                  service_type_id, category_id, integrations, description,
                                  similar_applications, service_owner, status)
        SELECT id, name, it_unit_id, vendor_id, renewal_date, annual_cost,
               service_type_id, category_id, integrations,
               COALESCE(description, other_units),
               similar_applications, service_owner, status
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
    """Initializes the SQLite database and creates/updates tables as needed."""
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()

        # --- IT Units Table ---
        cur.execute("CREATE TABLE IF NOT EXISTS it_units (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        cur.execute("PRAGMA table_info(it_units)")
        existing_columns = [info[1] for info in cur.fetchall()]
        required_it_unit_columns = {
            "contact_person": "TEXT", "contact_email": "TEXT", "notes": "TEXT",
            "total_fte": "INTEGER", "budget_amount": "REAL"
        }
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
        required_app_columns = {
            "it_unit_id": "INTEGER", "vendor_id": "INTEGER", "renewal_date": "TEXT", "annual_cost": "REAL", 
            "service_type_id": "INTEGER", "category_id": "INTEGER", "integrations": "TEXT", 
            "description": "TEXT", "similar_applications": "TEXT", "service_owner": "TEXT", "status": "TEXT"
        }
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
        required_it_services_columns = {
            "it_unit_id": "INTEGER", "fte_count": "INTEGER", "dependencies": "TEXT", "service_owner": "TEXT", 
            "status": "TEXT", "sla_level_id": "INTEGER", "service_method_id": "INTEGER", "budget_allocation": "REAL"
        }
        for col, col_type in required_it_services_columns.items():
            if col not in it_services_columns:
                cur.execute(f"ALTER TABLE it_services ADD COLUMN {col} {col_type}")

        # --- Infrastructure Table ---
        cur.execute("CREATE TABLE IF NOT EXISTS infrastructure (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        cur.execute("PRAGMA table_info(infrastructure)")
        infra_columns = [info[1] for info in cur.fetchall()]
        if 'notes' in infra_columns and 'description' not in infra_columns:
            cur.execute("ALTER TABLE infrastructure RENAME COLUMN notes TO description")
        
        # NOTE: purchase_date and warranty_expiry are intentionally left out of the required columns
        # as they are being removed. No new migration is needed; they will just become unused.
        cur.execute("PRAGMA table_info(infrastructure)")
        infra_columns_final = [info[1] for info in cur.fetchall()]
        required_infra_columns = {
            "it_unit_id": "INTEGER", "vendor_id": "INTEGER", "location": "TEXT", "status": "TEXT", 
            "annual_maintenance_cost": "REAL", "description": "TEXT"
        }
        for col, col_type in required_infra_columns.items():
            if col not in infra_columns_final:
                cur.execute(f"ALTER TABLE infrastructure ADD COLUMN {col} {col_type}")
        
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

# --- DATABASE HELPER FUNCTIONS ---
def get_connection():
    return sqlite3.connect(DB_FILE)

def log_change(user_email, action, item_type, item_name, details=""):
    with get_connection() as con:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        con.execute(
            """INSERT INTO audit_log (timestamp, user_email, action, item_type, item_name, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (timestamp, user_email, action, item_type, item_name, details)
        )
        con.commit()

# --- IT UNIT FUNCTIONS ---
def get_it_units():
    with get_connection() as con:
        return pd.read_sql_query("SELECT id, name FROM it_units ORDER BY name", con)

def get_it_unit_details(unit_id):
    with get_connection() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM it_units WHERE id = ?", (unit_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def add_it_unit(user_email, name, contact_person, contact_email="", total_fte=0, budget_amount=0.0, notes="", bulk=False):
    if not name or not contact_person:
        return "Unit Name and Contact Person are required."
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id FROM it_units WHERE name = ?", (name,))
        if cur.fetchone():
            return f"IT Unit '{name}' already exists."
        cur.execute(
            "INSERT INTO it_units (name, contact_person, contact_email, total_fte, budget_amount, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (name, contact_person, contact_email, total_fte, budget_amount, notes)
        )
        con.commit()
        log_change(user_email, "CREATE", "IT Unit", name, details="Bulk Import" if bulk else "")
        if not bulk: st.success(f"Added new IT Unit: {name}")
        return True

def update_it_unit_details(user_email, unit_id, name, contact_person, contact_email, total_fte, budget_amount, notes):
    if not name or not contact_person:
        return "Unit Name and Contact Person cannot be empty."
    with get_connection() as con:
        con.execute(
            "UPDATE it_units SET name = ?, contact_person = ?, contact_email = ?, total_fte = ?, budget_amount = ?, notes = ? WHERE id = ?",
            (name, contact_person, contact_email, total_fte, budget_amount, notes, unit_id)
        )
        con.commit()
        log_change(user_email, "UPDATE", "IT Unit", name)
        return True

def delete_it_unit(user_email, unit_id, unit_name):
    with get_connection() as con:
        con.execute("DELETE FROM it_units WHERE id = ?", (unit_id,))
        for table in ['applications', 'it_services', 'infrastructure']:
            con.execute(f"UPDATE {table} SET it_unit_id = NULL WHERE it_unit_id = ?", (unit_id,))
        con.commit()
        log_change(user_email, "DELETE", "IT Unit", unit_name)

# --- LOOKUP TABLE FUNCTIONS ---
def get_lookup_data(table_name):
    with get_connection() as con:
        return pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY name", con)

def add_lookup_item(user_email, table_name, name):
    with get_connection() as con:
        con.execute(f"INSERT INTO {table_name} (name) VALUES (?)", (name,))
        con.commit()
        log_change(user_email, "CREATE", f"Lookup: {table_name}", name)

def update_lookup_item(user_email, table_name, item_id, new_name):
    with get_connection() as con:
        con.execute(f"UPDATE {table_name} SET name = ? WHERE id = ?", (new_name, item_id))
        con.commit()
        log_change(user_email, "UPDATE", f"Lookup: {table_name}", new_name)

def delete_lookup_item(user_email, table_name, item_id, item_name):
    with get_connection() as con:
        con.execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
        con.commit()
        log_change(user_email, "DELETE", f"Lookup: {table_name}", item_name)

# --- APPLICATION FUNCTIONS ---
def get_applications():
    with get_connection() as con:
        query = """
            SELECT a.id, a.name, iu.name as managing_it_unit, v.name as vendor, 
                   st.name as type, c.name as category, a.annual_cost, a.renewal_date, 
                   a.similar_applications, a.service_owner, a.status
            FROM applications a
            LEFT JOIN it_units iu ON a.it_unit_id = iu.id
            LEFT JOIN vendors v ON a.vendor_id = v.id
            LEFT JOIN service_types st ON a.service_type_id = st.id
            LEFT JOIN categories c ON a.category_id = c.id
            ORDER BY a.name
        """
        return pd.read_sql_query(query, con)

def get_application_details(app_id):
    with get_connection() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def add_application(user_email, name, it_unit_id, vendor_id, category_id, service_type_id, annual_cost, renewal_date, integrations, description, similar_apps, service_owner, status, bulk=False):
    if not all([name, it_unit_id, vendor_id, category_id]):
        return "Application Name, Managing IT Unit, Vendor, and Category are required."
    with get_connection() as con:
        con.execute(
            """INSERT INTO applications (name, it_unit_id, vendor_id, category_id, service_type_id, annual_cost, renewal_date, integrations, description, similar_applications, service_owner, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, it_unit_id, vendor_id, category_id, service_type_id, annual_cost, renewal_date, integrations, description, similar_apps, service_owner, status)
        )
        con.commit()
        log_change(user_email, "CREATE", "Application", name, details="Bulk Import" if bulk else "")
        if not bulk: st.success(f"Added application: {name}")
        return True

def update_application(user_email, app_id, name, it_unit_id, vendor_id, category_id, service_type_id, annual_cost, renewal_date, integrations, description, similar_apps, service_owner, status):
    if not all([name, it_unit_id, vendor_id, category_id]):
        return "Application Name, Managing IT Unit, Vendor, and Category cannot be empty."
    with get_connection() as con:
        con.execute(
            """UPDATE applications SET name=?, it_unit_id=?, vendor_id=?, category_id=?, service_type_id=?, annual_cost=?, 
               renewal_date=?, integrations=?, description=?, similar_applications=?, service_owner=?, status=? WHERE id=?""",
            (name, it_unit_id, vendor_id, category_id, service_type_id, annual_cost, renewal_date, integrations, description, similar_apps, service_owner, status, app_id)
        )
        con.commit()
        log_change(user_email, "UPDATE", "Application", name)
        return True

def delete_application(user_email, app_id, app_name):
    with get_connection() as con:
        con.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        con.commit()
        log_change(user_email, "DELETE", "Application", app_name)
        
# --- IT SERVICE FUNCTIONS ---
def get_it_services():
    with get_connection() as con:
        query = """
            SELECT its.id, its.name, iu.name as providing_it_unit, its.status,
                   its.service_owner, its.fte_count, sl.name as sla_level, 
                   sm.name as service_method, its.budget_allocation
            FROM it_services its
            LEFT JOIN it_units iu ON its.it_unit_id = iu.id
            LEFT JOIN sla_levels sl ON its.sla_level_id = sl.id
            LEFT JOIN service_methods sm ON its.service_method_id = sm.id
            ORDER BY its.name
        """
        return pd.read_sql_query(query, con)

def get_it_service_details(service_id):
    with get_connection() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM it_services WHERE id = ?", (service_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def add_it_service(user_email, name, it_unit_id, desc="", fte=0, deps="", owner="", status="", sla_id=None, method_id=None, budget=0.0, bulk=False):
    if not name or not it_unit_id:
        return "Service Name and Providing IT Unit are required."
    with get_connection() as con:
        con.execute(
            """INSERT INTO it_services (name, it_unit_id, description, fte_count, dependencies, service_owner, status, sla_level_id, service_method_id, budget_allocation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, it_unit_id, desc, fte, deps, owner, status, sla_id, method_id, budget)
        )
        con.commit()
        log_change(user_email, "CREATE", "IT Service", name, details="Bulk Import" if bulk else "")
        if not bulk: st.success(f"Added service: {name}")
        return True

def update_it_service(user_email, service_id, name, it_unit_id, desc, fte, deps, owner, status, sla_id, method_id, budget):
    if not name or not it_unit_id:
        return "Service Name and Providing IT Unit cannot be empty."
    with get_connection() as con:
        con.execute(
            """UPDATE it_services SET name=?, it_unit_id=?, description=?, fte_count=?, dependencies=?, 
               service_owner=?, status=?, sla_level_id=?, service_method_id=?, budget_allocation=? WHERE id = ?""",
            (name, it_unit_id, desc, fte, deps, owner, status, sla_id, method_id, budget, service_id)
        )
        con.commit()
        log_change(user_email, "UPDATE", "IT Service", name)
        return True

def delete_it_service(user_email, service_id, service_name):
    with get_connection() as con:
        con.execute("DELETE FROM it_services WHERE id = ?", (service_id,))
        con.commit()
        log_change(user_email, "DELETE", "IT Service", service_name)

# --- INFRASTRUCTURE FUNCTIONS ---
def get_infrastructure():
    with get_connection() as con:
        query = """
            SELECT i.id, i.name, iu.name as managing_it_unit, v.name as vendor, i.location, 
                   i.status, i.annual_maintenance_cost
            FROM infrastructure i
            LEFT JOIN it_units iu ON i.it_unit_id = iu.id
            LEFT JOIN vendors v ON i.vendor_id = v.id
            ORDER BY i.name
        """
        return pd.read_sql_query(query, con)

def get_infrastructure_details(infra_id):
    with get_connection() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM infrastructure WHERE id = ?", (infra_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def add_infrastructure(user_email, name, it_unit_id, vendor_id=None, location="", status="", cost=0.0, description="", bulk=False):
    if not name or not it_unit_id:
        return "Infrastructure Name and Managing IT Unit are required."
    with get_connection() as con:
        con.execute(
            """INSERT INTO infrastructure (name, it_unit_id, vendor_id, location, status, annual_maintenance_cost, description)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, it_unit_id, vendor_id, location, status, cost, description)
        )
        con.commit()
        log_change(user_email, "CREATE", "Infrastructure", name, details="Bulk Import" if bulk else "")
        if not bulk: st.success(f"Added infrastructure: {name}")
        return True

def update_infrastructure(user_email, infra_id, name, it_unit_id, vendor_id, location, status, cost, description):
    if not name or not it_unit_id:
        return "Infrastructure Name and Managing IT Unit cannot be empty."
    with get_connection() as con:
        con.execute(
            """UPDATE infrastructure SET name=?, it_unit_id=?, vendor_id=?, location=?, status=?, 
               annual_maintenance_cost=?, description=? WHERE id = ?""",
            (name, it_unit_id, vendor_id, location, status, cost, description, infra_id)
        )
        con.commit()
        log_change(user_email, "UPDATE", "Infrastructure", name)
        return True

def delete_infrastructure(user_email, infra_id, infra_name):
    with get_connection() as con:
        con.execute("DELETE FROM infrastructure WHERE id = ?", (infra_id,))
        con.commit()
        log_change(user_email, "DELETE", "Infrastructure", infra_name)

# --- AUDIT LOG FUNCTIONS ---
def get_audit_log():
    with get_connection() as con:
        return pd.read_sql_query("SELECT timestamp, user_email, action, item_type, item_name FROM audit_log ORDER BY timestamp DESC", con)