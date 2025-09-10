import datetime as dt
import os
import signal
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from wpp.calendars import get_business_day_offset
from wpp.config import get_max_runtime_minutes, get_no_connection_shutdown_delay, get_wpp_data_dir, get_wpp_db_file, get_wpp_log_dir, get_wpp_report_dir
from wpp.RunReports import main as run_reports_main
from wpp.ui.streamlit.simple_shutdown import start_shutdown_monitor, update_session_activity
from wpp.UpdateDatabase import main as update_database_main


def get_project_root():
    """Find the project root directory by looking for pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback to current working directory if pyproject.toml not found
    return Path.cwd()


def get_asset_path(relative_path: str):
    """Get absolute path to asset relative to project root."""
    project_root = get_project_root()
    return project_root / "src/wpp/ui/streamlit/assets" / relative_path


def configure_page():
    """Configure Streamlit page settings."""
    st.set_page_config(page_title="WPP Management", page_icon="📊", layout="wide", initial_sidebar_state="expanded")


def load_css(file_name):
    """Load external CSS file with cache busting."""
    try:
        import time

        cache_buster = int(time.time())
        with open(file_name) as f:
            css_content = f.read()
            # Add cache busting comment
            css_content = f"/* Cache buster: {cache_buster} */\n" + css_content
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("CSS file not found. Using default styling.")


def load_javascript(file_name):
    """Load external JavaScript file."""
    try:
        with open(file_name) as f:
            st.markdown(f"<script>{f.read()}</script>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"JavaScript file not found: {file_name}")


def initialize_session_state():
    """Initialize session state variables."""
    if "app_logs" not in st.session_state:
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


def display_latest_report(match_name: str) -> None:
    """Display the latest report matching the given name pattern."""
    try:
        reports = [os.path.join(get_wpp_report_dir(), f) for f in os.listdir(get_wpp_report_dir()) if match_name in f]
        if not reports:
            st.info("No reports found matching the criteria.")
            return

        latest_report = max(reports, key=os.path.getctime)
        xls = pd.ExcelFile(latest_report)
        sheet_names = [str(n) for n in xls.sheet_names]
        tabs = st.tabs(sheet_names)

        for tab, sheet_name in zip(tabs, sheet_names):
            df = pd.read_excel(xls, sheet_name=sheet_name)
            with tab:
                st.write(df)
    except Exception as e:
        st.error(f"Error displaying report: {e}")


def display_latest_data_import_issues() -> None:
    """Display the latest data import issues spreadsheet."""
    try:
        reports_dir = get_wpp_report_dir()
        if not reports_dir.exists():
            st.info("Reports directory not found.")
            return

        # Look for Data_Import_Issues files
        issues_files = [f for f in os.listdir(reports_dir) if f.startswith("Data_Import_Issues_") and f.endswith(".xlsx")]

        if not issues_files:
            st.info("No data import issues files found.")
            return

        # Get the most recent file
        latest_issues_file = max([os.path.join(reports_dir, f) for f in issues_files], key=os.path.getctime)

        # Display file info
        file_name = os.path.basename(latest_issues_file)
        file_time = dt.datetime.fromtimestamp(os.path.getctime(latest_issues_file))
        st.markdown(f"**File:** {file_name}")
        st.markdown(f"**Created:** {file_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Load and display the Excel file
        xls = pd.ExcelFile(latest_issues_file)
        sheet_names = [str(n) for n in xls.sheet_names]

        if len(sheet_names) == 1:
            # Single sheet - display directly
            df = pd.read_excel(xls, sheet_name=sheet_names[0])
            st.write(df)
        else:
            # Multiple sheets - use tabs
            tabs = st.tabs(sheet_names)
            for tab, sheet_name in zip(tabs, sheet_names):
                df = pd.read_excel(xls, sheet_name=sheet_name)
                with tab:
                    st.write(df)

    except Exception as e:
        st.error(f"Error displaying data import issues: {e}")


def display_latest_log(match_name: str) -> None:
    """Display the latest log file matching the given name pattern in a scrollable text area."""
    try:
        logs = [os.path.join(get_wpp_log_dir(), f) for f in os.listdir(get_wpp_log_dir()) if match_name in f]
        if not logs:
            st.info("No log files found matching the criteria.")
            return

        latest_log = max(logs, key=os.path.getctime)
        file_name = os.path.basename(latest_log)
        file_time = dt.datetime.fromtimestamp(os.path.getctime(latest_log))

        # Display log file info
        st.markdown(f"**File:** {file_name}")
        st.markdown(f"**Created:** {file_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Read log content
        with open(latest_log) as file:
            log_content = file.read()

        # Display in a scrollable text area with fixed height
        st.text_area("Log Content:", value=log_content, height=400, disabled=True, label_visibility="collapsed")
    except Exception as e:
        st.error(f"Error displaying log: {e}")


def delete_db() -> None:
    """Delete the existing database file."""
    db_file = get_wpp_db_file()
    if os.path.exists(db_file):
        os.remove(db_file)
        st.info(f"Deleted existing DB file: {db_file}")
    else:
        st.warning(f"DB file does not exist: {db_file}")


def render_main_header():
    """Render the main application header content (without title since it's now fixed)."""
    # Display data directory information
    data_dir = get_wpp_data_dir()
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📂 Data Directory")
    st.markdown(f"`{data_dir}`")

    # Check if directory exists and show status
    if data_dir.exists():
        st.markdown('<span class="status-indicator status-success"></span>Directory accessible', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-indicator status-error"></span>Directory not found', unsafe_allow_html=True)
        st.warning(f"Data directory does not exist: {data_dir}")

    st.markdown("</div>", unsafe_allow_html=True)


def render_banner_image():
    """Render the banner image in the sidebar."""
    try:
        import base64

        banner_path = get_asset_path("images/wppmc.png")
        with open(banner_path, "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode()

        st.markdown(
            f"""
            <div class="banner-container">
                <img src="data:image/png;base64,{img_data}" class="banner-image">
            </div>
            """,
            unsafe_allow_html=True,
        )
    except FileNotFoundError:
        st.markdown(
            """
            <div class="banner-container">
                <h3 style="margin: 0; color: #1f77b4;">🏢 WPP Management</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar():
    """Render the complete sidebar with navigation and system controls."""
    with st.sidebar:
        # Add banner image at the top
        render_banner_image()

        # Navigation section
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("### 🧭 Navigation")
        page = st.radio("Select a page:", ["🔄 Update Database", "📊 Run Reports"], help="Choose what you'd like to do")
        st.markdown("</div>", unsafe_allow_html=True)

        # System controls section
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("### ⚙️ System Controls")

        # Database status
        db_file = get_wpp_db_file()
        if os.path.exists(db_file):
            st.markdown('<span class="status-indicator status-success"></span>Database: Connected', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-indicator status-warning"></span>Database: Not Found', unsafe_allow_html=True)

        st.markdown('<div style="height: 1px; background: linear-gradient(90deg, transparent, #cccccc, transparent); margin: 1rem 0;"></div>', unsafe_allow_html=True)

        if st.button("🔴 Shut Down App", help="Safely shut down the application"):
            st.info("Shutting down the app... Goodbye!")
            # Import threading here (os, signal, time already imported globally)
            import threading

            def shutdown_server():
                time.sleep(1)  # Give time for the UI to update
                try:
                    os.kill(os.getpid(), signal.SIGTERM)
                except Exception:
                    os.kill(os.getpid(), signal.SIGKILL)

            # Start shutdown in background thread
            threading.Thread(target=shutdown_server, daemon=True).start()

            st.markdown(
                """
            <script>
                // Try to close the browser window
                setTimeout(() => {
                    window.close();
                }, 500);
            </script>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

        # Display app logs with better formatting
        render_app_logs()

    return page


def render_app_logs():
    """Render application logs in the sidebar."""
    if st.session_state.app_logs:
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        with st.expander("📋 Recent Activity", expanded=False):
            for log in st.session_state.app_logs[-10:]:  # Show last 10 logs
                if "❌" in log:
                    st.markdown(f'<div class="alert-error" style="padding: 0.5rem; margin: 0.25rem 0;">{log}</div>', unsafe_allow_html=True)
                elif "⚠️" in log:
                    st.markdown(f'<div style="color: #856404; padding: 0.25rem;">{log}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="color: #155724; padding: 0.25rem;">{log}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_update_database_page():
    """Render the Update Database page."""
    # Database Update Section
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("## 🔄 Database Update")
        st.markdown("Process source files and update the database with latest data")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### ⚙️ Options")
        delete_existing_db = st.checkbox("Delete existing database before update", value=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Action button
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Update Database", help="Start the database update process"):
            with st.spinner("Updating database... Please wait"):
                try:
                    if delete_existing_db:
                        delete_db()
                    update_database_main()
                    st.markdown('<div class="alert-success">✅ Database updated successfully!</div>', unsafe_allow_html=True)
                    st.session_state.update_db_executed = True
                except Exception as e:
                    st.markdown(f'<div class="alert-error">❌ Error updating database: {e}</div>', unsafe_allow_html=True)
                    st.session_state.update_db_executed = True  # Show results even on error
                    st.info("💡 Check the Data Import Issues below to see what needs to be fixed.")
    st.markdown("</div>", unsafe_allow_html=True)

    # Display results if database was updated (success or error)
    if st.session_state.get("update_db_executed", False):
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### ⚠️ Data Import Issues")
        display_latest_data_import_issues()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📋 Update Log")
        display_latest_log("UpdateDatabase")
        st.markdown("</div>", unsafe_allow_html=True)


def render_run_reports_page():
    """Render the Run Reports page."""
    business_day = get_business_day_offset_cached()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("## 📊 Generate Reports")
    st.markdown("Create comprehensive reports from your database information")
    st.markdown("</div>", unsafe_allow_html=True)

    # Date selection with better layout
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**📅 Report Configuration**")
        run_date = st.date_input("Select report date:", dt.date.today() - business_day, help="Choose the date for report generation")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**ℹ️ Information**")
        st.info("Using business day calendar (excludes weekends and UK holidays)")
        st.markdown("</div>", unsafe_allow_html=True)

    # Action button
    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📈 Generate Reports", help="Create reports for the selected date"):
            with st.spinner("Generating reports... This may take a few minutes"):
                try:
                    run_reports_main(run_date, run_date)
                    st.markdown('<div class="alert-success">✅ Reports generated successfully!</div>', unsafe_allow_html=True)
                    st.session_state.reports_generated = True
                except Exception as e:
                    st.markdown(f'<div class="alert-error">❌ Error generating reports: {e}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Display results if reports were generated
    if st.session_state.get("reports_generated", False):
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📊 Latest Generated Report")
        display_latest_report("WPP_Report")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📄 Report Generation Log")
        display_latest_log("RunReports")
        st.markdown("</div>", unsafe_allow_html=True)


def main():
    """Main application entry point."""
    # Configure page
    configure_page()

    # Load CSS using project-relative path
    css_path = get_asset_path("css/styles.css")
    load_css(str(css_path))

    # Add inline CSS for modern flat design and fixed header
    st.markdown(
        """
    <style>
    /* Modern flat background */
    .stApp, .stApp > div, .main, section.main {
        background: #f8f9fa !important;
    }
    /* Main content styling */
    .block-container {
        background: transparent !important;
        background-color: transparent !important;
        padding-top: 80px !important; /* Add space for fixed header */
        max-width: 1200px !important;
    }
    /* Modern flat sidebar */
    section[data-testid="stSidebar"] {
        background: #ffffff !important;
        border-right: 1px solid #e9ecef !important;
    }

    /* Modern fixed header - improved targeting */
    .fixed-header-wpp {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100vw !important;
        z-index: 999999 !important;
        background: #ffffff !important;
        color: #2c3e50 !important;
        padding: 1rem 2rem !important;
        border-bottom: 1px solid #e9ecef !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        text-align: center !important;
        margin: 0 !important;
        display: block !important;
        visibility: visible !important;
    }

    /* Adjust main content spacing */
    .main > div {
        padding-top: 1rem !important;
    }

    /* Clean card hover effects */
    .card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
        transition: box-shadow 0.2s ease !important;
    }

    /* Debug - make sure header is visible */
    .fixed-header-wpp:after {
        content: " (Header Loaded)" !important;
        color: #999 !important;
        font-size: 0.8rem !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Add modern fixed header bar with improved HTML
    st.markdown(
        """
    <div class="fixed-header-wpp" id="wpp-header">
        📊 WPP Management Application
    </div>
    <script>
    // Ensure header stays visible
    const header = document.getElementById('wpp-header');
    if (header) {
        header.style.position = 'fixed';
        header.style.top = '0';
        header.style.left = '0';
        header.style.right = '0';
        header.style.zIndex = '999999';
        header.style.display = 'block';
        header.style.visibility = 'visible';
        console.log('WPP Header found and styled');
    } else {
        console.error('WPP Header not found');
    }
    </script>
    """,
        unsafe_allow_html=True,
    )

    # Start simple shutdown monitor
    if "shutdown_monitor_started" not in st.session_state:
        st.session_state.shutdown_monitor_started = False

    if not st.session_state.shutdown_monitor_started:
        print("🚀 Starting simple shutdown monitor...")
        if start_shutdown_monitor(
            max_runtime_minutes=get_max_runtime_minutes(),
            session_timeout_seconds=get_no_connection_shutdown_delay() * 60,  # Convert minutes to seconds
        ):
            st.session_state.shutdown_monitor_started = True
            print("✅ Shutdown monitor started successfully")
        else:
            print("ℹ️  Shutdown monitor already running")
            st.session_state.shutdown_monitor_started = True

    # Update activity on every page load/interaction
    update_session_activity()

    # Initialize session state
    initialize_session_state()

    # Render main header
    render_main_header()

    # Render sidebar and get selected page
    page = render_sidebar()

    # Render the appropriate page based on selection
    if page == "🔄 Update Database":
        update_session_activity()  # User navigated to this page
        render_update_database_page()
    elif page == "📊 Run Reports":
        update_session_activity()  # User navigated to this page
        render_run_reports_page()


if __name__ == "__main__":
    main()
