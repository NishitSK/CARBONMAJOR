import datetime
from typing import List, Dict, Any

def format_table(headers: List[str], data: List[List[Any]], col_widths: List[int] = None) -> str:
    """
    Creates a manually aligned ASCII table without external dependencies.
    """
    if not data:
        return "No data available."
    
    # Calculate column widths if not provided
    if col_widths is None:
        col_widths = [len(h) for h in headers]
        for row in data:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))
    
    # Header separator
    separator = "+" + "+".join(["-" * (w + 2) for w in col_widths]) + "+"
    
    # Formatted Header
    header_row = "|" + "|".join([f" {headers[i].ljust(col_widths[i])} " for i in range(len(headers))]) + "|"
    
    # Data Rows
    data_rows = []
    for row in data:
        formatted_row = "|" + "|".join([f" {str(row[i]).ljust(col_widths[i])} " for i in range(len(row))]) + "|"
        data_rows.append(formatted_row)
        
    return "\n".join([separator, header_row, separator] + data_rows + [separator])

def log_decision(message: str, level: str = "INFO"):
    """
    Lightweight logging function.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] [{level}] {message}"
    print(formatted_msg)
    
def print_section_header(title: str):
    """
    Prints a clear visual divider for CLI sections.
    """
    print("\n" + "=" * 40)
    print(f" {title.upper()} ".center(40, "="))
    print("=" * 40 + "\n")
