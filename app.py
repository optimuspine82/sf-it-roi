# app.py
import streamlit as st
from config import ALLOWED_EMAILS
import database as db
import ui

# --- AUTHENTICATION ---
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

# --- MAIN APP ---
def main():
    st.set_page_config(layout="wide", page_title="Service Portfolio Manager")
    
    if not check_authentication():
        return

    db.init_db()
    
    user_email = st.session_state.get('user_email', 'unknown')
    
    st.sidebar.success(f"Logged in as {user_email}")
    if st.sidebar.button("Logout"):
        st.session_state['authenticated'] = False
        st.session_state.pop('user_email', None)
        st.rerun()

    st.title("Service Portfolio Manager")
    st.write("Track IT Units, applications, and internal IT services to identify overlaps and cost-saving opportunities.")

    tab_names = ["IT Units", "Applications", "Infrastructure", "IT Services", "Dashboard", "Settings", "Audit Log", "Bulk Import"]
    
    unit_tab, app_tab, infra_tab, service_tab, dashboard_tab, settings_tab, audit_tab, import_tab = st.tabs(tab_names)

    # Render the content for each tab by calling functions from the ui.py module
    with unit_tab:
        ui.render_it_units_tab(user_email)
        
    with app_tab:
        ui.render_applications_tab(user_email)

    with infra_tab:
        ui.render_infrastructure_tab(user_email)

    with service_tab:
        ui.render_services_tab(user_email)

    with dashboard_tab:
        ui.render_dashboard_tab()

    with settings_tab:
        ui.render_settings_tab(user_email)
    
    with audit_tab:
        ui.render_audit_tab()

    with import_tab:
        ui.render_import_tab(user_email)

if __name__ == '__main__':
    main()