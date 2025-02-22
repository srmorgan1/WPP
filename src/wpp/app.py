import streamlit as st
import pandas as pd
import os
import logging
from typing import Optional

# Import the main functions from the scripts
from wpp.RunReports import main as run_reports_main
from wpp.UpdateDatabase import main as update_database_main
from wpp.config import WPP_REPORT_DIR, WPP_LOG_DIR


# Function to display the latest report
def display_latest_report() -> None:
    latest_report = max(
        [os.path.join(WPP_REPORT_DIR, f) for f in os.listdir(WPP_REPORT_DIR)],
        key=os.path.getctime,
    )
    df = pd.read_excel(latest_report)
    st.write(df)


# Function to display the latest log
def display_latest_log() -> None:
    latest_log = max(
        [os.path.join(WPP_LOG_DIR, f) for f in os.listdir(WPP_LOG_DIR)],
        key=os.path.getctime,
    )
    with open(latest_log, "r") as file:
        log_content = file.read()
    st.text(log_content)


# Streamlit app
st.title("WPP Management Application")

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Run Reports", "Update Database"])

if page == "Run Reports":
    st.header("Run Reports")
    if st.button("Run RunReports.py"):
        try:
            run_reports_main()
            st.success("RunReports.py executed successfully.")
        except Exception as e:
            st.error(f"Error running RunReports.py: {e}")
        st.subheader("Latest Report")
        display_latest_report()
        st.subheader("Latest Log")
        display_latest_log()

elif page == "Update Database":
    st.header("Update Database")
    if st.button("Run UpdateDatabase.py"):
        try:
            update_database_main()
            st.success("UpdateDatabase.py executed successfully.")
        except Exception as e:
            st.error(f"Error running UpdateDatabase.py: {e}")
        st.subheader("Latest Log")
        display_latest_log()
