import os

# NB: These must be set to the correct locations on your system
if os.name == "posix":
    WPP_ROOT_DIR = r"/Users/steve/Work/WPP"
else:
    # WPP_ROOT_DIR = r'Z:/qube/iSite/AutoBOSShelleyAngeAndSandra'
    # WPP_ROOT_DIR = os.path.normpath(os.path.join(sys.path[0], os.pardir))
    WPP_ROOT_DIR = r"\\SBS\public\qube\iSite\AutoBOSShelleyAngeAndSandra"

WPP_INPUT_DIR = WPP_ROOT_DIR + r"/Inputs"
WPP_REPORT_DIR = WPP_ROOT_DIR + r"/Reports"
WPP_LOG_DIR = WPP_ROOT_DIR + r"/Logs"
WPP_DB_DIR = WPP_ROOT_DIR + r"/Database"
WPP_DB_FILE = WPP_DB_DIR + r"/WPP_DB.db"
WPP_EXCEL_LOG_FILE = WPP_REPORT_DIR + r"/Data_Import_Issues_{}.xlsx"
WPP_REPORT_FILE = WPP_REPORT_DIR + r"/WPP_Report_{}.xlsx"
WPP_RUN_REPORTS_LOG_FILE = WPP_LOG_DIR + r"/Log_RunReports_{}.txt"
