import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path

# --- DATABASE SETUP ---
DB_FILE = "portfolio.db"

def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        # Create providers table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
        ''')
        # Create services table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY,
                provider_id INTEGER,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                cost REAL NOT NULL,
                renewal_date TEXT NOT NULL,
                FOREIGN KEY (provider_id) REFERENCES providers (id) ON DELETE CASCADE
            )
        ''')
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
    """Fetches all providers from the database."""
    with get_connection() as con:
        return pd.read_sql_query("SELECT id, name FROM providers ORDER BY name", con)

def add_provider(name):
    """Adds a new provider."""
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("INSERT INTO providers (name) VALUES (?)", (name,))
        con.commit()

def update_provider(provider_id, name):
    """Updates a provider's name."""
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("UPDATE providers SET name = ? WHERE id = ?", (name, provider_id))
        con.commit()

def delete_provider(provider_id):
    """Deletes a provider and all their associated services."""
    with get_connection() as con:
        cur = con.cursor()
        # The ON DELETE CASCADE foreign key constraint handles deleting associated services
        cur.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        con.commit()

# Service Functions
def get_services(provider_id):
    """Fetches all services for a given provider."""
    with get_connection() as con:
        return pd.read_sql_query("SELECT * FROM services WHERE provider_id = ?", con, params=(provider_id,))

def get_all_services():
    """Fetches all services from all providers."""
    with get_connection() as con:
        query = """
        SELECT s.name, s.category, s.cost, p.name as provider_name
        FROM services s
        JOIN providers p ON s.provider_id = p.id
        """
        return pd.read_sql_query(query, con)

def add_service(provider_id, name, category, cost, renewal_date):
    """Adds a new service."""
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO services (provider_id, name, category, cost, renewal_date) VALUES (?, ?, ?, ?, ?)",
            (provider_id, name, category, cost, renewal_date)
        )
        con.commit()

def update_service(service_id, name, category, cost, renewal_date):
    """Updates an existing service."""
    with get_connection() as con:
        cur = con.cursor()
        cur.execute(
            "UPDATE services SET name=?, category=?, cost=?, renewal_date=? WHERE id=?",
            (name, category, cost, renewal_date, service_id)
        )
        con.commit()

def delete_service(service_id):
    """Deletes a service."""
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM services WHERE id = ?", (service_id,))
        con.commit()


# --- STREAMLIT UI ---

def main():
    st.set_page_config(layout="wide", page_title="Service Portfolio Manager")

    # Initialize database
    init_db()

    st.title("Service Portfolio Manager")
    st.write("Track services, identify overlaps, and discover cost-saving opportunities.")

    # Main layout
    col1, col2 = st.columns([1, 2.5])

    with col1:
        st.header("Service Providers")
        providers = get_providers()

        # Add Provider Form
        with st.expander("➕ Add New Provider", expanded=False):
            with st.form("add_provider_form", clear_on_submit=True):
                new_provider_name = st.text_input("Provider Name")
                submitted = st.form_submit_button("Add Provider")
                if submitted and new_provider_name:
                    add_provider(new_provider_name)
                    st.success(f"Added provider: {new_provider_name}")
                    st.rerun()

        # Display Providers
        if not providers.empty:
            for index, provider in providers.iterrows():
                with st.container():
                    sub_col1, sub_col2 = st.columns([3, 1])
                    with sub_col1:
                        if st.button(provider["name"], key=f"select_{provider['id']}", use_container_width=True):
                            st.session_state.selected_provider_id = provider['id']
                            st.session_state.selected_provider_name = provider['name']
                    with sub_col2:
                         if st.button("🗑️", key=f"del_{provider['id']}", help=f"Delete {provider['name']}"):
                            delete_provider(provider['id'])
                            st.rerun()
        else:
            st.info("No providers added yet. Use the form above to add one.")


    with col2:
        if "selected_provider_id" in st.session_state:
            provider_id = st.session_state.selected_provider_id
            provider_name = st.session_state.selected_provider_name

            st.header(f"Services for: {provider_name}")
            services_df = get_services(provider_id)

            # Add Service Form
            with st.expander("➕ Add New Service", expanded=False):
                 with st.form("add_service_form", clear_on_submit=True):
                    service_name = st.text_input("Service/Application Name")
                    service_category = st.selectbox("Category",
                        ["SaaS", "PaaS", "IaaS", "Collaboration", "Project Management", "CRM", "Marketing", "Finance", "HR", "Other"])
                    service_cost = st.number_input("Monthly Cost ($)", min_value=0.0, format="%.2f")
                    service_renewal = st.date_input("Next Renewal Date")
                    submitted = st.form_submit_button("Save Service")
                    if submitted and service_name:
                        add_service(provider_id, service_name, service_category, service_cost, str(service_renewal))
                        st.success(f"Added service '{service_name}' to {provider_name}")
                        st.rerun()

            # Display Services
            if not services_df.empty:
                st.dataframe(services_df[['name', 'category', 'cost', 'renewal_date']], use_container_width=True)
                service_to_delete = st.selectbox("Select a service to delete", options=services_df['name'], index=None, placeholder="Delete a service...")
                if service_to_delete:
                    service_id_to_delete = services_df[services_df['name'] == service_to_delete]['id'].iloc[0]
                    if st.button(f"Confirm Delete '{service_to_delete}'", type="primary"):
                        delete_service(service_id_to_delete)
                        st.rerun()

            else:
                st.info("No services added yet for this provider.")

        else:
            st.info("⬅️ Select a provider from the list to view their services.")

        # --- Dashboard & Recommendations ---
        st.header("Dashboard & Recommendations")
        all_services_df = get_all_services()

        # Metrics
        total_providers = len(providers)
        total_services = len(all_services_df)
        total_monthly_cost = all_services_df['cost'].sum()

        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("Total Providers", total_providers)
        metric_col2.metric("Total Services", total_services)
        metric_col3.metric("Total Monthly Cost", f"${total_monthly_cost:,.2f}")

        # Recommendations
        st.subheader("Potential Overlaps")
        if not all_services_df.empty:
            duplicates = all_services_df[all_services_df.duplicated(subset=['category'], keep=False)].sort_values(by='category')
            if not duplicates.empty:
                st.warning("Found services in the same category across different providers. Review for potential consolidation.")
                st.dataframe(duplicates, use_container_width=True)
            else:
                st.success("No overlapping service categories found. Your portfolio looks streamlined!")
        else:
            st.info("Add services to generate recommendations.")


if __name__ == '__main__':
    main()
