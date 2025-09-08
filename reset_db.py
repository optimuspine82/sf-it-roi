import os
from db import init_db, SessionLocal, DB_PATH, Provider, Service, Application, Mapping

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

init_db()
sess = SessionLocal()

# Seed mappings
mapping_data = {
    "ProviderType": ["Central IT", "School IT", "Department IT"],
    "AppType": ["COTS", "Custom", "Open Source"],
    "AppCategory": ["Productivity", "Research", "Data Analysis"],
    "DeliveryModel": ["Centralized", "Distributed"],
    "SupportModel": ["24/7", "Business Hours"],
    "LicenseType": ["Per User", "Site License"],
    "SlaTier": ["Gold", "Silver", "Bronze"],
    "LifecyclePhase": ["Production", "Retiring", "Pilot"],
    "DataClassification": ["Public", "Internal", "Restricted"],
    "HostingModel": ["On-Prem", "Cloud", "Hybrid"]
}
for g, vals in mapping_data.items():
    for v in vals:
        sess.add(Mapping(group=g, value=v))

# Providers
prov1 = Provider(org_name="UNC Central IT", org_type="Central IT")
prov2 = Provider(org_name="Pharmacy IT", org_type="School IT")
prov3 = Provider(org_name="Public Health IT", org_type="School IT")
sess.add_all([prov1, prov2, prov3])
sess.commit()

# Services
svc1 = Service(service_name="Email & Collaboration", delivery_model="Centralized",
               support_model="24/7", sla_tier="Gold", owner=prov1)
svc2 = Service(service_name="Lab Data Management", delivery_model="Distributed",
               support_model="Business Hours", sla_tier="Silver", owner=prov2)
svc3 = Service(service_name="Classroom Tech", delivery_model="Distributed",
               support_model="Business Hours", sla_tier="Bronze", owner=prov3)
sess.add_all([svc1, svc2, svc3])
sess.commit()

# Applications
app1 = Application(app_name="Microsoft 365", app_type="COTS", app_category="Productivity", vendor="Microsoft",
                   primary_function="Collaboration", service=svc1, owner=prov1,
                   annual_license_cost=50000, hosting_model="Cloud", hosting_cost=10000, lifecycle_phase="Production")
app2 = Application(app_name="Microsoft Teams", app_type="COTS", app_category="Productivity", vendor="Microsoft",
                   primary_function="Chat & Meetings", service=svc1, owner=prov1,
                   annual_license_cost=20000, hosting_model="Cloud", hosting_cost=5000, lifecycle_phase="Production")
app3 = Application(app_name="LabGuru", app_type="COTS", app_category="Research", vendor="BioData",
                   primary_function="Lab Data", service=svc2, owner=prov2,
                   annual_license_cost=15000, hosting_model="Cloud", hosting_cost=2000, lifecycle_phase="Production")
app4 = Application(app_name="Tableau", app_type="COTS", app_category="Data Analysis", vendor="Salesforce",
                   primary_function="Visualization", service=svc3, owner=prov3,
                   annual_license_cost=30000, hosting_model="Cloud", hosting_cost=4000, lifecycle_phase="Production")
sess.add_all([app1, app2, app3, app4])
sess.commit()

print("Database reset and seeded successfully.")
