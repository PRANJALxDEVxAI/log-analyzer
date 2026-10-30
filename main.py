
import argparse
from src.analyser import (
    find_common_messages,
    calculate_error_percentage,
    find_time_range
)
from src.log_reader import read_log_file
from src.log_parser import parse_log_entry
from src.analyser import count_log_levels, find_errors, find_common_errors
from src.report_generator import generate_json_report, generate_csv_report


# Command-line arguments
parser = argparse.ArgumentParser(description="Python Log Analyzer")

parser.add_argument(
    "--file",
    required=True,
    help="Path to the log file"
)

args = parser.parse_args()

file_path = args.file


# Read log file
raw_logs = read_log_file(file_path)


# Parse log entries
logs = []
invalid_entries = 0

for entry in raw_logs:
    parsed = parse_log_entry(entry)

    if parsed is not None:
        logs.append(parsed)
    else:
        invalid_entries += 1


# Analyse logs
statistics = count_log_levels(logs)
errors = find_errors(logs)
common_errors = find_common_errors(errors)

common_messages = find_common_messages(logs)
error_percentage = calculate_error_percentage(logs)
earliest, latest = find_time_range(logs)


# Display results
print("\nMost Common Messages:")
print(common_messages.most_common(5))

print("\nError Percentage:", error_percentage, "%")

print("\nTime Range:")
print("Earliest:", earliest)
print("Latest:", latest)

print("\nInvalid Entries:", invalid_entries)


# Generate reports
print("\n========== GENERATING REPORTS ==========")

generate_json_report(
    logs,
    statistics,
    errors,
    common_errors,
    common_messages,
    error_percentage,
    earliest,
    latest,
    invalid_entries
)
generate_csv_report(logs)

print("\nAnalysis completed successfully!")
