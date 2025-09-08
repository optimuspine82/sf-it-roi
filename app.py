import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
import datetime

# --- DATABASE SETUP ---
DB_FILE = "portfolio.db"

def init_db():
    """Initializes the SQLite database and creates/updates tables as needed."""
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()

        # --- Providers Table Setup & Migration ---
        cur.execute("CREATE TABLE IF NOT EXISTS providers (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        
        cur.execute("PRAGMA table_info(providers)")
        providers_columns = [info[1] for info in cur.fetchall()]
        if 'other_units' in providers_columns:
            st.info("Old schema detected. Migrating 'other_units' field from Providers to Applications...")
            cur.execute("ALTER TABLE providers RENAME TO providers_old")
            cur.execute("""
                CREATE TABLE providers (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, contact_person TEXT,
                    contact_email TEXT, notes TEXT, total_fte INTEGER, budget_amount REAL
                )
            """)
            cur.execute("""
                INSERT INTO providers (id, name, contact_person, contact_email, notes, total_fte, budget_amount)
                SELECT id, name, contact_person, contact_email, notes, total_fte, budget_amount FROM providers_old
            """)
            cur.execute("DROP TABLE providers_old")
            st.success("Provider schema migration complete.")

        cur.execute("PRAGMA table_info(providers)")
        existing_columns = [info[1] for info in cur.fetchall()]
        required_provider_columns = {
            "contact_person": "TEXT", "contact_email": "TEXT", "notes": "TEXT",
            "total_fte": "INTEGER", "budget_amount": "REAL"
        }
        for column_name, column_type in required_provider_columns.items():
            if column_name not in existing_columns:
                cur.execute(f"ALTER TABLE providers ADD COLUMN {column_name} {column_type}")

        # --- Lookup Tables ---
        cur.execute('''CREATE TABLE IF NOT EXISTS service_types (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS sla_levels (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS service_methods (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)''')

        # --- RENAME services to applications for migration ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='services'")
        if cur.fetchone():
            cur.execute("ALTER TABLE services RENAME TO applications")
            st.success("Migrated database table from 'services' to 'applications'.")

        # --- Applications Table Setup & Migration ---
        cur.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY, provider_id INTEGER, name TEXT NOT NULL,
                renewal_date TEXT NOT NULL,
                FOREIGN KEY (provider_id) REFERENCES providers (id) ON DELETE CASCADE
            )
        ''')
        cur.execute("PRAGMA table_info(applications)")
        app_columns = [info[1] for info in cur.fetchall()]
        required_app_columns = {
            "annual_cost": "REAL", "service_type_id": "INTEGER REFERENCES service_types(id)",
            "category_id": "INTEGER REFERENCES categories(id)", "integrations": "TEXT", "other_units": "TEXT"
        }
        for col, col_type in required_app_columns.items():
            if col not in app_columns:
                cur.execute(f"ALTER TABLE applications ADD COLUMN {col} {col_type}")
        
        # --- IT Services Table Setup & Migration ---
        cur.execute('''
            CREATE TABLE IF NOT EXISTS it_services (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT
            )
        ''')
        cur.execute("PRAGMA table_info(it_services)")
        it_services_columns = [info[1] for info in cur.fetchall()]
        if 'sla_details' in it_services_columns: # Migration from old text field
             # Use a temporary name to avoid conflicts
            cur.execute("ALTER TABLE it_services RENAME TO it_services_old")
            cur.execute('''
                CREATE TABLE it_services (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
                    provider_id INTEGER REFERENCES providers(id), fte_count INTEGER,
                    dependencies TEXT, service_owner TEXT, status TEXT,
                    sla_level_id INTEGER REFERENCES sla_levels(id),
                    service_method_id INTEGER REFERENCES service_methods(id)
                )
            ''')
            cur.execute('''
                INSERT INTO it_services (id, name, description, provider_id, fte_count, dependencies, service_owner, status)
                SELECT id, name, description, provider_id, fte_count, dependencies, service_owner, status FROM it_services_old
            ''')
            cur.execute("DROP TABLE it_services_old")

        required_it_services_columns = {
            "provider_id": "INTEGER REFERENCES providers(id)", "fte_count": "INTEGER",
            "dependencies": "TEXT", "service_owner": "TEXT", "status": "TEXT",
            "sla_level_id": "INTEGER REFERENCES sla_levels(id)",
            "service_method_id": "INTEGER REFERENCES service_methods(id)"
        }
        for col, col_type in required_it_services_columns.items():
            if col not in it_services_columns:
                cur.execute(f"ALTER TABLE it_services ADD COLUMN {col} {col_type}")

        con.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
    finally:
        if con:
            con.close()

# --- DATABASE HELPER FUNCTIONS ---

def get_connection():
    """Returns a database connection."""
    return sqlite3.connect(DB_FILE)

# Provider Functions
def get_providers():
    with get_connection() as con:
        return pd.read_sql_query("SELECT id, name FROM providers ORDER BY name", con)

def get_provider_details(provider_id):
    with get_connection() as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM providers WHERE id = ?", (provider_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def add_provider(name, contact_person, contact_email, total_fte, budget_amount, notes):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO providers (name, contact_person, contact_email, total_fte, budget_amount, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, contact_person, contact_email, total_fte, budget_amount, notes))
        con.commit()

def update_provider_details(provider_id, name, contact_person, contact_email, total_fte, budget_amount, notes):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("""
            UPDATE providers
            SET name = ?, contact_person = ?, contact_email = ?, total_fte = ?, budget_amount = ?, notes = ?
            WHERE id = ?
        """, (name, contact_person, contact_email, total_fte, budget_amount, notes, provider_id))
        con.commit()

def delete_provider(provider_id):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        cur.execute("DELETE FROM applications WHERE provider_id = ?", (provider_id,))
        con.commit()

# Lookup CRUD Functions (Types, Categories, SLAs, Methods)
def get_lookup_data(table_name):
    with get_connection() as con:
        return pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY name", con)

def add_lookup_item(table_name, name):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(f"INSERT INTO {table_name} (name) VALUES (?)", (name,))
        con.commit()

def delete_lookup_item(table_name, item_id):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
        con.commit()

# Application Functions
def get_applications():
    with get_connection() as con:
        query = """
            SELECT
                a.id, a.name, p.name as provider, st.name as type, c.name as category,
                a.annual_cost, a.renewal_date, a.integrations, a.other_units
            FROM applications a
            JOIN providers p ON a.provider_id = p.id
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

def add_application(provider_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """INSERT INTO applications (provider_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (provider_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units)
        )
        con.commit()

def update_application(app_id, provider_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            """UPDATE applications SET provider_id=?, name=?, service_type_id=?, category_id=?, annual_cost=?, renewal_date=?, integrations=?, other_units=?
               WHERE id=?""",
            (provider_id, name, service_type_id, category_id, annual_cost, renewal_date, integrations, other_units, app_id)
        )
        con.commit()

def delete_application(app_id):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        con.commit()
        
# IT Service Functions
def get_it_services():
    with get_connection() as con:
        query = """
            SELECT
                its.id, its.name, p.name as provider, its.status,
                its.service_owner, its.fte_count, sl.name as sla_level, sm.name as service_method
            FROM it_services its
            LEFT JOIN providers p ON its.provider_id = p.id
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

def add_it_service(name, desc, provider_id, fte, deps, owner, status, sla_id, method_id):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO it_services (name, description, provider_id, fte_count, dependencies, service_owner, status, sla_level_id, service_method_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, desc, provider_id, fte, deps, owner, status, sla_id, method_id))
        con.commit()

def update_it_service(service_id, name, desc, provider_id, fte, deps, owner, status, sla_id, method_id):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("""
            UPDATE it_services
            SET name=?, description=?, provider_id=?, fte_count=?, dependencies=?, service_owner=?, status=?, sla_level_id=?, service_method_id=?
            WHERE id = ?
        """, (name, desc, provider_id, fte, deps, owner, status, sla_id, method_id, service_id))
        con.commit()

def delete_it_service(service_id):
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM it_services WHERE id = ?", (service_id,))
        con.commit()

# --- STREAMLIT UI ---

def render_lookup_manager(title, singular_name, table_name):
    st.write(f"#### {title}")
    with st.form(f"add_{table_name}_form", clear_on_submit=True):
        new_name = st.text_input(f"New {singular_name} Name")
        if st.form_submit_button(f"Add {singular_name}"):
            if new_name:
                add_lookup_item(table_name, new_name)
                st.rerun()
    
    items = get_lookup_data(table_name)
    for _, row in items.iterrows():
        l_col, r_col = st.columns([4, 1])
        l_col.write(row['name'])
        if r_col.button("🗑️", key=f"del_{table_name}_{row['id']}"):
            delete_lookup_item(table_name, row['id'])
            st.rerun()

def main():
    st.set_page_config(layout="wide", page_title="Service Portfolio Manager")
    init_db()

    st.title("Service Portfolio Manager")
    st.write("Track providers, applications, and internal IT services to identify overlaps and cost-saving opportunities.")

    tab_names = ["Providers", "Applications", "IT Services", "Dashboard", "Settings"]
    provider_tab, app_tab, service_tab, dashboard_tab, settings_tab = st.tabs(tab_names)

    # Pre-load data for dropdowns
    providers_df = get_providers()
    provider_options = dict(zip(providers_df['id'], providers_df['name']))

    # --- PROVIDERS TAB ---
    with provider_tab:
        st.header("Manage Service Providers")
        
        with st.expander("➕ Add New Provider"):
            with st.form("add_provider_form", clear_on_submit=True):
                name = st.text_input("Provider Name")
                contact_person = st.text_input("Contact Person")
                contact_email = st.text_input("Contact Email")
                total_fte = st.number_input("Total FTE", min_value=0, step=1)
                budget_amount = st.number_input("Annual Budget ($)", min_value=0.0, format="%.2f")
                notes = st.text_area("Notes", height=150)
                if st.form_submit_button("Add Provider") and name:
                    add_provider(name, contact_person, contact_email, total_fte, budget_amount, notes)
                    st.success(f"Added: {name}")
                    st.rerun()

        st.subheader("Edit or Delete a Provider")
        provider_to_edit_id = st.selectbox("Select a provider", options=[None] + list(provider_options.keys()), format_func=lambda x: "---" if x is None else provider_options.get(x), key="edit_provider_select")

        if provider_to_edit_id:
            provider_details = get_provider_details(provider_to_edit_id)
            with st.form("edit_provider_form"):
                st.write(f"**Editing: {provider_details['name']}**")
                name = st.text_input("Provider Name", value=provider_details['name'])
                contact_person = st.text_input("Contact Person", value=provider_details.get('contact_person') or '')
                contact_email = st.text_input("Contact Email", value=provider_details.get('contact_email') or '')
                total_fte = st.number_input("Total FTE", min_value=0, step=1, value=int(provider_details.get('total_fte') or 0))
                budget_amount = st.number_input("Annual Budget ($)", min_value=0.0, format="%.2f", value=float(provider_details.get('budget_amount') or 0.0))
                notes = st.text_area("Notes", value=provider_details.get('notes') or '', height=150)
                
                del_col, save_col = st.columns([1, 6])
                if save_col.form_submit_button("Save Changes", width='stretch'):
                    update_provider_details(provider_to_edit_id, name, contact_person, contact_email, total_fte, budget_amount, notes)
                    st.success(f"Updated details for {name}")
                    st.rerun()
                if del_col.form_submit_button("DELETE", type="primary"):
                    delete_provider(provider_to_edit_id)
                    st.warning(f"Deleted provider: {provider_details['name']}")
                    st.rerun()

        st.subheader("All Providers")
        st.dataframe(providers_df, width='stretch')

    # --- APPLICATIONS TAB ---
    with app_tab:
        st.header("Manage Applications")
        service_types_df = get_lookup_data('service_types')
        categories_df = get_lookup_data('categories')
        type_options = dict(zip(service_types_df['id'], service_types_df['name']))
        category_options = dict(zip(categories_df['id'], categories_df['name']))

        with st.expander("➕ Add New Application"):
            if providers_df.empty or service_types_df.empty or categories_df.empty:
                st.warning("Please add at least one Provider, Application Type, and Category in Settings.")
            else:
                with st.form("add_app_form", clear_on_submit=True):
                    app_name = st.text_input("Application Name")
                    provider_id = st.selectbox("Provider", options=provider_options.keys(), format_func=provider_options.get)
                    service_type_id = st.selectbox("Type", options=type_options.keys(), format_func=type_options.get)
                    category_id = st.selectbox("Category", options=category_options.keys(), format_func=category_options.get)
                    annual_cost = st.number_input("Annual Cost ($)", min_value=0.0, format="%.2f")
                    renewal_date = st.date_input("Next Renewal Date", value=datetime.date.today())
                    integrations = st.text_area("Known Integrations")
                    other_units = st.text_area("Other Business Units Using Service", height=100)
                    
                    if st.form_submit_button("Save Application") and app_name:
                        add_application(provider_id, app_name, service_type_id, category_id, annual_cost, str(renewal_date), integrations, other_units)
                        st.success(f"Added application: {app_name}")
                        st.rerun()

        applications_df = get_applications()
        st.dataframe(applications_df, width='stretch')

        st.subheader("Edit or Delete an Application")
        app_options = dict(zip(applications_df['id'], applications_df['name']))
        app_to_edit_id = st.selectbox("Select an application", options=[None] + list(app_options.keys()), format_func=lambda x: "---" if x is None else app_options.get(x), key="edit_app_select")

        if app_to_edit_id:
            app_details = get_application_details(app_to_edit_id)
            with st.form(f"edit_app_form_{app_to_edit_id}"):
                st.write(f"**Editing: {app_details['name']}**")
                edit_name = st.text_input("Application Name", value=app_details['name'])
                
                default_provider_index = list(provider_options.keys()).index(app_details['provider_id']) if app_details.get('provider_id') in provider_options else 0
                edit_provider_id = st.selectbox("Provider", options=provider_options.keys(), format_func=provider_options.get, index=default_provider_index)
                
                default_type_index = list(type_options.keys()).index(app_details['service_type_id']) if app_details.get('service_type_id') in type_options else 0
                edit_type_id = st.selectbox("Type", options=type_options.keys(), format_func=type_options.get, index=default_type_index)
                
                default_cat_index = list(category_options.keys()).index(app_details['category_id']) if app_details.get('category_id') in category_options else 0
                edit_category_id = st.selectbox("Category", options=category_options.keys(), format_func=category_options.get, index=default_cat_index)

                edit_annual_cost = st.number_input("Annual Cost ($)", min_value=0.0, format="%.2f", value=float(app_details.get('annual_cost') or 0.0))
                edit_renewal = st.date_input("Next Renewal Date", value=pd.to_datetime(app_details['renewal_date']))
                edit_integrations = st.text_area("Known Integrations", value=app_details.get('integrations') or '')
                edit_other_units = st.text_area("Other Business Units Using Service", value=app_details.get('other_units') or '', height=100)

                del_col, save_col = st.columns([1, 6])
                if save_col.form_submit_button("Save Changes", width='stretch'):
                    update_application(app_to_edit_id, edit_provider_id, edit_name, edit_type_id, edit_category_id, edit_annual_cost, str(edit_renewal), edit_integrations, edit_other_units)
                    st.success("Application updated.")
                    st.rerun()
                if del_col.form_submit_button("DELETE", type="primary"):
                    delete_application(app_to_edit_id)
                    st.warning(f"Deleted application: {app_details['name']}")
                    st.rerun()

    # --- IT SERVICES TAB ---
    with service_tab:
        st.header("Manage Internal IT Services")
        sla_levels_df = get_lookup_data('sla_levels')
        service_methods_df = get_lookup_data('service_methods')
        sla_options = dict(zip(sla_levels_df['id'], sla_levels_df['name']))
        method_options = dict(zip(service_methods_df['id'], service_methods_df['name']))
        
        with st.expander("➕ Add New IT Service"):
            with st.form("add_it_service_form", clear_on_submit=True):
                it_service_name = st.text_input("Service Name")
                provider_id = st.selectbox("Associated Provider (Optional)", options=[None] + list(provider_options.keys()), format_func=lambda x: "None" if x is None else provider_options.get(x), key="add_it_provider")
                status = st.selectbox("Status", options=["Active", "In Development", "Retired"])
                service_owner = st.text_input("Service Owner/Lead")
                fte_count = st.number_input("Dedicated FTEs", min_value=0, step=1)
                sla_id = st.selectbox("SLA Level", options=[None] + list(sla_options.keys()), format_func=lambda x: "None" if x is None else sla_options.get(x))
                method_id = st.selectbox("Service Method", options=[None] + list(method_options.keys()), format_func=lambda x: "None" if x is None else method_options.get(x))
                it_service_desc = st.text_area("Description")
                dependencies = st.text_area("Dependencies (e.g., other apps, services)")
                
                if st.form_submit_button("Add Service") and it_service_name:
                    add_it_service(it_service_name, it_service_desc, provider_id, fte_count, dependencies, service_owner, status, sla_id, method_id)
                    st.success(f"Added service: {it_service_name}")
                    st.rerun()

        it_services_df = get_it_services()
        st.dataframe(it_services_df, width='stretch')
        
        st.subheader("Edit or Delete an IT Service")
        it_service_options = dict(zip(it_services_df['id'], it_services_df['name']))
        it_service_to_edit_id = st.selectbox("Select a service", options=[None] + list(it_service_options.keys()), format_func=lambda x: "---" if x is None else it_service_options.get(x), key="edit_it_service_select")

        if it_service_to_edit_id:
            it_service_details = get_it_service_details(it_service_to_edit_id)
            with st.form(f"edit_it_service_{it_service_to_edit_id}"):
                st.write(f"**Editing: {it_service_details['name']}**")
                edit_it_name = st.text_input("Service Name", value=it_service_details['name'])
                
                provider_keys = [None] + list(provider_options.keys())
                default_provider_id = it_service_details.get('provider_id')
                default_provider_index = provider_keys.index(default_provider_id) if default_provider_id in provider_keys else 0
                edit_provider_id = st.selectbox("Associated Provider", options=provider_keys, format_func=lambda x: "None" if x is None else provider_options.get(x), index=default_provider_index, key="edit_it_provider")

                status_options = ["Active", "In Development", "Retired"]
                default_status = it_service_details.get('status')
                default_status_index = status_options.index(default_status) if default_status in status_options else 0
                edit_status = st.selectbox("Status", options=status_options, index=default_status_index)
                
                sla_keys = [None] + list(sla_options.keys())
                default_sla_id = it_service_details.get('sla_level_id')
                default_sla_index = sla_keys.index(default_sla_id) if default_sla_id in sla_keys else 0
                edit_sla_id = st.selectbox("SLA Level", options=sla_keys, format_func=lambda x: "None" if x is None else sla_options.get(x), index=default_sla_index)

                method_keys = [None] + list(method_options.keys())
                default_method_id = it_service_details.get('service_method_id')
                default_method_index = method_keys.index(default_method_id) if default_method_id in method_keys else 0
                edit_method_id = st.selectbox("Service Method", options=method_keys, format_func=lambda x: "None" if x is None else method_options.get(x), index=default_method_index)

                edit_service_owner = st.text_input("Service Owner/Lead", value=it_service_details.get('service_owner') or '')
                edit_fte_count = st.number_input("Dedicated FTEs", min_value=0, step=1, value=int(it_service_details.get('fte_count') or 0))
                edit_it_desc = st.text_area("Description", value=it_service_details.get('description') or '')
                edit_dependencies = st.text_area("Dependencies", value=it_service_details.get('dependencies') or '')

                del_col, save_col = st.columns([1, 6])
                if save_col.form_submit_button("Save Changes", width='stretch'):
                    update_it_service(it_service_to_edit_id, edit_it_name, edit_it_desc, edit_provider_id, edit_fte_count, edit_dependencies, edit_service_owner, edit_status, edit_sla_id, edit_method_id)
                    st.success(f"Updated {edit_it_name}")
                    st.rerun()
                if del_col.form_submit_button("DELETE", type="primary"):
                    delete_it_service(it_service_to_edit_id)
                    st.warning(f"Deleted service: {it_service_details['name']}")
                    st.rerun()


    # --- DASHBOARD TAB ---
    with dashboard_tab:
        st.header("Dashboard & Recommendations")
        all_apps_df = get_applications()
        all_providers_df = get_providers()
        
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        total_providers = len(all_providers_df)
        total_apps = len(all_apps_df)
        total_annual_cost = all_apps_df['annual_cost'].sum() if 'annual_cost' in all_apps_df.columns else 0.0
        
        metric_col1.metric("Total Providers", total_providers)
        metric_col2.metric("Total Applications", total_apps)
        metric_col3.metric("Total Annual Cost", f"${total_annual_cost:,.2f}")

        st.subheader("Potential Overlaps by Category")
        if not all_apps_df.empty:
            duplicates = all_apps_df.dropna(subset=['category'])[all_apps_df.dropna(subset=['category']).duplicated(subset=['category'], keep=False)].sort_values(by='category')
            if not duplicates.empty:
                st.warning("Found applications in the same category across different providers. Review for potential consolidation.")
                st.dataframe(duplicates[['provider', 'name', 'category', 'annual_cost']], width='stretch')
            else:
                st.success("No overlapping application categories found.")
        else:
            st.info("Add applications to generate recommendations.")

    # --- SETTINGS TAB ---
    with settings_tab:
        st.header("Manage Lookups")
        
        type_col, cat_col = st.columns(2)
        with type_col:
            render_lookup_manager("Application Types", "Application Type", "service_types")
        with cat_col:
            render_lookup_manager("Categories", "Category", "categories")

        st.divider()

        sla_col, method_col = st.columns(2)
        with sla_col:
            render_lookup_manager("SLA Levels", "SLA Level", "sla_levels")
        with method_col:
            render_lookup_manager("Service Methods", "Service Method", "service_methods")

if __name__ == '__main__':
    main()

