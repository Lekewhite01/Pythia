import psycopg2
import csv
import yaml
import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from psycopg2.extras import DictCursor
import sys
sys.path.append('..')

# Function to load configuration from a YAML file
def load_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

# Load the configuration
config = load_config('../secrets.yaml')


def connect_to_postgres(host, database, user, password):
    """
    Establish a connection to a PostgreSQL database.
    
    Args:
        host (str): The database host address.
        database (str): The name of the database.
        user (str): The username for authentication.
        password (str): The password for authentication.
        
    Returns:
        psycopg2.connection: A connection object to the PostgreSQL database.
    """
    return psycopg2.connect(host=host, database=database, user=user, password=password)

def get_table_names(cursor):
    """
    Retrieve the names of all tables in the database, excluding system tables.
    
    Args:
        cursor (psycopg2.cursor): The cursor object for executing SQL queries.
        
    Returns:
        list: A list of tuples containing the schema and table names.
    """
    cursor.execute("""
        SELECT table_schema, table_name 
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema') 
        AND table_type = 'BASE TABLE'
    """)
    return cursor.fetchall()

def get_column_info(cursor, schema, table_name):
    """
    Fetch metadata about the columns in a specified table.
    
    Args:
        cursor (psycopg2.cursor): The cursor object for executing SQL queries.
        schema (str): The schema name where the table is located.
        table_name (str): The name of the table.
        
    Returns:
        list: A list of tuples containing column names and data types.
    """
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, (schema, table_name))
    return cursor.fetchall()

def get_table_data(cursor, schema, table_name):
    """
    Fetch all data from a specified table.
    
    Args:
        cursor (psycopg2.cursor): The cursor object for executing SQL queries.
        schema (str): The schema name where the table is located.
        table_name (str): The name of the table.
        
    Returns:
        list: A list of tuples representing the rows of the table.
    """
    try:
        cursor.execute(f'SELECT * FROM "{schema}"."{table_name}"')
        return cursor.fetchall()
    except psycopg2.errors.UndefinedTable:
        print(f"Table '{schema}.{table_name}' does not exist or is not accessible.")
        return []
    except psycopg2.Error as e:
        print(f"Error accessing table '{schema}.{table_name}': {str(e)}")
        return []

def write_to_excel(workbook, sheet_name, columns, data):
    """
    Write table data and column information to an Excel sheet.
    
    Args:
        workbook (openpyxl.Workbook): An openpyxl workbook object where the data will be written.
        sheet_name (str): The name of the Excel sheet.
        columns (list): A list of tuples containing column names and data types.
        data (list): A list of tuples representing the rows of the table.
        
    Returns:
        None
    """
    sheet = workbook.create_sheet(title=sheet_name)
    
    # Write column headers in the first row
    for col, (column_name, _) in enumerate(columns, start=1):
        cell = sheet.cell(row=1, column=col, value=column_name)
        cell.font = Font(bold=True)  # Set the font to bold for headers
    
    # Write the data to the sheet
    for row, record in enumerate(data, start=2):  # Start from row 2, after headers
        for col, (_, data_type) in enumerate(columns, start=1):
            value = record[col-1]  # Get the value for each column in the row
            
            # Convert the value based on its data type
            if value is not None:
                if data_type == 'integer':
                    value = int(value)
                elif data_type == 'numeric':
                    value = float(value)
                elif data_type == 'boolean':
                    value = bool(value)
                elif data_type.startswith('timestamp'):
                    if isinstance(value, str):
                        value = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
                elif data_type == 'date':
                    if isinstance(value, str):
                        value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
            
            # Write the value to the corresponding cell
            sheet.cell(row=row, column=col, value=value)
    
    # Adjust column widths for better readability
    for col in sheet.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2) * 1.2
        sheet.column_dimensions[column].width = adjusted_width

def get_column_metadata(cursor, table_name, column_name, data_type):
    """
    Retrieve distinct values for a column in a table based on its data type.
    
    Args:
        cursor (psycopg2.cursor): The cursor object for executing SQL queries.
        table_name (str): The name of the table.
        column_name (str): The name of the column.
        data_type (str): The data type of the column.
        
    Returns:
        list: A list of distinct values for the column, converted to strings.
    """
    if data_type.startswith('character') or data_type == 'text':
        # Fetch distinct values for character or text columns
        cursor.execute(f"SELECT DISTINCT {column_name} FROM {table_name}")
    else:
        # Fetch a limited number of rows for other data types
        cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT 100")
    
    return [str(row[0]) for row in cursor.fetchall() if row[0] is not None]

def main():
    # PostgreSQL connection details
    pg_host = config['bihost']
    pg_database = config['bidbname']
    pg_user = config['biuser']
    pg_password = config['bipassword']

    # Output excel spreadsheet
    output_file = "bounty_database_schema_metadata.xlsx"

    # Connect to PostgreSQL
    conn = connect_to_postgres(pg_host, pg_database, pg_user, pg_password)
    cursor = conn.cursor(cursor_factory=DictCursor)

    # Create a new workbook
    workbook = Workbook()
    
    # Remove the default sheet created by openpyxl
    workbook.remove(workbook.active)

    # Get all table names
    table_info = get_table_names(cursor)

    # Process each table
    for schema, table_name in table_info:
        print(f"Processing table: {schema}.{table_name}")
        columns = get_column_info(cursor, schema, table_name)
        data = get_table_data(cursor, schema, table_name)
        if data:
            sheet_name = f"{schema}.{table_name}"[:31]  # Excel sheet names are limited to 31 characters
            write_to_excel(workbook, sheet_name, columns, data)

    # Save the workbook
    workbook.save(output_file)

    conn.close()
    print(f"Data extraction complete. Output saved to {output_file}")

if __name__ == "__main__":
    main()