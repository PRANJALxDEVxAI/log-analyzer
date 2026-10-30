
from collections import Counter


def count_log_levels(logs):
    levels = []

    for log in logs:
        levels.append(log["level"])

    return Counter(levels)


def find_errors(logs):
    errors = []

    for log in logs:
        if log["level"] == "ERROR" or log["level"] == "CRITICAL":
            errors.append(log)

    return errors


def find_common_errors(errors):
    error_messages = []

    for error in errors:
        error_messages.append(error["message"])

    return Counter(error_messages)

from datetime import datetime
from collections import Counter


def find_common_messages(logs):
    messages = []

    for log in logs:
        messages.append(log["message"])

    return Counter(messages)


def calculate_error_percentage(logs):
    if len(logs) == 0:
        return 0

    error_count = 0

    for log in logs:
        if log["level"] == "ERROR" or log["level"] == "CRITICAL":
            error_count += 1

    percentage = (error_count / len(logs)) * 100

    return round(percentage, 2)


def find_time_range(logs):
    if len(logs) == 0:
        return None, None

    timestamps = []

    for log in logs:
        timestamp = datetime.strptime(
            log["timestamp"], "%Y-%m-%d %H:%M:%S"
        )

        timestamps.append(timestamp)

    earliest = min(timestamps)
    latest = max(timestamps)

    return earliest, latest
