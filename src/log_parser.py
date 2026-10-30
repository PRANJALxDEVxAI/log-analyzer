from datetime import datetime

def parse_log_entry(log_entry):
    parts = log_entry.strip().split(" " , 3)
    if len(parts) < 4:
        return None

    timestamp = parts[0] + " " + parts[1]
    level = parts[2]
    message = parts[3]

    try:
        datetime.strptime(timestamp , "%Y-%m-%d %H:%M:%S")

    except ValueError: 
        return None

    return{
        "timestamp": timestamp,
        "level": level,
        "message": message
    }