import os
import shutil
import pandas as pd
from pandas import ExcelFile
from wpp.UpdateDatabase import main as update_database_main
from wpp.RunReports import main as run_reports_main

# Define paths
WPP_ROOT_DIR = r"/Users/steve/Work/WPP"
WPP_REPORT_DIR = WPP_ROOT_DIR + "/Reports"
REFERENCE_REPORT_DIR = r"/Users/steve/Work/WPP/ReferenceReports"


def compare_excel_files(generated_file: str, reference_file: str) -> None:
    with ExcelFile(generated_file) as gen_xl, ExcelFile(reference_file) as ref_xl:
        assert gen_xl.sheet_names == ref_xl.sheet_names, "Sheet names do not match"

        for sheet_name in gen_xl.sheet_names:
            gen_df = pd.read_excel(gen_xl, sheet_name=sheet_name)
            ref_df = pd.read_excel(ref_xl, sheet_name=sheet_name)
            pd.testing.assert_frame_equal(
                gen_df, ref_df, check_dtype=False, check_like=True
            )


def test_regression() -> None:
    # Clean up the Reports directory
    if os.path.exists(WPP_REPORT_DIR):
        shutil.rmtree(WPP_REPORT_DIR)
    os.makedirs(WPP_REPORT_DIR, exist_ok=True)

    # Run UpdateDatabase
    update_database_main()

    # Run RunReports
    run_reports_main()

    # Compare generated reports with reference reports
    generated_reports = sorted(os.listdir(WPP_REPORT_DIR))
    reference_reports = sorted(os.listdir(REFERENCE_REPORT_DIR))

    assert len(generated_reports) == len(reference_reports), (
        "Number of reports do not match"
    )

    for generated_report, reference_report in zip(generated_reports, reference_reports):
        generated_report_path = os.path.join(WPP_REPORT_DIR, generated_report)
        reference_report_path = os.path.join(REFERENCE_REPORT_DIR, reference_report)

        assert os.path.basename(generated_report_path) == os.path.basename(
            reference_report_path
        ), "Report names do not match"

        compare_excel_files(generated_report_path, reference_report_path)


if __name__ == "__main__":
    test_regression()
