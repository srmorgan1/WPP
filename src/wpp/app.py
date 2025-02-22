import streamlit as st
import pandas as pd
import os
import datetime as dt

# Import the main functions from the scripts
from wpp.RunReports import main as run_reports_main
from wpp.UpdateDatabase import main as update_database_main
from wpp.config import WPP_REPORT_DIR, WPP_LOG_DIR
from wpp.calendars import BUSINESS_DAY


# Function to display the latest report
def display_latest_report(match_name: str) -> None:
    latest_report = max(
        [os.path.join(WPP_REPORT_DIR, f) for f in os.listdir(WPP_REPORT_DIR) if match_name in f],
        key=os.path.getctime,
    )
    xls = pd.ExcelFile(latest_report)
    sheet_names = xls.sheet_names
    tabs = st.tabs(sheet_names)
    for tab, sheet_name in zip(tabs, sheet_names):
        df = pd.read_excel(xls, sheet_name=sheet_name)
        with tab:
            st.write(df)


# Function to display the latest log
def display_latest_log(match_name: str) -> None:
    latest_log = max(
        [os.path.join(WPP_LOG_DIR, f) for f in os.listdir(WPP_LOG_DIR) if match_name in f],
        key=os.path.getctime,
    )
    with open(latest_log, "r") as file:
        log_content = file.read()
    st.text(log_content)


# Streamlit app
st.title("WPP Management Application")

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Update Database", "Run Reports"])

if page == "Run Reports":
    st.header("Run Reports")
    run_date = st.date_input("Run Date", dt.date.today() - BUSINESS_DAY)
    if st.button("Run the Reports"):
        try:
            run_reports_main(run_date, run_date)
            st.success("RunReports executed successfully.")
        except Exception as e:
            st.error(f"Error running the reports: {e}")
        st.subheader("Latest Report")
        display_latest_report("WPP_Report")
        st.subheader("Latest Log")
        display_latest_log("RunReports")

elif page == "Update Database":
    st.header("Update Database")
    if st.button("Update the Database"):
        try:
            update_database_main()
            st.success("UpdateDatabase executed successfully.")
        except Exception as e:
            st.error(f"Error updating the database: {e}")
        st.subheader("Latest Log")
        display_latest_log("UpdateDatabase")
