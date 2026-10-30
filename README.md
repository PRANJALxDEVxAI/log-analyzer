# Log Analyzer Pro

A Python-based log analysis application that reads, parses, and analyzes log files to help identify errors, warnings, recurring issues, and other important information.

The project includes a modern desktop GUI built with **CustomTkinter**, along with a modular Python backend for processing log data and generating reports.

## Features

- **Log File Reading:** Load and read `.log` files.
- **Log Parsing:** Extract timestamps, log levels, and messages.
- **Log Level Analysis:** Count INFO, WARNING, ERROR, and CRITICAL entries.
- **Error Detection:** Identify ERROR and CRITICAL entries.
- **Recurring Error Detection:** Find frequently occurring error messages.
- **Message Analysis:** Identify commonly repeated log messages.
- **Error Percentage:** Calculate the percentage of errors in a log file.
- **Time Range Analysis:** Find the earliest and latest timestamps.
- **Invalid Entry Detection:** Track log entries that cannot be parsed.
- **JSON Reports:** Generate detailed analysis reports in JSON format.
- **CSV Reports:** Export log entries into CSV format.
- **Desktop GUI:** Navigate through analysis, dashboard, explorer, reports, and settings.

## Technologies Used

- Python 3
- CustomTkinter
- JSON
- CSV
- Datetime
- Collections
- Threading
- Tkinter

## Project Structure

```text
LOG ANALYSER/
│
├── data/
│   ├── sample.log
│   └── server.log
│
├── src/
│   ├── log_reader.py
│   ├── log_parser.py
│   ├── analyser.py
│   └── report_generator.py
│
├── reports/
│
├── main.py
├── README.md
└── [GUI Python File]
```

## How It Works

The application follows a modular processing pipeline:

1. **Read:** Load the selected log file.
2. **Parse:** Convert raw log lines into structured Python dictionaries.
3. **Analyze:** Calculate statistics and identify errors and recurring messages.
4. **Report:** Generate JSON and CSV reports.
5. **Display:** Present the results through the desktop interface.

## Log Format

The application expects log entries in the following format:

```text
YYYY-MM-DD HH:MM:SS LEVEL Message
```

Example:

```text
2026-10-20 09:15:22 INFO Application started
2026-10-20 09:16:10 WARNING Low disk space
2026-10-20 09:17:35 ERROR Database connection failed
2026-10-20 09:18:00 CRITICAL Server unavailable
```

## Running the Project

### 1. Clone the Repository

```bash
git clone YOUR_REPOSITORY_URL
```

### 2. Navigate to the Project

```bash
cd "LOG ANALYSER"
```

### 3. Install GUI Dependency

```bash
pip install customtkinter
```

### 4. Run the Desktop GUI

Run your GUI Python file:

```bash
python your_gui_filename.py
```

Replace the filename with the actual name of your GUI file.

### 5. Run the Command-Line Version

```bash
python main.py --file data/sample.log
```

You can also analyze another log file:

```bash
python main.py --file data/server.log
```

## Generated Reports

The application generates reports inside the `reports/` directory.

| Report | Format | Purpose |
|---|---|---|
| analysis_report.json | JSON | Detailed analysis results |
| analysis_report.csv | CSV | Structured log entries |

Reports are regenerated when a new analysis is performed.

## Learning Objectives

This project helped me practice:

- File handling in Python.
- String manipulation and parsing.
- Working with dictionaries and lists.
- Exception handling.
- Modular programming and imports.
- Data analysis using Python.
- JSON and CSV file operations.
- GUI development with CustomTkinter.
- Basic multithreading for background tasks.

## Future Improvements

- Support for additional log formats.
- More advanced filtering and search.
- Custom report naming.
- Additional analysis statistics.
- Exporting dashboard summaries.

---

**Project:** Log Analyzer Pro  
**Language:** Python  
**Interface:** CustomTkinter Desktop GUI
