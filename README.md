# UNC Health Affairs IT ROI Tracker (Complete)

## Prerequisites
- Python 3.11.x (required, not compatible with Python 3.13+)
- pip (latest)

## Quickstart
```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python reset_db.py
streamlit run streamlit_app.py --server.address=localhost --server.port=8501