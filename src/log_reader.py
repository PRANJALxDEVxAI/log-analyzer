from pathlib import Path

def read_log_file(file_path):
    try:
        with open(file_path , "r" , encoding = "utf-8") as file:
            log_enteries = file.readlines()

        return log_enteries

    except FileNotFoundError:
        print("Error: Log File not found.")
        return []

    except PermissionError:
        print("Error: Permission denied while trying to read the log file.")
        return []