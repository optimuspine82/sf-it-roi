Service Portfolio Manager
========================

A web application built with Python, Streamlit, and SQLite to track and manage an organization's IT portfolio, including internal IT units, applications, infrastructure, and services. The primary goal is to provide a centralized inventory to help identify consolidation opportunities, track spending, and manage ownership.
Features

    Tabbed Interface: Data is organized into logical sections:

        IT Units: Manage the internal teams responsible for services.
        Applications: Track both internal and external software.
        Infrastructure: Catalog physical and cloud hardware.
        IT Services: Document internal services like help desks.
        Dashboard: A high-level visual overview of the entire portfolio.
        Settings: Customize dropdown values used throughout the app.
        Audit Log: Track all changes made by users.

    Full CRUD Functionality: Create, Read, Update, and Delete capabilities for all data types, with confirmation steps to prevent accidental deletion.

    Interactive Dashboard: Utilizes Plotly to create interactive charts and graphs for visualizing costs, duplications, and resource allocation.

    Consolidation Insights: The dashboard automatically identifies and flags:

        Duplicate applications or services across different IT Units.
        Functionally similar applications based on shared categories.

    Search and Filtering: Each data tab includes robust filtering and search capabilities to easily find specific items.

    Data Export: Export filtered data from any main tab to a CSV file for offline analysis.

    Simple Authentication: A straightforward, email-based authentication system to control access during testing and deployment.

    "Quick Add" / Copy Feature: Quickly populate new entries by copying an existing item as a template.

Prerequisites

    Python 3.8+

    pip (Python package installer)

Setup and Installation

    Clone the repository:

    git clone <your-repository-url>
    cd <your-repository-folder>

    Create and activate a virtual environment:

        Windows:
        python -m venv .venv
        .venv\Scripts\activate

        macOS / Linux:
        python3 -m venv .venv
        source .venv/bin/activate

    Install the required dependencies:
    pip install -r requirements.txt

Running the Application

    From your project's root directory, run the following command in your terminal:

    streamlit run app.py

    Your web browser will open a new tab with the application running. On the first visit, you will be prompted to log in with one of the authorized email addresses.

File Structure

    app.py: The main Streamlit application script containing all UI and backend logic.
    config.py: Contains the list of authorized emails for authentication.
    requirements.txt: A list of all Python packages required to run the application.
    portfolio.db: The SQLite database file. This file is automatically created in the root directory the first time the application is run.
    .gitignore: Specifies files and directories that should be ignored by Git (like .venv and portfolio.db).

    README.md: This file.

Deployment

The recommended method for deploying this application for sandboxing and user feedback is the Streamlit Community Cloud. It offers a free tier and integrates directly with public GitHub repositories.
