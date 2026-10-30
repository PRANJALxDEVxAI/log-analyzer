
import json
import csv
from pathlib import Path



def generate_json_report(
    logs,
    statistics,
    errors,
    common_errors,
    common_messages,
    error_percentage,
    earliest,
    latest,
    invalid_entries
):

    report = {
        "total_logs": len(logs),
        "invalid_entries": invalid_entries,

        "log_level_statistics": dict(statistics),

        "total_errors": len(errors),
        "error_percentage": error_percentage,

        "common_errors": dict(common_errors),
        "common_messages": dict(common_messages),

        "time_range": {
            "earliest": str(earliest) if earliest else None,
            "latest": str(latest) if latest else None
        },

        "error_details": errors
    }

    report_path = Path("reports/analysis_report.json")

    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print(f"JSON report saved: {report_path}")




def generate_csv_report(logs):

    report_path = Path("reports/analysis_report.csv")

    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", newline="", encoding="utf-8") as file:

        fieldnames = ["timestamp", "level", "message"]

        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(logs)

    print(f"CSV report saved: {report_path}")
