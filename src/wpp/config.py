import os
import datetime as dt

# NB: These must be set to the correct locations on your system
if os.name == "posix":
    WPP_ROOT_DIR = r"/Users/steve/Work/WPP"
else:
    WPP_ROOT_DIR = r"\\SBS\public\qube\iSite\AutoBOSShelleyAngeAndSandra"
    # WPP_ROOT_DIR = r'Z:/qube/iSite/AutoBOSShelleyAngeAndSandra'
    # WPP_ROOT_DIR = os.path.normpath(os.path.join(sys.path[0], os.pardir))

    
def set_wpp_root_dir(root_dir: str) -> None:
    global WPP_ROOT_DIR
    WPP_ROOT_DIR = root_dir


def get_wpp_root_dir() -> str:
    return WPP_ROOT_DIR


def get_wpp_input_dir() -> str:
    return WPP_ROOT_DIR + r"/Inputs"


def get_wpp_report_dir() -> str:
    return WPP_ROOT_DIR + r"/Reports"


def get_wpp_log_dir() -> str:
    return WPP_ROOT_DIR + r"/Logs"


def get_wpp_db_dir() -> str:
    return WPP_ROOT_DIR + r"/Database"


def get_wpp_db_file() -> str:
    return get_wpp_db_dir() + r"/WPP_DB.db"


def get_wpp_excel_log_file(date: dt.date) -> str:
    return get_wpp_report_dir() + rf"/Data_Import_Issues_{date.strftime('%Y-%m-%d')}.xlsx"


def get_wpp_report_file(date: dt.date | dt.datetime) -> str:
    return get_wpp_report_dir() + rf"/WPP_Report_{date.isoformat().replace('/', '.')}.xlsx"


def get_wpp_update_database_log_file(date: dt.date | dt.datetime) -> str:
    return get_wpp_log_dir() + rf"/Log_UpdateDatabase_{str(date).replace('/', '.')}.txt"


def get_wpp_run_reports_log_file(date: dt.date | dt.datetime) -> str:
    return get_wpp_log_dir() + rf"/Log_RunReports_{str(date).replace('/', '.')}.txt"
