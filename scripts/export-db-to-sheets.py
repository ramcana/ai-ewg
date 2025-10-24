#!/usr/bin/env python3
"""
Export SQLite database tables to Google Sheets or CSV
Usage: python export-db-to-sheets.py [--format csv|sheets] [--table episodes]
"""

import sqlite3
import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime

def export_to_csv(db_path: str, output_dir: str = "exports", table: str = None):
    """Export SQLite tables to CSV files"""
    
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    
    # Get all tables if not specified
    if table:
        tables = [table]
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📊 Exporting {len(tables)} table(s) from {db_path.name}")
    print("=" * 60)
    
    for table_name in tables:
        try:
            # Read table into DataFrame
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file = output_dir / f"{table_name}_{timestamp}.csv"
            
            # Export to CSV
            df.to_csv(csv_file, index=False)
            
            print(f"✅ {table_name}: {len(df)} rows → {csv_file}")
            
        except Exception as e:
            print(f"❌ {table_name}: Error - {e}")
    
    conn.close()
    print("\n" + "=" * 60)
    print(f"📁 Files saved to: {output_dir.absolute()}\n")


def export_to_google_sheets(db_path: str, credentials_file: str = None, table: str = None):
    """Export SQLite tables to Google Sheets (requires gspread)"""
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("❌ Google Sheets integration requires: pip install gspread google-auth")
        print("\nAlternatively, use CSV export and manually import to Google Sheets:")
        print("  python export-db-to-sheets.py --format csv")
        return
    
    if not credentials_file:
        print("❌ Google Sheets requires credentials JSON file")
        print("\nGet credentials:")
        print("  1. Go to: https://console.cloud.google.com/")
        print("  2. Create project → Enable Google Sheets API")
        print("  3. Create Service Account → Download JSON")
        print("  4. Run: python export-db-to-sheets.py --format sheets --credentials path/to/creds.json")
        return
    
    # Setup Google Sheets connection
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
    client = gspread.authorize(creds)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    # Get tables
    if table:
        tables = [table]
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📊 Exporting {len(tables)} table(s) to Google Sheets")
    print("=" * 60)
    
    # Create or open spreadsheet
    spreadsheet_name = f"Pipeline DB Export - {datetime.now().strftime('%Y-%m-%d')}"
    
    try:
        spreadsheet = client.open(spreadsheet_name)
        print(f"📝 Using existing spreadsheet: {spreadsheet_name}")
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(spreadsheet_name)
        print(f"📝 Created new spreadsheet: {spreadsheet_name}")
    
    for table_name in tables:
        try:
            # Read table into DataFrame
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            
            # Create or update worksheet
            try:
                worksheet = spreadsheet.worksheet(table_name)
                worksheet.clear()
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=table_name, rows=len(df)+1, cols=len(df.columns))
            
            # Convert DataFrame to list of lists
            data = [df.columns.tolist()] + df.values.tolist()
            
            # Update worksheet
            worksheet.update(data, 'A1')
            
            print(f"✅ {table_name}: {len(df)} rows → Sheet '{table_name}'")
            
        except Exception as e:
            print(f"❌ {table_name}: Error - {e}")
    
    conn.close()
    print("\n" + "=" * 60)
    print(f"📊 Spreadsheet URL: {spreadsheet.url}\n")


def view_table_info(db_path: str):
    """Display information about database tables"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📊 Database: {db_path}")
    print("=" * 60)
    
    for table in tables:
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        
        print(f"\n📋 Table: {table}")
        print(f"   Rows: {row_count:,}")
        print(f"   Columns: {len(columns)}")
        print("   Schema:")
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            is_pk = " (PRIMARY KEY)" if col[5] else ""
            print(f"     - {col_name}: {col_type}{is_pk}")
    
    conn.close()
    print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Export SQLite database to CSV or Google Sheets")
    parser.add_argument("--db", default="data/pipeline.db", help="Path to SQLite database")
    parser.add_argument("--format", choices=["csv", "sheets", "info"], default="csv", 
                       help="Export format (csv, sheets, or info to view table structure)")
    parser.add_argument("--table", help="Specific table to export (default: all tables)")
    parser.add_argument("--output", default="exports", help="Output directory for CSV files")
    parser.add_argument("--credentials", help="Google Sheets credentials JSON file")
    
    args = parser.parse_args()
    
    if args.format == "info":
        view_table_info(args.db)
    elif args.format == "csv":
        export_to_csv(args.db, args.output, args.table)
    elif args.format == "sheets":
        export_to_google_sheets(args.db, args.credentials, args.table)


if __name__ == "__main__":
    main()
