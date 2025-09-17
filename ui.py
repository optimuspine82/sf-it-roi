# ui.py
import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import database as db

# --- UI CONSTANTS ---
TAB_INSTRUCTIONS = {
    "IT Units": "Manage the internal IT teams or departments responsible for applications and services. You can add new units, edit their contact and budget information, or delete them here.",
    "Applications": "Track all software applications, whether they are developed internally or purchased from an external vendor. Link each application to the IT Unit that manages it.",
    "Infrastructure": "Track physical or cloud infrastructure components like servers, networks, or storage systems. Assign them to an IT Unit and track costs and lifecycle dates.",
    "IT Services": "Manage all internal services provided by your IT Units, such as the Help Desk or Classroom Support. You can track budget, FTEs, and service level details.",
    "Dashboard": "Get a high-level visual overview of your portfolio. This dashboard highlights total costs, shows spending by vendor, and application distribution by IT Unit.",
    "Settings": "Configure the dropdown options used throughout the application. Add or remove Vendors, Application Types, Categories, etc., to customize the forms to your needs.",
    "Audit Log": "View a complete history of all changes made within the application. You can filter the log by user, item type, or date range to track activity.",
    "Bulk Import": "Upload multiple records at once using a CSV file. Select the data type you wish to import, download the template, fill it in, and upload it here."
}

# --- UI HELPER FUNCTIONS ---
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
                db.add_lookup_item(user_email, table_name, new_name)
                st.rerun()
    
    items = db.get_lookup_data(table_name)
    for _, row in items.iterrows():
        item_id, item_name = row['id'], row['name']
        is_editing = ('editing_lookup_item' in st.session_state and
                      st.session_state.editing_lookup_item['table'] == table_name and
                      st.session_state.editing_lookup_item['id'] == item_id)

        if is_editing:
            with st.form(key=f"edit_lookup_{table_name}_{item_id}"):
                new_item_name = st.text_input("New Name", value=item_name)
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Save", type="primary"):
                    db.update_lookup_item(user_email, table_name, item_id, new_item_name)
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

# --- TAB RENDERING FUNCTIONS ---
def render_it_units_tab(user_email):
    st.header("Manage IT Units")
    st.info(TAB_INSTRUCTIONS["IT Units"])
    
    with st.expander("➕ Add New IT Unit"):
        with st.form("add_unit_form", clear_on_submit=True):
            st.write("Fields marked with an * are required.")
            name = st.text_input("IT Unit Name*")
            contact_person = st.text_input("Contact Person*")
            contact_email = st.text_input("Contact Email")
            total_fte = st.number_input("Total FTE", min_value=0, step=1)
            budget_amount = st.number_input("Annual Budget ($)", min_value=0.0, format="%.2f")
            notes = st.text_area("Notes", height=150)
            
            if st.form_submit_button("Add IT Unit"):
                if not name or not contact_person:
                    st.warning("Please fill in all required fields.")
                else:
                    result = db.add_it_unit(user_email, name, contact_person, contact_email, total_fte, budget_amount, notes)
                    if isinstance(result, str):
                        st.warning(result)
                    else:
                        st.rerun()
    
    st.divider()
    it_units_df_all = db.get_it_units()
    search_unit = st.text_input("Search IT Units by Name")
    
    filtered_units_df = it_units_df_all
    if search_unit:
        filtered_units_df = it_units_df_all[it_units_df_all['name'].str.contains(search_unit, case=False, na=False)]

    st.subheader("Edit or Delete an IT Unit")
    
    unit_options = dict(zip(filtered_units_df['id'], filtered_units_df['name']))
    unit_to_edit_id = st.selectbox("Select an IT Unit", options=[None] + list(unit_options.keys()), format_func=lambda x: "---" if x is None else unit_options.get(x))

    if unit_to_edit_id:
        unit_details = db.get_it_unit_details(unit_to_edit_id)
        if 'confirming_delete_unit' in st.session_state and st.session_state.confirming_delete_unit == unit_to_edit_id:
            st.warning(f"**Are you sure you want to delete '{unit_details['name']}'?** This removes its association from any items.")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete it", key="confirm_del_unit"):
                db.delete_it_unit(user_email, unit_to_edit_id, unit_details['name'])
                st.session_state.pop('confirming_delete_unit', None)
                st.success(f"Deleted IT Unit: {unit_details['name']}")
                st.rerun()
            if c2.button("Cancel", key="cancel_del_unit"):
                st.session_state.pop('confirming_delete_unit', None)
                st.rerun()

        with st.form("edit_unit_form"):
            st.write(f"**Editing: {unit_details['name']}** (Fields with * are required)")
            name = st.text_input("IT Unit Name*", value=unit_details['name'])
            contact_person = st.text_input("Contact Person*", value=unit_details.get('contact_person') or '')
            contact_email = st.text_input("Contact Email", value=unit_details.get('contact_email') or '')
            total_fte = st.number_input("Total FTE", min_value=0, step=1, value=int(unit_details.get('total_fte') or 0))
            budget_amount = st.number_input("Annual Budget ($)", min_value=0.0, format="%.2f", value=float(unit_details.get('budget_amount') or 0.0))
            notes = st.text_area("Notes", value=unit_details.get('notes') or '', height=150)
            
            del_col, save_col = st.columns([1, 6])
            if save_col.form_submit_button("Save Changes", width='stretch', type="primary"):
                if not name or not contact_person:
                    st.warning("Please fill in all required fields.")
                else:
                    result = db.update_it_unit_details(user_email, unit_to_edit_id, name, contact_person, contact_email, total_fte, budget_amount, notes)
                    if isinstance(result, str):
                        st.warning(result)
                    else:
                        st.success(f"Updated details for {name}")
                        st.rerun()
            if del_col.form_submit_button("DELETE"):
                st.session_state.confirming_delete_unit = unit_to_edit_id
                st.rerun()

    st.subheader("All IT Units")
    st.dataframe(filtered_units_df, width='stretch')
    csv_units = convert_df_to_csv(filtered_units_df)
    st.download_button(label="Download data as CSV", data=csv_units, file_name='it_units_export.csv', mime='text/csv')

def render_applications_tab(user_email):
    st.header("Manage Applications")
    st.info(TAB_INSTRUCTIONS["Applications"])
    
    applications_df = db.get_applications()
    it_units_df_all = db.get_it_units()
    vendors_df = db.get_lookup_data('vendors')
    categories_df = db.get_lookup_data('categories')
    
    it_unit_options_all = dict(zip(it_units_df_all['id'], it_units_df_all['name']))
    vendor_options_all = dict(zip(vendors_df['id'], vendors_df['name']))
    category_options_all = dict(zip(categories_df['id'], categories_df['name']))
    
    app_labels = {
        row['id']: f"{row['name']} (Unit: {row.get('managing_it_unit', 'N/A')}) - ID: {row['id']}"
        for _, row in applications_df.iterrows()
    }
    
    with st.expander("➕ Add New Application"):
        if it_units_df_all.empty or vendors_df.empty or categories_df.empty:
            st.warning("To add an application, please ensure at least one IT Unit, one Vendor, and one Category have been created in the 'IT Units' and 'Settings' tabs.")
        else:
            app_to_copy_id = st.selectbox(
                "Or, copy an existing item to start...",
                options=[None] + list(applications_df['id']),
                format_func=lambda x: "---" if x is None else app_labels.get(x),
                key="copy_app_select"
            )
            
            default_vals = {}
            if app_to_copy_id:
                default_vals = db.get_application_details(app_to_copy_id)

            with st.form("add_app_form", clear_on_submit=True):
                st.write("Fields marked with an * are required.")
                app_name = st.text_input("Application Name*", value=default_vals.get('name', ''))
                
                unit_keys = list(it_unit_options_all.keys())
                default_unit_idx = unit_keys.index(default_vals.get('it_unit_id')) if default_vals.get('it_unit_id') in unit_keys else 0
                it_unit_id = st.selectbox("Managing IT Unit*", options=unit_keys, format_func=it_unit_options_all.get, index=default_unit_idx)
                
                vendor_keys = list(vendor_options_all.keys())
                default_vendor_idx = vendor_keys.index(default_vals.get('vendor_id')) if default_vals.get('vendor_id') in vendor_keys else 0
                vendor_id = st.selectbox("Vendor*", options=vendor_keys, format_func=vendor_options_all.get, index=default_vendor_idx)
                
                category_keys = list(category_options_all.keys())
                default_cat_idx = category_keys.index(default_vals.get('category_id')) if default_vals.get('category_id') in category_keys else 0
                category_id = st.selectbox("Category*", options=category_keys, format_func=category_options_all.get, index=default_cat_idx)
                
                service_type_options_all = dict(db.get_lookup_data('service_types')[['id', 'name']].values)
                type_keys = list(service_type_options_all.keys())
                default_type_idx = type_keys.index(default_vals.get('service_type_id')) if default_vals.get('service_type_id') in type_keys else 0
                service_type_id = st.selectbox("Type", options=type_keys, format_func=service_type_options_all.get, index=default_type_idx)

                service_owner = st.text_input("Service Owner/Lead", value=default_vals.get('service_owner', ''))
                annual_cost = st.number_input("Annual Cost ($)", min_value=0.0, format="%.2f", value=float(default_vals.get('annual_cost', 0.0)))
                renewal_date = st.date_input("Next Renewal Date", value=pd.to_datetime(default_vals.get('renewal_date')) if pd.notna(default_vals.get('renewal_date')) else None)
                integrations = st.text_area("Known Integrations", value=default_vals.get('integrations', ''))
                description = st.text_area("Description", value=default_vals.get('description', ''), height=100)
                similar_apps = st.text_area("Similar Applications (if any)", value=default_vals.get('similar_applications', ''))
                
                if st.form_submit_button("Save Application"):
                    if not all([app_name, it_unit_id, vendor_id, category_id]):
                        st.warning("Please fill in all required fields.")
                    else:
                        result = db.add_application(user_email, app_name, it_unit_id, vendor_id, category_id, service_type_id, annual_cost, str(renewal_date) if renewal_date else None, integrations, description, similar_apps, service_owner)
                        if isinstance(result, str):
                            st.warning(result)
                        else:
                            st.rerun()

    st.divider()
    st.subheader("Filter and Search Applications")
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    search_app = fcol1.text_input("Search by Name")
    filter_unit = fcol2.multiselect("Filter by IT Unit", options=it_unit_options_all.values())
    filter_vendor = fcol3.multiselect("Filter by Vendor", options=vendor_options_all.values())
    category_options_filter = dict(db.get_lookup_data('categories')[['id', 'name']].values)
    filter_category = fcol4.multiselect("Filter by Category", options=category_options_filter.values())
    
    filtered_apps_df = applications_df.copy()
    
    if search_app: filtered_apps_df = filtered_apps_df[filtered_apps_df['name'].str.contains(search_app, case=False, na=False)]
    if filter_unit: filtered_apps_df = filtered_apps_df[filtered_apps_df['managing_it_unit'].isin(filter_unit)]
    if filter_vendor: filtered_apps_df = filtered_apps_df[filtered_apps_df['vendor'].isin(filter_vendor)]
    if filter_category: filtered_apps_df = filtered_apps_df[filtered_apps_df['category'].isin(filter_category)]

    st.dataframe(filtered_apps_df, width='stretch')
    csv_apps = convert_df_to_csv(filtered_apps_df)
    st.download_button(label="Download data as CSV", data=csv_apps, file_name='applications_export.csv', mime='text/csv')

    st.subheader("Edit or Delete an Application")
    
    app_to_edit_id = st.selectbox(
        "Select an application",
        options=[None] + list(app_labels.keys()),
        format_func=lambda x: "---" if x is None else app_labels.get(x)
    )

    if app_to_edit_id:
        app_details = db.get_application_details(app_to_edit_id)
        if 'confirming_delete_app' in st.session_state and st.session_state.confirming_delete_app == app_to_edit_id:
            st.warning(f"**Are you sure you want to delete the application '{app_details['name']}'?**")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete it", key="confirm_del_app"):
                db.delete_application(user_email, app_to_edit_id, app_details['name'])
                st.session_state.pop('confirming_delete_app', None)
                st.success(f"Deleted application: {app_details['name']}")
                st.rerun()
            if c2.button("Cancel", key="cancel_del_app"):
                st.session_state.pop('confirming_delete_app', None)
                st.rerun()
        
        with st.form(f"edit_app_form_{app_to_edit_id}"):
            st.write(f"**Editing: {app_details['name']}** (Fields with * are required)")
            edit_name = st.text_input("Application Name*", value=app_details['name'])
            
            default_unit_idx = list(it_unit_options_all.keys()).index(app_details['it_unit_id']) if app_details.get('it_unit_id') in it_unit_options_all else 0
            edit_it_unit_id = st.selectbox("Managing IT Unit*", options=it_unit_options_all.keys(), format_func=it_unit_options_all.get, index=default_unit_idx)
            
            default_vendor_idx = list(vendor_options_all.keys()).index(app_details.get('vendor_id')) if app_details.get('vendor_id') in vendor_options_all else 0
            edit_vendor_id = st.selectbox("Vendor*", options=list(vendor_options_all.keys()), format_func=vendor_options_all.get, index=default_vendor_idx)
            
            default_cat_idx = list(category_options_all.keys()).index(app_details['category_id']) if app_details.get('category_id') in category_options_all else 0
            edit_category_id = st.selectbox("Category*", options=list(category_options_all.keys()), format_func=category_options_all.get, index=default_cat_idx)
            
            type_options_all = dict(db.get_lookup_data('service_types')[['id', 'name']].values)
            default_type_idx = list(type_options_all.keys()).index(app_details.get('service_type_id')) if app_details.get('service_type_id') in type_options_all else 0
            edit_type_id = st.selectbox("Type", options=list(type_options_all.keys()), format_func=type_options_all.get, index=default_type_idx)
            
            edit_service_owner = st.text_input("Service Owner/Lead", value=app_details.get('service_owner') or '')
            edit_annual_cost = st.number_input("Annual Cost ($)", min_value=0.0, format="%.2f", value=float(app_details.get('annual_cost') or 0.0))
            edit_renewal = st.date_input("Next Renewal Date", value=pd.to_datetime(app_details['renewal_date']) if pd.notna(app_details['renewal_date']) else None)
            edit_integrations = st.text_area("Known Integrations", value=app_details.get('integrations') or '')
            edit_description = st.text_area("Description", value=app_details.get('description') or '', height=100)
            edit_similar_apps = st.text_area("Similar Applications", value=app_details.get('similar_applications') or '')

            del_col, save_col = st.columns([1, 6])
            if save_col.form_submit_button("Save Changes", width='stretch', type="primary"):
                if not all([edit_name, edit_it_unit_id, edit_vendor_id, edit_category_id]):
                    st.warning("Please fill in all required fields.")
                else:
                    result = db.update_application(user_email, app_to_edit_id, edit_name, edit_it_unit_id, edit_vendor_id, edit_category_id, edit_type_id, edit_annual_cost, str(edit_renewal) if edit_renewal else None, edit_integrations, edit_description, edit_similar_apps, edit_service_owner)
                    if isinstance(result, str):
                        st.warning(result)
                    else:
                        st.success("Application updated.")
                        st.rerun()
            if del_col.form_submit_button("DELETE"):
                st.session_state.confirming_delete_app = app_to_edit_id
                st.rerun()

def render_infrastructure_tab(user_email):
    st.header("Manage Infrastructure")
    st.info(TAB_INSTRUCTIONS["Infrastructure"])
    
    it_units_df_all = db.get_it_units()
    it_unit_options_all = dict(zip(it_units_df_all['id'], it_units_df_all['name']))
    vendor_options_all = dict(zip(db.get_lookup_data('vendors')['id'], db.get_lookup_data('vendors')['name']))
    
    infra_df = db.get_infrastructure()
    infra_options_all = dict(zip(infra_df['id'], infra_df['name']))

    with st.expander("➕ Add New Infrastructure"):
        if it_units_df_all.empty:
            st.warning("Please add at least one IT Unit before adding infrastructure.")
        else:
            infra_to_copy_id = st.selectbox(
                "Or, copy an existing item to start...",
                options=[None] + list(infra_options_all.keys()),
                format_func=lambda x: "---" if x is None else infra_options_all.get(x),
                key="copy_infra_select"
            )
            
            default_vals = {}
            if infra_to_copy_id:
                default_vals = db.get_infrastructure_details(infra_to_copy_id)

            with st.form("add_infra_form", clear_on_submit=True):
                st.write("Fields marked with an * are required.")
                name = st.text_input("Infrastructure Name*", value=default_vals.get('name', ''))
                
                unit_keys = list(it_unit_options_all.keys())
                default_unit_idx = unit_keys.index(default_vals.get('it_unit_id')) if default_vals.get('it_unit_id') in unit_keys else 0
                it_unit_id = st.selectbox("Managing IT Unit*", options=unit_keys, format_func=it_unit_options_all.get, index=default_unit_idx)
                
                vendor_keys = [None] + list(vendor_options_all.keys())
                default_vendor_idx = vendor_keys.index(default_vals.get('vendor_id')) if default_vals.get('vendor_id') in vendor_keys else 0
                vendor_id = st.selectbox("Vendor (Optional)", options=vendor_keys, format_func=lambda x: "None" if x is None else vendor_options_all.get(x), index=default_vendor_idx)
                
                location = st.text_input("Location (e.g., Data Center, Cloud Region)", value=default_vals.get('location', ''))
                status_options = ["Production", "Staging", "Development", "Decommissioned"]
                default_status_idx = status_options.index(default_vals.get('status')) if default_vals.get('status') in status_options else 0
                status = st.selectbox("Status", options=status_options, index=default_status_idx)
                
                purchase_date = st.date_input("Purchase Date", value=pd.to_datetime(default_vals.get('purchase_date')) if pd.notna(default_vals.get('purchase_date')) else None)
                warranty_expiry = st.date_input("Warranty Expiry Date", value=pd.to_datetime(default_vals.get('warranty_expiry')) if pd.notna(default_vals.get('warranty_expiry')) else None)
                cost = st.number_input("Annual Maintenance Cost ($)", min_value=0.0, format="%.2f", value=float(default_vals.get('annual_maintenance_cost', 0.0)))
                description = st.text_area("Description", value=default_vals.get('description', ''))

                if st.form_submit_button("Save Infrastructure"):
                    if not name or not it_unit_id:
                        st.warning("Please fill in all required fields.")
                    else:
                        result = db.add_infrastructure(user_email, name, it_unit_id, vendor_id, location, status, str(purchase_date) if purchase_date else None, str(warranty_expiry) if warranty_expiry else None, cost, description)
                        if isinstance(result, str):
                            st.warning(result)
                        else:
                            st.rerun()

    st.divider()
    st.subheader("Filter and Search Infrastructure")
    infra_f1, infra_f2, infra_f3, infra_f4 = st.columns(4)
    search_infra = infra_f1.text_input("Search by Name", key="infra_search")
    filter_infra_unit = infra_f2.multiselect("Filter by IT Unit", options=list(it_unit_options_all.values()), key="infra_unit_filter")
    filter_infra_vendor = infra_f3.multiselect("Filter by Vendor", options=list(vendor_options_all.values()), key="infra_vendor_filter")
    filter_infra_status = infra_f4.multiselect("Filter by Status", options=["Production", "Staging", "Development", "Decommissioned"], key="infra_status_filter")
    
    filtered_infra_df = infra_df.copy()

    if search_infra: filtered_infra_df = filtered_infra_df[filtered_infra_df['name'].str.contains(search_infra, case=False, na=False)]
    if filter_infra_unit: filtered_infra_df = filtered_infra_df[filtered_infra_df['managing_it_unit'].isin(filter_infra_unit)]
    if filter_infra_vendor: filtered_infra_df = filtered_infra_df[filtered_infra_df['vendor'].isin(filter_infra_vendor)]
    if filter_infra_status: filtered_infra_df = filtered_infra_df[filtered_infra_df['status'].isin(filter_infra_status)]
    
    st.dataframe(filtered_infra_df, width='stretch')
    csv_infra = convert_df_to_csv(filtered_infra_df)
    st.download_button(label="Download data as CSV", data=csv_infra, file_name='infrastructure_export.csv', mime='text/csv')

    st.subheader("Edit or Delete Infrastructure")
    infra_to_edit_id = st.selectbox("Select an item to Edit/Delete", options=[None] + list(infra_options_all.keys()), format_func=lambda x: "---" if x is None else infra_options_all.get(x))

    if infra_to_edit_id:
        infra_details = db.get_infrastructure_details(infra_to_edit_id)
        if 'confirming_delete_infra' in st.session_state and st.session_state.confirming_delete_infra == infra_to_edit_id:
            st.warning(f"**Are you sure you want to delete '{infra_details['name']}'?**")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete it", key="confirm_del_infra"):
                db.delete_infrastructure(user_email, infra_to_edit_id, infra_details['name'])
                st.session_state.pop('confirming_delete_infra', None)
                st.success(f"Deleted: {infra_details['name']}")
                st.rerun()
            if c2.button("Cancel", key="cancel_del_infra"):
                st.session_state.pop('confirming_delete_infra', None)
                st.rerun()
        
        with st.form(f"edit_infra_form_{infra_to_edit_id}"):
            st.write(f"**Editing: {infra_details['name']}** (Fields with * are required)")
            edit_name = st.text_input("Name*", value=infra_details['name'])
            
            default_unit_idx = list(it_unit_options_all.keys()).index(infra_details['it_unit_id']) if infra_details.get('it_unit_id') in it_unit_options_all else 0
            edit_it_unit_id = st.selectbox("Managing IT Unit*", options=list(it_unit_options_all.keys()), format_func=it_unit_options_all.get, index=default_unit_idx)

            vendor_keys = [None] + list(vendor_options_all.keys())
            default_vendor_idx = vendor_keys.index(infra_details.get('vendor_id')) if infra_details.get('vendor_id') in vendor_keys else 0
            edit_vendor_id = st.selectbox("Vendor (Optional)", options=vendor_keys, format_func=lambda x: "None" if x is None else vendor_options_all.get(x), index=default_vendor_idx)
            
            edit_location = st.text_input("Location", value=infra_details.get('location') or '')
            status_options = ["Production", "Staging", "Development", "Decommissioned"]
            default_status_idx = status_options.index(infra_details.get('status')) if infra_details.get('status') in status_options else 0
            edit_status = st.selectbox("Status", options=status_options, index=default_status_idx)
            
            edit_purchase_date = st.date_input("Purchase Date", value=pd.to_datetime(infra_details['purchase_date']) if pd.notna(infra_details['purchase_date']) else None)
            edit_warranty_expiry = st.date_input("Warranty Expiry Date", value=pd.to_datetime(infra_details['warranty_expiry']) if pd.notna(infra_details['warranty_expiry']) else None)
            edit_cost = st.number_input("Annual Maintenance Cost ($)", min_value=0.0, format="%.2f", value=float(infra_details.get('annual_maintenance_cost') or 0.0))
            edit_description = st.text_area("Description", value=infra_details.get('description') or '')

            del_col, save_col = st.columns([1, 6])
            if save_col.form_submit_button("Save Changes", width='stretch', type="primary"):
                if not edit_name or not edit_it_unit_id:
                    st.warning("Please fill in all required fields.")
                else:
                    result = db.update_infrastructure(user_email, infra_to_edit_id, edit_name, edit_it_unit_id, edit_vendor_id, edit_location, edit_status, str(edit_purchase_date) if edit_purchase_date else None, str(edit_warranty_expiry) if edit_warranty_expiry else None, edit_cost, edit_description)
                    if isinstance(result, str):
                        st.warning(result)
                    else:
                        st.success("Infrastructure item updated.")
                        st.rerun()
            if del_col.form_submit_button("DELETE"):
                st.session_state.confirming_delete_infra = infra_to_edit_id
                st.rerun()

def render_services_tab(user_email):
    st.header("Manage Internal IT Services")
    st.info(TAB_INSTRUCTIONS["IT Services"])

    it_services_df = db.get_it_services()
    it_service_options_all = dict(zip(it_services_df['id'], it_services_df['name']))
    it_unit_options_all = dict(zip(db.get_it_units()['id'], db.get_it_units()['name']))

    with st.expander("➕ Add New IT Service"):
        if not it_unit_options_all:
            st.warning("Please add at least one IT Unit before adding a service.")
        else:
            service_to_copy_id = st.selectbox(
                "Or, copy an existing item to start...",
                options=[None] + list(it_service_options_all.keys()),
                format_func=lambda x: "---" if x is None else it_service_options_all.get(x),
                key="copy_service_select"
            )
            
            default_vals = {}
            if service_to_copy_id:
                default_vals = db.get_it_service_details(service_to_copy_id)

            with st.form("add_it_service_form", clear_on_submit=True):
                st.write("Fields marked with an * are required.")
                it_service_name = st.text_input("Service Name*", value=default_vals.get('name', ''))
                
                unit_keys = list(it_unit_options_all.keys())
                default_unit_idx = unit_keys.index(default_vals.get('it_unit_id')) if default_vals.get('it_unit_id') in unit_keys else 0
                it_unit_id = st.selectbox("Providing IT Unit*", options=unit_keys, format_func=it_unit_options_all.get, index=default_unit_idx)
                
                status_options = ["Active", "In Development", "Retired"]
                default_status_idx = status_options.index(default_vals.get('status')) if default_vals.get('status') in status_options else 0
                status = st.selectbox("Status", options=status_options, index=default_status_idx)

                service_owner = st.text_input("Service Owner/Lead", value=default_vals.get('service_owner', ''))
                fte_count = st.number_input("Dedicated FTEs", min_value=0, step=1, value=int(default_vals.get('fte_count', 0)))
                budget_allocation = st.number_input("Budget Allocation ($)", min_value=0.0, format="%.2f", value=float(default_vals.get('budget_allocation', 0.0)))

                sla_options_all = dict(db.get_lookup_data('sla_levels')[['id', 'name']].values)
                sla_keys = [None] + list(sla_options_all.keys())
                default_sla_idx = sla_keys.index(default_vals.get('sla_level_id')) if default_vals.get('sla_level_id') in sla_keys else 0
                sla_id = st.selectbox("SLA Level", options=sla_keys, format_func=lambda x: "None" if x is None else sla_options_all.get(x), index=default_sla_idx)

                method_options_all = dict(db.get_lookup_data('service_methods')[['id', 'name']].values)
                method_keys = [None] + list(method_options_all.keys())
                default_method_idx = method_keys.index(default_vals.get('service_method_id')) if default_vals.get('service_method_id') in method_keys else 0
                method_id = st.selectbox("Service Method", options=method_keys, format_func=lambda x: "None" if x is None else method_options_all.get(x), index=default_method_idx)
                
                it_service_desc = st.text_area("Description", value=default_vals.get('description', ''))
                dependencies = st.text_area("Dependencies (e.g., other apps, services)", value=default_vals.get('dependencies', ''))
                
                if st.form_submit_button("Add Service"):
                    if not it_service_name or not it_unit_id:
                        st.warning("Please fill in all required fields.")
                    else:
                        result = db.add_it_service(user_email, it_service_name, it_unit_id, it_service_desc, fte_count, dependencies, service_owner, status, sla_id, method_id, budget_allocation)
                        if isinstance(result, str):
                            st.warning(result)
                        else:
                            st.rerun()
                            
    st.divider()
    st.subheader("Filter and Search IT Services")
    fscol1, fscol2, fscol3, fscol4 = st.columns(4)
    search_its = fscol1.text_input("Search by Name", key="it_search")
    filter_unit_its = fscol2.multiselect("Filter by IT Unit", options=list(it_unit_options_all.values()), key="it_unit_filter")
    filter_status_its = fscol3.multiselect("Status", options=["Active", "In Development", "Retired"], key="it_status_filter")
    sla_options_all = dict(db.get_lookup_data('sla_levels')[['id', 'name']].values)
    filter_sla_its = fscol4.multiselect("SLA Level", options=list(sla_options_all.values()), key="it_sla_filter")

    filtered_its_df = it_services_df.copy()

    if search_its: filtered_its_df = filtered_its_df[filtered_its_df['name'].str.contains(search_its, case=False, na=False)]
    if filter_unit_its: filtered_its_df = filtered_its_df[filtered_its_df['providing_it_unit'].isin(filter_unit_its)]
    if filter_status_its: filtered_its_df = filtered_its_df[filtered_its_df['status'].isin(filter_status_its)]
    if filter_sla_its: filtered_its_df = filtered_its_df[filtered_its_df['sla_level'].isin(filter_sla_its)]

    st.dataframe(filtered_its_df, width='stretch')
    csv_its = convert_df_to_csv(filtered_its_df)
    st.download_button(label="Download data as CSV", data=csv_its, file_name='it_services_export.csv', mime='text/csv')
    
    st.subheader("Edit or Delete an IT Service")
    it_service_to_edit_id = st.selectbox("Select a service to Edit/Delete", options=[None] + list(it_service_options_all.keys()), format_func=lambda x: "---" if x is None else it_service_options_all.get(x))

    if it_service_to_edit_id:
        it_service_details = db.get_it_service_details(it_service_to_edit_id)
        if 'confirming_delete_service' in st.session_state and st.session_state.confirming_delete_service == it_service_to_edit_id:
            st.warning(f"**Are you sure you want to delete the IT Service '{it_service_details['name']}'?**")
            c1, c2 = st.columns(2)
            if c1.button("Yes, delete it", key="confirm_del_service"):
                db.delete_it_service(user_email, it_service_to_edit_id, it_service_details['name'])
                st.session_state.pop('confirming_delete_service', None)
                st.success(f"Deleted IT Service: {it_service_details['name']}")
                st.rerun()
            if c2.button("Cancel", key="cancel_del_service"):
                st.session_state.pop('confirming_delete_service', None)
                st.rerun()

        with st.form(f"edit_it_service_{it_service_to_edit_id}"):
            st.write(f"**Editing: {it_service_details['name']}** (Fields with * are required)")
            edit_it_name = st.text_input("Service Name*", value=it_service_details['name'])
            
            default_unit_idx = list(it_unit_options_all.keys()).index(it_service_details.get('it_unit_id')) if it_service_details.get('it_unit_id') in it_unit_options_all else 0
            edit_it_unit_id = st.selectbox("Providing IT Unit*", options=list(it_unit_options_all.keys()), format_func=it_unit_options_all.get, index=default_unit_idx)
            
            status_options = ["Active", "In Development", "Retired"]
            default_status_idx = status_options.index(it_service_details.get('status')) if it_service_details.get('status') in status_options else 0
            edit_status = st.selectbox("Status", options=status_options, index=default_status_idx)
            
            sla_keys = [None] + list(sla_options_all.keys())
            default_sla_idx = sla_keys.index(it_service_details.get('sla_level_id')) if it_service_details.get('sla_level_id') in sla_keys else 0
            edit_sla_id = st.selectbox("SLA Level", options=sla_keys, format_func=lambda x: "None" if x is None else sla_options_all.get(x), index=default_sla_idx)

            method_options_all = dict(db.get_lookup_data('service_methods')[['id', 'name']].values)
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
                if not edit_it_name or not edit_it_unit_id:
                    st.warning("Please fill in all required fields.")
                else:
                    result = db.update_it_service(user_email, it_service_to_edit_id, edit_it_name, edit_it_desc, edit_it_unit_id, edit_fte_count, edit_dependencies, edit_service_owner, edit_status, edit_sla_id, edit_method_id, edit_budget)
                    if isinstance(result, str):
                        st.warning(result)
                    else:
                        st.success(f"Updated {edit_it_name}")
                        st.rerun()
            if del_col.form_submit_button("DELETE"):
                st.session_state.confirming_delete_service = it_service_to_edit_id
                st.rerun()

def render_dashboard_tab():
    st.header("Dashboard & Recommendations")
    st.info(TAB_INSTRUCTIONS["Dashboard"])
    
    all_apps_df = db.get_applications()
    all_it_units_df = db.get_it_units()
    all_it_services_df = db.get_it_services()
    all_infra_df = db.get_infrastructure()
    
    st.subheader("High-Level Metrics")
    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
    
    total_annual_cost = all_apps_df['annual_cost'].sum() if not all_apps_df.empty else 0.0
    total_it_budget = all_it_services_df['budget_allocation'].sum() if not all_it_services_df.empty else 0.0
    total_maint_cost = all_infra_df['annual_maintenance_cost'].sum() if not all_infra_df.empty else 0.0
    
    metric_col1.metric("Total IT Units", len(all_it_units_df))
    metric_col2.metric("Total Applications", len(all_apps_df))
    metric_col3.metric("Total Infrastructure", len(all_infra_df))
    metric_col4.metric("Total IT Services", len(all_it_services_df))
    metric_col5.metric("Total Annual Spend/Budget", f"${(total_annual_cost + total_it_budget + total_maint_cost):,.2f}")

    st.divider()
    st.subheader("Consolidation Opportunities")

    if not all_apps_df.empty:
        app_duplicates = all_apps_df[all_apps_df.duplicated(subset=['name'], keep=False)].sort_values(by='name')
        if not app_duplicates.empty:
            st.warning("Duplicate Applications Found Across IT Units")
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
        mask = all_apps_df['category'].notna() & all_apps_df.duplicated(subset=['category'], keep=False)
        category_duplicates = all_apps_df[mask].sort_values(by='category')

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
            apps_by_unit.columns = ['managing_it_unit', 'count']
            fig_apps_by_unit = px.pie(apps_by_unit, names='managing_it_unit', values='count', title='Application Count by Managing IT Unit')
            st.plotly_chart(fig_apps_by_unit, use_container_width=True)

        with chart_col2:
            apps_by_category = all_apps_df['category'].value_counts().reset_index()
            apps_by_category.columns = ['category', 'count']
            fig_app_category = px.bar(apps_by_category, x='category', y='count', title='Application Count by Category')
            st.plotly_chart(fig_app_category, use_container_width=True)
    else:
        st.info("Add applications to see application-specific insights.")
    
    if not all_infra_df.empty:
        st.divider()
        st.subheader("Infrastructure Visual Insights")
        infra_chart1, infra_chart2 = st.columns(2)
        with infra_chart1:
            maint_cost_by_vendor = all_infra_df.groupby('vendor')['annual_maintenance_cost'].sum().reset_index()
            fig_maint_cost = px.pie(maint_cost_by_vendor, names='vendor', values='annual_maintenance_cost', title='Annual Maintenance Cost by Vendor')
            st.plotly_chart(fig_maint_cost, use_container_width=True)
        with infra_chart2:
            infra_by_unit = all_infra_df['managing_it_unit'].value_counts().reset_index()
            infra_by_unit.columns = ['managing_it_unit', 'count']
            fig_infra_by_unit = px.pie(infra_by_unit, names='managing_it_unit', values='count', title='Infrastructure Count by Managing IT Unit')
            st.plotly_chart(fig_infra_by_unit, use_container_width=True)

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

def render_settings_tab(user_email):
    st.header("Manage Lookups")
    st.info(TAB_INSTRUCTIONS["Settings"])

    if 'confirming_delete_lookup' in st.session_state and st.session_state.confirming_delete_lookup:
        item = st.session_state.confirming_delete_lookup
        st.warning(f"**Are you sure you want to delete the lookup item '{item['name']}'?**")
        c1, c2 = st.columns(2)
        if c1.button("Yes, delete it", key="confirm_del_lookup"):
            db.delete_lookup_item(user_email, item['table'], item['id'], item['name'])
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

def render_audit_tab():
    st.header("Audit Log")
    st.info(TAB_INSTRUCTIONS["Audit Log"])

    audit_df = db.get_audit_log()
    
    st.subheader("Filter Audit Log")
    log_f1, log_f2, log_f3 = st.columns(3)

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

def render_import_tab(user_email):
    st.header("Bulk Import from CSV")
    st.info(TAB_INSTRUCTIONS["Bulk Import"])
    
    template_cols = {
        "IT Units": ["name", "contact_person", "contact_email", "total_fte", "budget_amount", "notes"],
        "Applications": ["name", "service_owner", "managing_it_unit_name", "vendor_name", "type_name", "category_name", "annual_cost", "renewal_date", "integrations", "description", "similar_applications"],
        "Infrastructure": ["name", "managing_it_unit_name", "vendor_name", "location", "status", "purchase_date", "warranty_expiry", "annual_maintenance_cost", "description"],
        "IT Services": ["name", "providing_it_unit_name", "status", "service_owner", "fte_count", "budget_allocation", "sla_level_name", "service_method_name", "description", "dependencies"]
    }

    import_type = st.selectbox("1. Select data type to import", options=list(template_cols.keys()))

    st.subheader("2. Download and Fill Template")
    st.markdown(f"Download the template for **{import_type}**, fill it in, and save it as a CSV file. **Do not change the column headers.**")
    
    template_df = pd.DataFrame(columns=template_cols[import_type])
    template_csv = convert_df_to_csv(template_df)
    st.download_button(
        label=f"Download {import_type} Template",
        data=template_csv,
        file_name=f"{import_type.lower().replace(' ', '_')}_template.csv",
        mime='text/csv'
    )
    
    st.divider()
    st.subheader("3. Upload Completed CSV File")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded_file is not None:
        try:
            import_df = pd.read_csv(uploaded_file)
            
            if not all(col in import_df.columns for col in template_cols[import_type]):
                st.error(f"The uploaded file is missing one or more required columns. Please use the template provided. Required columns: {template_cols[import_type]}")
            else:
                st.success("File uploaded successfully. Click the button below to process the records.")
                if st.button(f"Process {import_type} Import", type="primary"):
                    process_import(import_type, import_df, user_email)

        except Exception as e:
            st.error(f"An error occurred while reading the file: {e}")


def process_import(import_type, df, user_email):
    """Main function to route the import DF to the correct processor."""
    success_log = []
    error_log = []
    
    it_units_map = pd.read_sql("SELECT id, name FROM it_units", db.get_connection()).set_index('name')['id'].to_dict()
    vendors_map = pd.read_sql("SELECT id, name FROM vendors", db.get_connection()).set_index('name')['id'].to_dict()
    types_map = pd.read_sql("SELECT id, name FROM service_types", db.get_connection()).set_index('name')['id'].to_dict()
    categories_map = pd.read_sql("SELECT id, name FROM categories", db.get_connection()).set_index('name')['id'].to_dict()
    slas_map = pd.read_sql("SELECT id, name FROM sla_levels", db.get_connection()).set_index('name')['id'].to_dict()
    methods_map = pd.read_sql("SELECT id, name FROM service_methods", db.get_connection()).set_index('name')['id'].to_dict()

    with st.spinner(f"Importing {len(df)} records for {import_type}..."):
        for index, row in df.iterrows():
            try:
                # Validation for required fields
                if import_type == "IT Units" and (pd.isna(row.get('name')) or pd.isna(row.get('contact_person'))):
                    raise ValueError("Missing required field: 'name' or 'contact_person'")
                if import_type == "Applications" and (pd.isna(row.get('name')) or pd.isna(row.get('managing_it_unit_name')) or pd.isna(row.get('vendor_name')) or pd.isna(row.get('category_name'))):
                    raise ValueError("Missing required field: 'name', 'managing_it_unit_name', 'vendor_name', or 'category_name'")
                if import_type == "Infrastructure" and (pd.isna(row.get('name')) or pd.isna(row.get('managing_it_unit_name'))):
                    raise ValueError("Missing required field: 'name' or 'managing_it_unit_name'")
                if import_type == "IT Services" and (pd.isna(row.get('name')) or pd.isna(row.get('providing_it_unit_name'))):
                    raise ValueError("Missing required field: 'name' or 'providing_it_unit_name'")

                # Processing logic
                if import_type == "IT Units":
                    fte_val, budget_val = row.get('total_fte'), row.get('budget_amount')
                    result = db.add_it_unit(
                        user_email, name=row['name'], contact_person=row.get('contact_person'),
                        contact_email=row.get('contact_email'), total_fte=int(fte_val) if pd.notna(fte_val) else 0,
                        budget_amount=float(budget_val) if pd.notna(budget_val) else 0.0,
                        notes=row.get('notes'), bulk=True
                    )
                    if isinstance(result, str): raise ValueError(result)

                elif import_type == "Applications":
                    it_unit_id = it_units_map.get(row['managing_it_unit_name'])
                    if not it_unit_id: raise ValueError(f"IT Unit '{row['managing_it_unit_name']}' not found.")
                    
                    vendor_id = vendors_map.get(row.get('vendor_name'))
                    if not vendor_id: raise ValueError(f"Vendor '{row['vendor_name']}' not found.")
                    
                    type_id = types_map.get(row['type_name'])
                    if not type_id: raise ValueError(f"Type '{row['type_name']}' not found.")
                    
                    category_id = categories_map.get(row['category_name'])
                    if not category_id: raise ValueError(f"Category '{row['category_name']}' not found.")

                    cost_val = row.get('annual_cost')
                    db.add_application(
                        user_email, row['name'], it_unit_id, vendor_id, category_id, type_id, 
                        annual_cost=float(cost_val) if pd.notna(cost_val) else 0.0,
                        renewal_date=str(pd.to_datetime(row['renewal_date']).date()) if pd.notna(row.get('renewal_date')) else None,
                        integrations=row.get('integrations'), description=row.get('description'),
                        similar_apps=row.get('similar_applications'), service_owner=row.get('service_owner'), bulk=True
                    )

                elif import_type == "Infrastructure":
                    it_unit_id = it_units_map.get(row['managing_it_unit_name'])
                    if not it_unit_id: raise ValueError(f"IT Unit '{row['managing_it_unit_name']}' not found.")

                    vendor_id = vendors_map.get(row.get('vendor_name')) if pd.notna(row.get('vendor_name')) else None
                    cost_val = row.get('annual_maintenance_cost')

                    db.add_infrastructure(
                        user_email, name=row['name'], it_unit_id=it_unit_id, vendor_id=vendor_id,
                        location=row.get('location'), status=row.get('status'),
                        purchase_date=str(pd.to_datetime(row['purchase_date']).date()) if pd.notna(row.get('purchase_date')) else None,
                        warranty_expiry=str(pd.to_datetime(row['warranty_expiry']).date()) if pd.notna(row.get('warranty_expiry')) else None,
                        cost=float(cost_val) if pd.notna(cost_val) else 0.0,
                        description=row.get('description'), bulk=True
                    )
                    
                elif import_type == "IT Services":
                    it_unit_id = it_units_map.get(row['providing_it_unit_name'])
                    if not it_unit_id: raise ValueError(f"IT Unit '{row['providing_it_unit_name']}' not found.")
                    
                    sla_id = slas_map.get(row.get('sla_level_name')) if pd.notna(row.get('sla_level_name')) else None
                    method_id = methods_map.get(row.get('service_method_name')) if pd.notna(row.get('service_method_name')) else None

                    fte_val, budget_val = row.get('fte_count'), row.get('budget_allocation')

                    db.add_it_service(
                        user_email, name=row['name'], it_unit_id=it_unit_id,
                        desc=row.get('description'), fte=int(fte_val) if pd.notna(fte_val) else 0,
                        deps=row.get('dependencies'), owner=row.get('service_owner'), status=row.get('status'),
                        sla_id=sla_id, method_id=method_id, budget=float(budget_val) if pd.notna(budget_val) else 0.0, 
                        bulk=True
                    )

                success_log.append(f"Row {index+2}: Successfully imported '{row['name']}'.")

            except Exception as e:
                error_log.append(f"Row {index+2}: Failed to import '{row.get('name', 'N/A')}'. Reason: {e}")

    st.success(f"Import complete. {len(success_log)} records processed successfully.")
    if error_log:
        st.warning(f"{len(error_log)} records failed to import.")
        with st.expander("View Error Details"):
            for log in error_log:
                st.error(log)
    
    st.info("To see the imported data in other tabs, you may need to refresh the page.")