import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
import datetime
import plotly.express as px
from config import ALLOWED_EMAILS

# --- CONFIGURATION & AUTHENTICATION ---
DB_FILE = "portfolio.db"

# Instructions for each tab, now located directly in the app
TAB_INSTRUCTIONS = {
    "IT Units": "Manage the internal IT teams or departments responsible for applications and services. You can add new units, edit their contact and budget information, or delete them here.",
    "Applications": "Track all software applications, whether they are developed internally or purchased from an external vendor. Link each application to the IT Unit that manages it.",
    "IT Services": "Manage all internal services provided by your IT Units, such as the Help Desk or Classroom Support. You can track budget, FTEs, and service level details.",
    "Dashboard": "Get a high-level visual overview of your portfolio. This dashboard highlights total costs, shows spending by vendor, and application distribution by IT Unit.",
    "Settings": "Configure the dropdown options used throughout the application. Add or remove Vendors, Application Types, Categories, etc., to customize the forms to your needs.",
    "Audit Log": "View a complete history of all changes made within the application. You can filter the log by user, item type, or date range to track activity."
}

def check_authentication():
    """
    Returns True if the user is authenticated.
    Otherwise, displays a login form and returns False.
    """
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False

    if st.session_state['authenticated']:
        return True

    st.header("Login")
    st.write("Please enter an authorized email address to access the application.")
    
    with st.form("login_form"):
        email = st.text_input("Email Address").lower()
        submitted = st.form_submit_button("Login")

        if submitted:
            if email in ALLOWED_EMAILS:
                st.session_state['authenticated'] = True
                st.session_state['user_email'] = email
                st.rerun()
            else:
                st.error("Access Denied: This email address is not authorized.")
    
    return False


# --- DATABASE SETUP ---
def init_db():
    """Initializes the SQLite database and creates/updates tables as needed."""
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()

        # --- Migration: providers table to it_units ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='providers'")
        if cur.fetchone():
            cur.execute("ALTER TABLE providers RENAME TO it_units")

        # --- IT Units Table Setup ---
        cur.execute("CREATE TABLE IF NOT EXISTS it_units (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        cur.execute("PRAGMA table_info(it_units)")
        existing_columns = [info[1] for info in cur.fetchall()]
        required_it_unit_columns = {
            "contact_person": "TEXT", "contact_email": "TEXT", "notes": "TEXT",
            "total_fte": "INTEGER", "budget_amount": "REAL"
        }
        for column_name, column_type in required_it_unit_columns.items():
            if column_name not in existing_columns:
                cur.execute(f"ALTER TABLE it_units ADD COLUMN {column_name} {column_type}")

        # --- Lookup Tables ---
        cur.execute('''CREATE TABLE IF NOT EXISTS vendors (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS service_types (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS sla_levels (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS service_methods (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')

        # --- Applications Table Setup & Migration ---
        cur.execute("CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        cur.execute("PRAGMA table_info(applications)")
        app_columns = [info[1] for info in cur.fetchall()]
        
        if 'provider_id' in app_columns:
            cur.execute("ALTER TABLE applications RENAME COLUMN provider_id TO it_unit_id")
            cur.execute("PRAGMA table_info(applications)") # Refresh columns after rename
            app_columns = [info[1] for info in cur.fetchall()]

        required_app_columns = {
            "it_unit_id": "INTEGER REFERENCES it_units(id)", "vendor_id": "INTEGER REFERENCES vendors(id)",
            "renewal_date": "TEXT", "annual_cost": "REAL", "service_type_id": "INTEGER REFERENCES service_types(id)",
            "category_id": "INTEGER REFERENCES categories(id)", "integrations": "TEXT", "other_units": "TEXT",
            "similar_applications": "TEXT", "service_owner": "TEXT"
        }
        for col, col_type in required_app_columns.items():
            if col not in app_columns:
                cur.execute(f"ALTER TABLE applications ADD COLUMN {col} {col_type}")
        
        # --- IT Services Table Setup & Migration (including removing UNIQUE constraint on name) ---
        cur.execute("PRAGMA index_list('it_services')")
        indexes = [row[1] for row in cur.fetchall()]
        has_unique_name_constraint = any('it_services_name' in idx for idx in indexes)

        if has_unique_name_constraint:
            st.warning("Migrating IT Services table to remove unique name constraint.")
            cur.execute("ALTER TABLE it_services RENAME TO it_services_old")
            cur.execute("CREATE TABLE it_services (id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT)")
            cur.execute("INSERT INTO it_services (id, name, description) SELECT id, name, description FROM it_services_old")
            cur.execute("DROP TABLE it_services_old")

        cur.execute("CREATE TABLE IF NOT EXISTS it_services (id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT)")
        cur.execute("PRAGMA table_info(it_services)")
        it_services_columns = [info[1] for info in cur.fetchall()]
        
        if 'provider_id' in it_services_columns:
            cur.execute("ALTER TABLE it_services RENAME COLUMN provider_id TO it_unit_id")
            cur.execute("PRAGMA table_info(it_services)") # Refresh columns after rename
            it_services_columns = [info[1] for info in cur.fetchall()]

        required_it_services_columns = {
            "it_unit_id": "INTEGER REFERENCES it_units(id)", "fte_count": "INTEGER",
            "dependencies": "TEXT", "service_owner": "TEXT", "status": "TEXT",
            "sla_level_id": "INTEGER REFERENCES sla_levels(id)",
            "service_method_id": "INTEGER REFERENCES service_methods(id)",
            "budget_allocation": "REAL"
        }
        for col, col_type in required_it_services_columns.items():
            if col not in it_services_columns:
                cur.execute(f"ALTER TABLE it_services ADD COLUMN {col} {col_type}")

        # --- Audit Log Table ---
        cur.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                user_email TEXT NOT NULL,
                action TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_name TEXT NOT NULL,
                details TEXT
            )
        ''')

        con.commit()
    except sqlite3.Error as e:
        st.error(f"Database error during initialization: {e}")
    finally:
        if con:
            con.close()


# --- DATABASE HELPER FUNCTIONS ---

def get_connection():
    """Returns a database connection."""
    return sqlite3.connect(DB_FILE)

def log_change(user_email, action, item_type, item_name, details=""):
    """Logs an action to the audit_log table."""
    with get_connection() as con:
        cur = con.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """INSERT INTO audit_log (timestamp, user_email, action, item_type, item_name, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (timestamp, user_email, action, item_type, item_name, details)
        )
        con.commit()

# IT Unit Functions
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

def add_it_unit(user_email, name, contact_person="", contact_email="", total_fte=0, budget_amount=0.0, notes=""):
    """Adds a new IT Unit if the name doesn't exist, returns the unit's ID."""
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT id FROM it_units WHERE name = ?", (name,))
        existing = cur.fetchone()
        if existing:
            st.warning(f"IT Unit '{name}' already exists.")
            return existing[0]

        cur.execute("""
            INSERT INTO it_units (name, contact_person, contact_email, total_fte, budget_amount, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, contact_person, contact_email, total_fte, budget_amount, notes))
        con.commit()
        log_change(user_email, "CREATE", "IT Unit", name)
        st.success(f"Added new IT Unit: {name}")
        return cur.lastrowid

def update_it_unit_details(user_email, unit_id, name, contact_person, contact_email, total_fte, budget_amount, notes):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("""
            UPDATE it_units
            SET name = ?, contact_person = ?, contact_email = ?, total_fte = ?, budget_amount = ?, notes = ?
            WHERE id = ?
        """, (name, contact_person, contact_email, total_fte, budget_amount, notes, unit_id))
        con.commit()
        log_change(user_email, "UPDATE", "IT Unit", name)

def delete_it_unit(user_email, unit_id, unit_name):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM it_units WHERE id = ?", (unit_id,))
        cur.execute("UPDATE applications SET it_unit_id = NULL WHERE it_unit_id = ?", (unit_id,))
        cur.execute("UPDATE it_services SET it_unit_id = NULL WHERE it_unit_id = ?", (unit_id,))
        con.commit()
        log_change(user_email, "DELETE", "IT Unit", unit_name)


# Lookup CRUD Functions (Vendors, Types, etc.)
def get_lookup_data(table_name):
    with get_connection() as con:
        return pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY name", con)

def add_lookup_item(user_email, table_name, name):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(f"INSERT INTO {table_name} (name) VALUES (?)", (name,))
        con.commit()
        log_change(user_email, "CREATE", f"Lookup: {table_name}", name)

def update_lookup_item(user_email, table_name, item_id, new_name):
    """Updates the name of a lookup item."""
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(f"UPDATE {table_name} SET name = ? WHERE id = ?", (new_name, item_id))
        con.commit()
        log_change(user_email, "UPDATE", f"Lookup: {table_name}", new_name)

def delete_lookup_item(user_email, table_name, item_id, item_name):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
        con.commit()
        log_change(user_email, "DELETE", f"Lookup: {table_name}", item_name)

# Application Functions
def get_applications():
    with get_connection() as con:
        query = """
            SELECT
                a.id, a.name, iu.name as managing_it_unit, v.name as vendor, 
                st.name as type, c.name as category, a.annual_cost, a.renewal_date, 
                a.similar_applications, a.service_owner
            FROM applications a
            LEFT JOIN it_units iu ON a.it_unit_id = iu.id
            LEFT JOIN vendors v ON a.vendor_id = v.id
            LEFT JOIN service_types st ON a.service_type_id = st.id
            LEFT JOIN categories c ON a.category_id = c.id
        """
        return pd.read_sql_query(query, con)

def get_application_details(app_id):
    with get_connection() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def add_application(user_email, it_unit_id, vendor_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units, similar_apps, service_owner):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """INSERT INTO applications (it_unit_id, vendor_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units, similar_applications, service_owner)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (it_unit_id, vendor_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units, similar_apps, service_owner)
        )
        con.commit()
        log_change(user_email, "CREATE", "Application", name)

def update_application(user_email, app_id, it_unit_id, vendor_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units, similar_apps, service_owner):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """UPDATE applications SET it_unit_id=?, vendor_id=?, name=?, service_type_id=?, category_id=?, annual_cost=?, renewal_date=?, integrations=?, other_units=?, similar_applications=?, service_owner=?
               WHERE id=?""",
            (it_unit_id, vendor_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units, similar_apps, service_owner, app_id)
        )
        con.commit()
        log_change(user_email, "UPDATE", "Application", name)

def delete_application(user_email, app_id, app_name):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        con.commit()
        log_change(user_email, "DELETE", "Application", app_name)
        
# IT Service Functions
def get_it_services():
    with get_connection() as con:
        query = """
            SELECT
                its.id, its.name, iu.name as providing_it_unit, its.status,
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

def add_it_service(user_email, name, desc, it_unit_id, fte, deps, owner, status, sla_id, method_id, budget):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO it_services (name, description, it_unit_id, fte_count, dependencies, service_owner, status, sla_level_id, service_method_id, budget_allocation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, desc, it_unit_id, fte, deps, owner, status, sla_id, method_id, budget))
        con.commit()
        log_change(user_email, "CREATE", "IT Service", name)

def update_it_service(user_email, service_id, name, desc, it_unit_id, fte, deps, owner, status, sla_id, method_id, budget):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("""
            UPDATE it_services
            SET name=?, description=?, it_unit_id=?, fte_count=?, dependencies=?, service_owner=?, status=?, sla_level_id=?, service_method_id=?, budget_allocation=?
            WHERE id = ?
        """, (name, desc, it_unit_id, fte, deps, owner, status, sla_id, method_id, budget, service_id))
        con.commit()
        log_change(user_email, "UPDATE", "IT Service", name)

def delete_it_service(user_email, service_id, service_name):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM it_services WHERE id = ?", (service_id,))
        con.commit()
        log_change(user_email, "DELETE", "IT Service", service_name)

# Audit Log Functions
def get_audit_log():
    with get_connection() as con:
        return pd.read_sql_query("SELECT timestamp, user_email, action, item_type, item_name FROM audit_log ORDER BY timestamp DESC", con)

# --- STREAMLIT UI ---

@st.cache_data
def convert_df_to_csv(df):
    """Helper function to convert a DataFrame to a CSV string."""
    return df.to_csv(index=False).encode('utf-8')

def render_lookup_manager(user_email, title, singular_name, table_name):
    st.write(f"#### {title}")
    with st.form(f"add_{table_name}_form", clear_on_submit=True):
        new_name = st.text_input(f"New {singular_name} Name")
        if st.form_submit_button(f"Add {singular_name}"):
            if new_name:
                add_lookup_item(user_email, table_name, new_name)
                st.rerun()
    
    items = get_lookup_data(table_name)
    for _, row in items.iterrows():
        item_id = row['id']
        item_name = row['name']
        
        is_editing = (
            'editing_lookup_item' in st.session_state and
            st.session_state.editing_lookup_item['table'] == table_name and
            st.session_state.editing_lookup_item['id'] == item_id
        )

        if is_editing:
            with st.form(key=f"edit_lookup_{table_name}_{item_id}"):
                new_item_name = st.text_input("New Name", value=item_name)
                
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Save", type="primary"):
                    update_lookup_item(user_email, table_name, item_id, new_item_name)
                    st.session_state.pop('editing_lookup_item', None)
                    st.success(f"Updated '{item_name}' to '{new_item_name}'.")
                    st.rerun()
                if c2.form_submit_button("Cancel"):
                    st.session_state.pop('editing_lookup_item', None)
                    st.rerun()
        else:
            l_col, m_col, r_col = st.columns([10, 1, 1])
            l_col.write(item_name)
            
            if m_col.button("✏️", key=f"edit_lookup_{table_name}_{item_id}"):
                st.session_state.editing_lookup_item = {'table': table_name, 'id': item_id}
                st.rerun()
                
            if r_col.button("🗑️", key=f"del_lookup_{table_name}_{item_id}"):
                st.session_state.confirming_delete_lookup = {'table': table_name, 'id': item_id, 'name': item_name}
                st.rerun()


def main():
    st.set_page_config(layout="wide", page_title="Service Portfolio Manager")
    
    if not check_authentication():
        return

    init_db()
    
    user_email = st.session_state.get('user_email', 'unknown')
    
    st.sidebar.success(f"Logged in as {user_email}")
    if st.sidebar.button("Logout"):
        st.session_state['authenticated'] = False
        st.session_state.pop('user_email', None)
        st.rerun()

    st.title("Service Portfolio Manager")
    st.write("Track IT Units, applications, and internal IT services to identify overlaps and cost-saving opportunities.")

    tab_names = ["IT Units", "Applications", "IT Services", "Dashboard", "Settings", "Audit Log"]
    unit_tab, app_tab, service_tab, dashboard_tab, settings_tab, audit_tab = st.tabs(tab_names)

    it_units_df_all = get_it_units()
    it_unit_options_all = dict(zip(it_units_df_all['id'], it_units_df_all['name']))

    with unit_tab:
        st.header("Manage IT Units")
        st.info(TAB_INSTRUCTIONS["IT Units"])
        
        with st.expander("➕ Add New IT Unit"):
            with st.form("add_unit_form", clear_on_submit=True):
                name = st.text_input("IT Unit Name")
                contact_person = st.text_input("Contact Person")
                contact_email = st.text_input("Contact Email")
                total_fte = st.number_input("Total FTE", min_value=0, step=1)
                budget_amount = st.number_input("Annual Budget ($)", min_value=0.0, format="%.2f")
                notes = st.text_area("Notes", height=150)
                if st.form_submit_button("Add IT Unit") and name:
                    add_it_unit(user_email, name, contact_person, contact_email, total_fte, budget_amount, notes)
                    st.rerun()
        
        st.divider()
        search_unit = st.text_input("Search IT Units by Name")
        
        filtered_units_df = it_units_df_all
        if search_unit:
            filtered_units_df = it_units_df_all[it_units_df_all['name'].str.contains(search_unit, case=False, na=False)]

        st.subheader("Edit or Delete an IT Unit")
        
        unit_options = dict(zip(filtered_units_df['id'], filtered_units_df['name']))
        unit_to_edit_id = st.selectbox("Select an IT Unit", options=[None] + list(unit_options.keys()), format_func=lambda x: "---" if x is None else unit_options.get(x))

        if unit_to_edit_id:
            unit_details = get_it_unit_details(unit_to_edit_id)
            if 'confirming_delete_unit' in st.session_state and st.session_state.confirming_delete_unit == unit_to_edit_id:
                st.warning(f"**Are you sure you want to delete '{unit_details['name']}'?** This removes its association from any items.")
                c1, c2 = st.columns(2)
                if c1.button("Yes, delete it", key="confirm_del_unit"):
                    delete_it_unit(user_email, unit_to_edit_id, unit_details['name'])
                    st.session_state.pop('confirming_delete_unit', None)
                    st.success(f"Deleted IT Unit: {unit_details['name']}")
                    st.rerun()
                if c2.button("Cancel", key="cancel_del_unit"):
                    st.session_state.pop('confirming_delete_unit', None)
                    st.rerun()

            with st.form("edit_unit_form"):
                st.write(f"**Editing: {unit_details['name']}**")
                name = st.text_input("IT Unit Name", value=unit_details['name'])
                contact_person = st.text_input("Contact Person", value=unit_details.get('contact_person') or '')
                contact_email = st.text_input("Contact Email", value=unit_details.get('contact_email') or '')
                total_fte = st.number_input("Total FTE", min_value=0, step=1, value=int(unit_details.get('total_fte') or 0))
                budget_amount = st.number_input("Annual Budget ($)", min_value=0.0, format="%.2f", value=float(unit_details.get('budget_amount') or 0.0))
                notes = st.text_area("Notes", value=unit_details.get('notes') or '', height=150)
                
                del_col, save_col = st.columns([1, 6])
                if save_col.form_submit_button("Save Changes", width='stretch', type="primary"):
                    update_it_unit_details(user_email, unit_to_edit_id, name, contact_person, contact_email, total_fte, budget_amount, notes)
                    st.success(f"Updated details for {name}")
                    st.rerun()
                if del_col.form_submit_button("DELETE"):
                    st.session_state.confirming_delete_unit = unit_to_edit_id
                    st.rerun()

        st.subheader("All IT Units")
        st.dataframe(filtered_units_df, width='stretch')
        csv_units = convert_df_to_csv(filtered_units_df)
        st.download_button(label="Download data as CSV", data=csv_units, file_name='it_units_export.csv', mime='text/csv')

    with app_tab:
        st.header("Manage Applications")
        st.info(TAB_INSTRUCTIONS["Applications"])
        
        vendors_df = get_lookup_data('vendors')
        vendor_options_all = dict(zip(vendors_df['id'], vendors_df['name']))
        service_types_df = get_lookup_data('service_types')
        type_options_all = dict(zip(service_types_df['id'], service_types_df['name']))
        categories_df = get_lookup_data('categories')
        category_options_all = dict(zip(categories_df['id'], categories_df['name']))

        with st.expander("➕ Add New Application"):
            if it_units_df_all.empty:
                st.warning("Please add at least one IT Unit before adding an application.")
            else:
                with st.form("add_app_form", clear_on_submit=True):
                    app_name = st.text_input("Application Name")
                    service_owner = st.text_input("Service Owner/Lead")
                    it_unit_id = st.selectbox("Managing IT Unit", options=it_unit_options_all.keys(), format_func=it_unit_options_all.get)
                    vendor_id = st.selectbox("Vendor (Optional, for external apps)", options=[None] + list(vendor_options_all.keys()), format_func=lambda x: "None (Internal)" if x is None else vendor_options_all.get(x))
                    service_type_id = st.selectbox("Type", options=type_options_all.keys(), format_func=type_options_all.get)
                    category_id = st.selectbox("Category", options=category_options_all.keys(), format_func=category_options_all.get)
                    annual_cost = st.number_input("Annual Cost ($)", min_value=0.0, format="%.2f")
                    renewal_date = st.date_input("Next Renewal Date", value=datetime.date.today())
                    integrations = st.text_area("Known Integrations")
                    other_units = st.text_area("Other Business Units Using Service", height=100)
                    similar_apps = st.text_area("Similar Applications (if any)")
                    
                    if st.form_submit_button("Save Application") and app_name:
                        add_application(user_email, it_unit_id, vendor_id, app_name, service_type_id, category_id, annual_cost, str(renewal_date), integrations, other_units, similar_apps, service_owner)
                        st.success(f"Added application: {app_name}")
                        st.rerun()
        st.divider()

        st.subheader("Filter and Search Applications")
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        search_app = fcol1.text_input("Search by Name")
        filter_unit = fcol2.multiselect("Filter by IT Unit", options=it_unit_options_all.values())
        filter_vendor = fcol3.multiselect("Filter by Vendor", options=vendor_options_all.values())
        filter_category = fcol4.multiselect("Filter by Category", options=category_options_all.values())
        
        applications_df = get_applications()
        filtered_apps_df = applications_df.copy()
        
        if search_app: filtered_apps_df = filtered_apps_df[filtered_apps_df['name'].str.contains(search_app, case=False, na=False)]
        if filter_unit: filtered_apps_df = filtered_apps_df[filtered_apps_df['managing_it_unit'].isin(filter_unit)]
        if filter_vendor: filtered_apps_df = filtered_apps_df[filtered_apps_df['vendor'].isin(filter_vendor)]
        if filter_category: filtered_apps_df = filtered_apps_df[filtered_apps_df['category'].isin(filter_category)]

        st.dataframe(filtered_apps_df, width='stretch')
        csv_apps = convert_df_to_csv(filtered_apps_df)
        st.download_button(label="Download data as CSV", data=csv_apps, file_name='applications_export.csv', mime='text/csv')

        st.subheader("Edit or Delete an Application")
        app_options_all = dict(zip(applications_df['id'], applications_df['name']))
        app_to_edit_id = st.selectbox("Select an application", options=[None] + list(app_options_all.keys()), format_func=lambda x: "---" if x is None else app_options_all.get(x))

        if app_to_edit_id:
            app_details = get_application_details(app_to_edit_id)
            if 'confirming_delete_app' in st.session_state and st.session_state.confirming_delete_app == app_to_edit_id:
                st.warning(f"**Are you sure you want to delete the application '{app_details['name']}'?**")
                c1, c2 = st.columns(2)
                if c1.button("Yes, delete it", key="confirm_del_app"):
                    delete_application(user_email, app_to_edit_id, app_details['name'])
                    st.session_state.pop('confirming_delete_app', None)
                    st.success(f"Deleted application: {app_details['name']}")
                    st.rerun()
                if c2.button("Cancel", key="cancel_del_app"):
                    st.session_state.pop('confirming_delete_app', None)
                    st.rerun()
            
            with st.form(f"edit_app_form_{app_to_edit_id}"):
                st.write(f"**Editing: {app_details['name']}**")
                edit_name = st.text_input("Application Name", value=app_details['name'])
                edit_service_owner = st.text_input("Service Owner/Lead", value=app_details.get('service_owner') or '')
                
                default_unit_idx = list(it_unit_options_all.keys()).index(app_details['it_unit_id']) if app_details.get('it_unit_id') in it_unit_options_all else 0
                edit_it_unit_id = st.selectbox("Managing IT Unit", options=it_unit_options_all.keys(), format_func=it_unit_options_all.get, index=default_unit_idx)

                vendor_keys = [None] + list(vendor_options_all.keys())
                default_vendor_id = app_details.get('vendor_id')
                default_vendor_idx = vendor_keys.index(default_vendor_id) if default_vendor_id in vendor_keys else 0
                edit_vendor_id = st.selectbox("Vendor", options=vendor_keys, format_func=lambda x: "None (Internal)" if x is None else vendor_options_all.get(x), index=default_vendor_idx)

                default_type_idx = list(type_options_all.keys()).index(app_details['service_type_id']) if app_details.get('service_type_id') in type_options_all else 0
                edit_type_id = st.selectbox("Type", options=type_options_all.keys(), format_func=type_options_all.get, index=default_type_idx)
                
                default_cat_idx = list(category_options_all.keys()).index(app_details['category_id']) if app_details.get('category_id') in category_options_all else 0
                edit_category_id = st.selectbox("Category", options=category_options_all.keys(), format_func=category_options_all.get, index=default_cat_idx)

                edit_annual_cost = st.number_input("Annual Cost ($)", min_value=0.0, format="%.2f", value=float(app_details.get('annual_cost') or 0.0))
                edit_renewal = st.date_input("Next Renewal Date", value=pd.to_datetime(app_details['renewal_date']))
                edit_integrations = st.text_area("Known Integrations", value=app_details.get('integrations') or '')
                edit_other_units = st.text_area("Other Business Units Using Service", value=app_details.get('other_units') or '', height=100)
                edit_similar_apps = st.text_area("Similar Applications", value=app_details.get('similar_applications') or '')

                del_col, save_col = st.columns([1, 6])
                if save_col.form_submit_button("Save Changes", width='stretch', type="primary"):
                    update_application(user_email, app_to_edit_id, edit_it_unit_id, edit_vendor_id, edit_name, edit_type_id, edit_category_id, edit_annual_cost, str(edit_renewal), edit_integrations, edit_other_units, edit_similar_apps, edit_service_owner)
                    st.success("Application updated.")
                    st.rerun()
                if del_col.form_submit_button("DELETE"):
                    st.session_state.confirming_delete_app = app_to_edit_id
                    st.rerun()

    with service_tab:
        st.header("Manage Internal IT Services")
        st.info(TAB_INSTRUCTIONS["IT Services"])
        
        sla_levels_df = get_lookup_data('sla_levels')
        service_methods_df = get_lookup_data('service_methods')
        sla_options_all = dict(zip(sla_levels_df['id'], sla_levels_df['name']))
        method_options_all = dict(zip(service_methods_df['id'], service_methods_df['name']))
        
        with st.expander("➕ Add New IT Service"):
            with st.form("add_it_service_form", clear_on_submit=True):
                it_service_name = st.text_input("Service Name")
                it_unit_id = st.selectbox("Providing IT Unit", options=[None] + list(it_unit_options_all.keys()), format_func=lambda x: "None" if x is None else it_unit_options_all.get(x))
                status = st.selectbox("Status", options=["Active", "In Development", "Retired"])
                service_owner = st.text_input("Service Owner/Lead")
                fte_count = st.number_input("Dedicated FTEs", min_value=0, step=1)
                budget_allocation = st.number_input("Budget Allocation ($)", min_value=0.0, format="%.2f")
                sla_id = st.selectbox("SLA Level", options=[None] + list(sla_options_all.keys()), format_func=lambda x: "None" if x is None else sla_options_all.get(x))
                method_id = st.selectbox("Service Method", options=[None] + list(method_options_all.keys()), format_func=lambda x: "None" if x is None else method_options_all.get(x))
                it_service_desc = st.text_area("Description")
                dependencies = st.text_area("Dependencies (e.g., other apps, services)")
                
                if st.form_submit_button("Add Service") and it_service_name:
                    add_it_service(user_email, it_service_name, it_service_desc, it_unit_id, fte_count, dependencies, service_owner, status, sla_id, method_id, budget_allocation)
                    st.success(f"Added service: {it_service_name}")
                    st.rerun()
        
        st.divider()
        st.subheader("Filter and Search IT Services")
        fscol1, fscol2, fscol3, fscol4 = st.columns(4)
        search_its = fscol1.text_input("Search by Name", key="it_search")
        filter_unit_its = fscol2.multiselect("Filter by IT Unit", options=it_unit_options_all.values(), key="it_unit_filter")
        filter_status_its = fscol3.multiselect("Status", options=["Active", "In Development", "Retired"], key="it_status_filter")
        filter_sla_its = fscol4.multiselect("SLA Level", options=sla_options_all.values(), key="it_sla_filter")

        it_services_df = get_it_services()
        filtered_its_df = it_services_df.copy()

        if search_its: filtered_its_df = filtered_its_df[filtered_its_df['name'].str.contains(search_its, case=False, na=False)]
        if filter_unit_its: filtered_its_df = filtered_its_df[filtered_its_df['providing_it_unit'].isin(filter_unit_its)]
        if filter_status_its: filtered_its_df = filtered_its_df[filtered_its_df['status'].isin(filter_status_its)]
        if filter_sla_its: filtered_its_df = filtered_its_df[filtered_its_df['sla_level'].isin(filter_sla_its)]

        st.dataframe(filtered_its_df, width='stretch')
        csv_its = convert_df_to_csv(filtered_its_df)
        st.download_button(label="Download data as CSV", data=csv_its, file_name='it_services_export.csv', mime='text/csv')
        
        st.subheader("Edit or Delete an IT Service")
        it_service_options_all = dict(zip(it_services_df['id'], it_services_df['name']))
        it_service_to_edit_id = st.selectbox("Select a service", options=[None] + list(it_service_options_all.keys()), format_func=lambda x: "---" if x is None else it_service_options_all.get(x))

        if it_service_to_edit_id:
            it_service_details = get_it_service_details(it_service_to_edit_id)
            if 'confirming_delete_service' in st.session_state and st.session_state.confirming_delete_service == it_service_to_edit_id:
                st.warning(f"**Are you sure you want to delete the IT Service '{it_service_details['name']}'?**")
                c1, c2 = st.columns(2)
                if c1.button("Yes, delete it", key="confirm_del_service"):
                    delete_it_service(user_email, it_service_to_edit_id, it_service_details['name'])
                    st.session_state.pop('confirming_delete_service', None)
                    st.success(f"Deleted IT Service: {it_service_details['name']}")
                    st.rerun()
                if c2.button("Cancel", key="cancel_del_service"):
                    st.session_state.pop('confirming_delete_service', None)
                    st.rerun()

            with st.form(f"edit_it_service_{it_service_to_edit_id}"):
                st.write(f"**Editing: {it_service_details['name']}**")
                edit_it_name = st.text_input("Service Name", value=it_service_details['name'])
                
                unit_keys = [None] + list(it_unit_options_all.keys())
                default_unit_id = it_service_details.get('it_unit_id')
                default_unit_idx = unit_keys.index(default_unit_id) if default_unit_id in unit_keys else 0
                edit_it_unit_id = st.selectbox("Providing IT Unit", options=unit_keys, format_func=lambda x: "None" if x is None else it_unit_options_all.get(x), index=default_unit_idx)
                
                status_options = ["Active", "In Development", "Retired"]
                default_status_idx = status_options.index(it_service_details.get('status')) if it_service_details.get('status') in status_options else 0
                edit_status = st.selectbox("Status", options=status_options, index=default_status_idx)
                
                sla_keys = [None] + list(sla_options_all.keys())
                default_sla_idx = sla_keys.index(it_service_details.get('sla_level_id')) if it_service_details.get('sla_level_id') in sla_keys else 0
                edit_sla_id = st.selectbox("SLA Level", options=sla_keys, format_func=lambda x: "None" if x is None else sla_options_all.get(x), index=default_sla_idx)

                method_keys = [None] + list(method_options_all.keys())
                default_method_idx = method_keys.index(it_service_details.get('service_method_id')) if it_service_details.get('service_method_id') in method_keys else 0
                edit_method_id = st.selectbox("Service Method", options=method_keys, format_func=lambda x: "None" if x is None else method_options_all.get(x), index=default_method_idx)

                edit_service_owner = st.text_input("Service Owner/Lead", value=it_service_details.get('service_owner') or '')
                edit_fte_count = st.number_input("Dedicated FTEs", min_value=0, step=1, value=int(it_service_details.get('fte_count') or 0))
                edit_budget = st.number_input("Budget Allocation ($)", min_value=0.0, format="%.2f", value=float(it_service_details.get('budget_allocation') or 0.0))
                edit_it_desc = st.text_area("Description", value=it_service_details.get('description') or '')
                edit_dependencies = st.text_area("Dependencies", value=it_service_details.get('dependencies') or '')

                del_col, save_col = st.columns([1, 6])
                if save_col.form_submit_button("Save Changes", width='stretch', type="primary"):
                    update_it_service(user_email, it_service_to_edit_id, edit_it_name, edit_it_desc, edit_it_unit_id, edit_fte_count, edit_dependencies, edit_service_owner, edit_status, edit_sla_id, edit_method_id, edit_budget)
                    st.success(f"Updated {edit_it_name}")
                    st.rerun()
                if del_col.form_submit_button("DELETE"):
                    st.session_state.confirming_delete_service = it_service_to_edit_id
                    st.rerun()

    with dashboard_tab:
        st.header("Dashboard & Recommendations")
        st.info(TAB_INSTRUCTIONS["Dashboard"])
        
        all_apps_df = get_applications()
        all_it_units_df = get_it_units()
        all_it_services_df = get_it_services()
        
        st.subheader("High-Level Metrics")
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        
        total_annual_cost = all_apps_df['annual_cost'].sum() if not all_apps_df.empty else 0.0
        total_it_budget = all_it_services_df['budget_allocation'].sum() if not all_it_services_df.empty else 0.0
        
        metric_col1.metric("Total IT Units", len(all_it_units_df))
        metric_col2.metric("Total Applications", len(all_apps_df))
        metric_col3.metric("Total IT Services", len(all_it_services_df))
        metric_col4.metric("Total Annual Spend/Budget", f"${(total_annual_cost + total_it_budget):,.2f}")

        st.divider()
        st.subheader("Consolidation Opportunities")

        if not all_apps_df.empty:
            app_duplicates = all_apps_df[all_apps_df.duplicated(subset=['name'], keep=False)].sort_values(by='name')
            if not app_duplicates.empty:
                st.warning("Duplicate Applications Found Across IT Units")
                
                dup_app_counts = app_duplicates['name'].value_counts().reset_index()
                dup_app_counts.columns = ['Application', 'Count']
                fig_dup_apps = px.bar(dup_app_counts, x='Application', y='Count', title='Duplicated Application Counts')
                st.plotly_chart(fig_dup_apps, use_container_width=True)
                
                st.dataframe(app_duplicates[['name', 'managing_it_unit', 'vendor', 'annual_cost']], width='stretch')
            else:
                st.success("No duplicate application names found.")
        
        if not all_it_services_df.empty:
            service_duplicates = all_it_services_df[all_it_services_df.duplicated(subset=['name'], keep=False)].sort_values(by='name')
            if not service_duplicates.empty:
                st.warning("Duplicate IT Services Found Across IT Units")
                st.dataframe(service_duplicates[['name', 'providing_it_unit', 'budget_allocation', 'fte_count']], width='stretch')
            else:
                st.success("No duplicate IT service names found.")
        
        if not all_apps_df.empty:
            category_duplicates = all_apps_df.dropna(subset=['category'])[all_apps_df.dropna(subset=['category']).duplicated(subset=['category'], keep=False)].sort_values(by='category')
            if not category_duplicates.empty:
                st.warning("Overlapping Application Categories Found")
                st.dataframe(category_duplicates[['category', 'name', 'managing_it_unit', 'vendor']], width='stretch')
            else:
                st.success("No overlapping application categories found.")

        if not all_apps_df.empty:
            st.divider()
            st.subheader("Application Visual Insights")
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                cost_by_vendor = all_apps_df.groupby('vendor')['annual_cost'].sum().reset_index()
                fig_vendor_cost = px.pie(cost_by_vendor, names='vendor', values='annual_cost', title='Annual Cost by Vendor')
                st.plotly_chart(fig_vendor_cost, use_container_width=True)
                
                apps_by_unit = all_apps_df['managing_it_unit'].value_counts().reset_index()
                fig_apps_by_unit = px.pie(apps_by_unit, names='managing_it_unit', values='count', title='Application Count by Managing IT Unit')
                st.plotly_chart(fig_apps_by_unit, use_container_width=True)

            with chart_col2:
                apps_by_category = all_apps_df['category'].value_counts().reset_index()
                fig_app_category = px.bar(apps_by_category, x='category', y='count', title='Application Count by Category')
                st.plotly_chart(fig_app_category, use_container_width=True)
        else:
            st.info("Add applications to see application-specific insights.")
        
        if not all_it_services_df.empty:
            st.divider()
            st.subheader("IT Service Visual Insights")
            it_chart_col1, it_chart_col2 = st.columns(2)
            with it_chart_col1:
                budget_by_service = all_it_services_df.groupby('name')['budget_allocation'].sum().reset_index()
                fig_it_budget = px.pie(budget_by_service, names='name', values='budget_allocation', title='Budget Allocation by IT Service')
                st.plotly_chart(fig_it_budget, use_container_width=True)
            with it_chart_col2:
                fte_by_service = all_it_services_df.groupby('name')['fte_count'].sum().reset_index()
                fig_it_fte = px.bar(fte_by_service, x='name', y='fte_count', title='Dedicated FTEs by IT Service')
                st.plotly_chart(fig_it_fte, use_container_width=True)
        else:
            st.info("Add IT services to see service-specific insights.")

    with settings_tab:
        st.header("Manage Lookups")
        st.info(TAB_INSTRUCTIONS["Settings"])

        if 'confirming_delete_lookup' in st.session_state and st.session_state.confirming_delete_lookup:
            item = st.session_state.confirming_delete_lookup
            st.warning(f"**Are you sure you want to delete the lookup item '{item['name']}'?**")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete it", key="confirm_del_lookup"):
                delete_lookup_item(user_email, item['table'], item['id'], item['name'])
                st.session_state.pop('confirming_delete_lookup', None)
                st.success(f"Deleted item: {item['name']}")
                st.rerun()
            if c2.button("Cancel", key="cancel_del_lookup"):
                st.session_state.pop('confirming_delete_lookup', None)
                st.rerun()
        
        ven_col, type_col = st.columns(2)
        with ven_col:
            render_lookup_manager(user_email, "Vendors", "Vendor", "vendors")
        with type_col:
            render_lookup_manager(user_email, "Application Types", "Application Type", "service_types")

        st.divider()

        cat_col, sla_col, method_col = st.columns(3)
        with cat_col:
            render_lookup_manager(user_email, "Categories", "Category", "categories")
        with sla_col:
            render_lookup_manager(user_email, "SLA Levels", "SLA Level", "sla_levels")
        with method_col:
            render_lookup_manager(user_email, "Service Methods", "Service Method", "service_methods")

    with audit_tab:
        st.header("Audit Log")
        st.info(TAB_INSTRUCTIONS["Audit Log"])

        audit_df = get_audit_log()
        
        st.subheader("Filter Audit Log")
        log_f1, log_f2, log_f3 = st.columns(3)

        # Ensure timestamp is datetime for filtering
        audit_df['timestamp'] = pd.to_datetime(audit_df['timestamp'])

        filter_user = log_f1.multiselect("Filter by User", options=audit_df['user_email'].unique())
        filter_item_type = log_f2.multiselect("Filter by Item Type", options=audit_df['item_type'].unique())
        
        today = datetime.date.today()
        filter_date = log_f3.date_input("Filter by Date Range", value=(today - datetime.timedelta(days=7), today))

        filtered_log_df = audit_df.copy()
        if filter_user:
            filtered_log_df = filtered_log_df[filtered_log_df['user_email'].isin(filter_user)]
        if filter_item_type:
            filtered_log_df = filtered_log_df[filtered_log_df['item_type'].isin(filter_item_type)]
        if len(filter_date) == 2:
            start_date = pd.to_datetime(filter_date[0]).date()
            end_date = pd.to_datetime(filter_date[1]).date()
            filtered_log_df = filtered_log_df[
                (filtered_log_df['timestamp'].dt.date >= start_date) & 
                (filtered_log_df['timestamp'].dt.date <= end_date)
            ]

        st.dataframe(filtered_log_df, width='stretch')
        
        csv_audit = convert_df_to_csv(filtered_log_df)
        st.download_button(
            label="Download log as CSV",
            data=csv_audit,
            file_name='audit_log_export.csv',
            mime='text/csv',
        )


if __name__ == '__main__':
    main()

