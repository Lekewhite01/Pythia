import argparse
from sqlalchemy import create_engine, MetaData, inspect
import sys
import yaml
from typing import Optional

# Function to load configuration from a YAML file
def load_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

# Load the configuration
config = load_config('../secrets.yaml')

def delete_table(table_name: str, schema: Optional[str] = None, confirm: bool = True) -> bool:
    """
    Delete a table from the database.
    
    Args:
        table_name (str): Name of the table to delete
        schema (str, optional): Database schema name
        confirm (bool): Whether to ask for confirmation before deletion
    
    Returns:
        bool: True if table was deleted successfully, False otherwise
    """
    # Database connection settings
    DB_CONFIG = {
        'host': config['bihost'],
        'port': config['port'],
        'database': config['bidbname'],
        'user': config['biuser'],
        'password': config['bipassword']
    }
    
    try:
        # Create database URL
        db_url = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        
        # Create engine
        engine = create_engine(db_url)
        
        # Create MetaData instance
        metadata = MetaData()
        
        # Create inspector
        inspector = inspect(engine)
        
        # Check if schema exists (if provided)
        if schema and schema not in inspector.get_schema_names():
            print(f"Error: Schema '{schema}' does not exist")
            return False
        
        # Get list of tables in schema
        tables = inspector.get_table_names(schema=schema)
        
        # Check if table exists
        if table_name not in tables:
            print(f"Error: Table '{table_name}' does not exist" + 
                  (f" in schema '{schema}'" if schema else ""))
            return False
            
        # Confirm deletion if required
        if confirm:
            response = input(f"Are you sure you want to delete table '{table_name}'" +
                           (f" from schema '{schema}'" if schema else "") +
                           "? This action cannot be undone! (y/N): ")
            if response.lower() != 'y':
                print("Operation cancelled")
                return False
        
        # Connect to database and delete table
        with engine.connect() as connection:
            # Start transaction
            trans = connection.begin()
            try:
                # Construct and execute DROP TABLE statement
                schema_prefix = f"{schema}." if schema else ""
                connection.execute(f'DROP TABLE {schema_prefix}"{table_name}" CASCADE')
                
                # Commit transaction
                trans.commit()
                print(f"Successfully deleted table '{table_name}'" +
                      (f" from schema '{schema}'" if schema else ""))
                return True
                
            except Exception as e:
                # Rollback transaction on error
                trans.rollback()
                print(f"Error deleting table: {str(e)}")
                return False
                
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return False

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Delete a table from the database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add arguments
    parser.add_argument(
        'table_name',
        help='Name of the table to delete'
    )
    parser.add_argument(
        '--schema',
        help='Database schema name (optional)',
        default=None
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Delete without confirmation'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Call delete_table function with parsed arguments
    success = delete_table(
        table_name=args.table_name,
        schema=args.schema,
        confirm=not args.force
    )
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()