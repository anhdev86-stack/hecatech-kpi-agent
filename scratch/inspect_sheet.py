import csv, io, urllib.request
from run_project_report import fetch_project_sheet

def inspect_sheet(project):
    print(f"Inspecting sheet: {project}")
    rows = fetch_project_sheet(project)
    if not rows:
        print("Empty sheet")
        return
    for i in range(min(5, len(rows))):
        print(f"Row {i}: {rows[i]}")

if __name__ == "__main__":
    inspect_sheet("XKMVN")
