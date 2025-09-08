from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os

DB_PATH = os.path.join("data", "app.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

class Provider(Base):
    __tablename__ = "providers"
    id = Column(Integer, primary_key=True)
    org_name = Column(String, nullable=False)
    org_unit = Column(String)
    location = Column(String)
    contact_name = Column(String)
    contact_email = Column(String)
    delivery_model = Column(String)
    support_model = Column(String)
    sla_tier = Column(String)
    csat_score = Column(Float)
    status = Column(String)
    lifecycle_phase = Column(String)
