import streamlit as st
from sqlalchemy.orm import Session
from db import SessionLocal, Provider, Application, Mapping
import pandas as pd
import altair as alt

st.set_page_config(page_title="UNC HA ROI Tracker", layout="wide")

def get_session() -> Session:
    return SessionLocal()

@st.cache_data
def get_mappings():
    sess = get_session()
    mappings = sess.query(Mapping).all()
    out = {}
    for m in mappings:
        out.setdefault(m.group, []).append(m.value)
    return out

def format_select_options(objs, label_fn):
    return {label_fn(obj): obj.id for obj in objs}

def main():
    st.title("🏛️ UNC Health Affairs ROI Tracker")
    tabs = st.tabs(["Dashboard", "Providers", "Services", "Applications", "Finder", "Opportunities"])

    with tabs[0]:
        render_dashboard()
    with tabs[1]:
        crud_providers()
    with tabs[2]:
        crud_services()
    with tabs[3]:
        crud_apps()
    with tabs[4]:
        render_finder()
    with tabs[5]:
        render_opportunities()

def render_dashboard():
    sess = get_session()
    st.header("Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Providers", sess.query(Provider).count())
    col2.metric("Total Services", sess.query(Service).count())
    col3.metric("Total Applications", sess.query(Application).count())

    st.subheader("Applications by Category")
    df = pd.read_sql(sess.query(Application).statement, sess.bind)
    if df.empty:
        st.info("No applications available.")
        return
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("app_category:N", title="Category"),
        y=alt.Y("count():Q", title="Count"),
        color="app_category:N"
    ).properties(width="container")
    st.altair_chart(chart)

    st.subheader("License Spend by Provider")
    df_apps = pd.read_sql(sess.query(Application).statement, sess.bind)
    df_prov = pd.read_sql(sess.query(Provider).statement, sess.bind)
    merged = df_apps.merge(df_prov, left_on="owning_org_id", right_on="id", suffixes=("_app", "_prov"))
    bar = alt.Chart(merged).mark_bar().encode(
        x=alt.X("org_name:N", title="Provider"),
        y=alt.Y("annual_license_cost:Q", aggregate="sum", title="Total Spend")
    ).properties(width="container")
    st.altair_chart(bar)

def crud_providers():
    sess = get_session()
    st.subheader("Manage Providers")
    with st.form("add_provider"):
        st.write("### Add New Provider")
        name = st.text_input("Organization Name")
        org_type = st.selectbox("Org Type", get_mappings().get("ProviderType", []))
        if st.form_submit_button("Add"):
            sess.add(Provider(org_name=name, org_type=org_type))
            sess.commit()
            st.success("Provider added!")

    st.write("### Existing Providers")
    for prov in sess.query(Provider).all():
        with st.expander(prov.org_name):
            new_name = st.text_input(f"Name [{prov.id}]", value=prov.org_name, key=f"name_{prov.id}")
            new_type = st.selectbox(f"Type [{prov.id}]", get_mappings().get("ProviderType", []), index=0, key=f"type_{prov.id}")
            if st.button("Save", key=f"save_{prov.id}"):
                prov.org_name = new_name
                prov.org_type = new_type
                sess.commit()
                st.success("Saved.")

def crud_services():
    sess = get_session()
    st.subheader("Manage Services")
    providers = sess.query(Provider).all()
    provider_map = format_select_options(providers, lambda p: p.org_name)
    with st.form("add_service"):
        st.write("### Add New Service")
        name = st.text_input("Service Name")
        delivery = st.selectbox("Delivery Model", get_mappings().get("DeliveryModel", []))
        support = st.selectbox("Support Model", get_mappings().get("SupportModel", []))
        sla = st.selectbox("SLA Tier", get_mappings().get("SlaTier", []))
        owner = st.selectbox("Owning Org", list(provider_map.keys()))
        if st.form_submit_button("Add"):
            sess.add(Service(
                service_name=name, delivery_model=delivery,
                support_model=support, sla_tier=sla,
                owning_org_id=provider_map[owner]
            ))
            sess.commit()
            st.success("Service added!")

    st.write("### Existing Services")
    for svc in sess.query(Service).all():
        with st.expander(svc.service_name):
            svc_name = st.text_input(f"Name [{svc.id}]", svc.service_name, key=f"svcname_{svc.id}")
            svc_owner = st.selectbox(f"Org [{svc.id}]", list(provider_map.keys()), key=f"owner_{svc.id}")
            if st.button("Save", key=f"svc_save_{svc.id}"):
                svc.service_name = svc_name
                svc.owning_org_id = provider_map[svc_owner]
                sess.commit()
                st.success("Saved.")

def crud_apps():
    sess = get_session()
    st.subheader("Manage Applications")
    services = sess.query(Service).all()
    providers = sess.query(Provider).all()
    mappings = get_mappings()

    svc_map = format_select_options(services, lambda s: s.service_name)
    prov_map = format_select_options(providers, lambda p: p.org_name)

    with st.form("add_app"):
        st.write("### Add New Application")
        name = st.text_input("App Name")
        app_type = st.selectbox("App Type", mappings.get("AppType", []))
        app_category = st.selectbox("App Category", mappings.get("AppCategory", []))
        vendor = st.text_input("Vendor")
        hosting = st.selectbox("Hosting Model", mappings.get("HostingModel", []))
        service = st.selectbox("Related Service", list(svc_map.keys()))
        owner = st.selectbox("Owning Org", list(prov_map.keys()), key="app_org_add")
        if st.form_submit_button("Add"):
            sess.add(Application(
                app_name=name,
                app_type=app_type,
                app_category=app_category,
                vendor=vendor,
                hosting_model=hosting,
                service_id=svc_map[service],
                owning_org_id=prov_map[owner]
            ))
            sess.commit()
            st.success("Application added!")

    st.write("### Existing Applications")
    for app in sess.query(Application).all():
        with st.expander(app.app_name):
            new_name = st.text_input(f"App Name [{app.id}]", app.app_name, key=f"appn_{app.id}")
            new_type = st.selectbox(f"Type [{app.id}]", mappings.get("AppType", []), key=f"appt_{app.id}")
            if st.button("Save", key=f"apps_{app.id}"):
                app.app_name = new_name
                app.app_type = new_type
                sess.commit()
                st.success("Saved.")

def render_finder():
    sess = get_session()
    st.subheader("🕵️ Finder")
    df = pd.read_sql(sess.query(Application).statement, sess.bind)
    if df.empty:
        st.info("No applications available.")
        return
    st.write("Applications with duplicate vendors:")
    dup_vendors = df[df.duplicated("vendor", keep=False)]
    st.dataframe(dup_vendors)

    st.download_button("Export All Applications", df.to_csv(index=False), "applications.csv")

def render_opportunities():
    sess = get_session()
    st.subheader("💡 Opportunities")
    df = pd.read_sql(sess.query(Application).statement, sess.bind)
    if df.empty:
        st.info("No data to analyze.")
        return
    dup_vendors = df[df.duplicated("vendor", keep=False)]
    st.write("Applications with vendor overlap may present consolidation opportunities:")
    st.dataframe(dup_vendors)

if __name__ == "__main__":
    main()
