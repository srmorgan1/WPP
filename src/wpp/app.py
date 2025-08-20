import datetime as dt
import os
import signal
import time

import pandas as pd
import streamlit as st

from wpp.calendars import get_business_day_offset
from wpp.config import get_wpp_db_file, get_wpp_log_dir, get_wpp_report_dir

# Initialize session state for app logs
if 'app_logs' not in st.session_state:
    st.session_state.app_logs = []

class StreamlitUILogger:
    """Simple logger that collects messages for display in Streamlit UI."""
    
    def warning(self, msg: str):
        st.session_state.app_logs.append(f"⚠️ {msg}")
    
    def error(self, msg: str):
        st.session_state.app_logs.append(f"❌ {msg}")
    
    def info(self, msg: str):
        st.session_state.app_logs.append(f"ℹ️ {msg}")

@st.cache_data
def get_business_day_offset_cached():
    """Get business day offset with caching to avoid repeated initialization."""
    logger = StreamlitUILogger()
    return get_business_day_offset(logger)

# Get the business day offset
BUSINESS_DAY = get_business_day_offset_cached()

# Import the main functions from the scripts
from wpp.RunReports import main as run_reports_main
from wpp.UpdateDatabase import main as update_database_main


# Function to display the latest report
def display_latest_report(match_name: str) -> None:
    latest_report = max(
        [os.path.join(get_wpp_report_dir(), f) for f in os.listdir(get_wpp_report_dir()) if match_name in f],
        key=os.path.getctime,
    )
    xls = pd.ExcelFile(latest_report)
    sheet_names = [str(n) for n in xls.sheet_names]
    tabs = st.tabs(sheet_names)
    for tab, sheet_name in zip(tabs, sheet_names):
        df = pd.read_excel(xls, sheet_name=sheet_name)
        with tab:
            st.write(df)


# Function to display the latest log
def display_latest_log(match_name: str) -> None:
    latest_log = max(
        [os.path.join(get_wpp_log_dir(), f) for f in os.listdir(get_wpp_log_dir()) if match_name in f],
        key=os.path.getctime,
    )
    with open(latest_log) as file:
        log_content = file.read()
    st.text(log_content)


def delete_db() -> None:
    db_file = get_wpp_db_file()
    if os.path.exists(db_file):
        os.remove(db_file)
        st.info(f"Deleted existing DB file: {db_file}")
    else:
        st.warning(f"DB file does not exist: {db_file}")


# Streamlit app
st.title("WPP Management Application")

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Update Database", "Run Reports"])
st.sidebar.markdown("---")
if st.sidebar.button("Shut Down The App"):
    st.info("Shutting down the app... Goodbye!")
    time.sleep(1)
    os.kill(os.getpid(), signal.SIGKILL)
    st.stop()

# Display app logs in sidebar
if st.session_state.app_logs:
    st.sidebar.markdown("---")
    with st.sidebar.expander("📋 App Logs"):
        for log in st.session_state.app_logs[-10:]:  # Show last 10 logs
            st.text(log)

if page == "Update Database":
    st.header("Update Database")
    col1, col2 = st.columns([3, 1])
    with col2:
        delete_existing_db = st.checkbox("Delete existing DB", value=True)
    with col1:
        if st.button("Update the Database"):
            try:
                if delete_existing_db:
                    delete_db()
                update_database_main()
                st.success("UpdateDatabase executed successfully.")
            except Exception as e:
                st.error(f"Error updating the database: {e}")
            st.subheader("Latest Log")
            display_latest_log("UpdateDatabase")

elif page == "Run Reports":
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
