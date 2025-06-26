import os
import psycopg2
import yaml
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path

def load_config(config_file):
    config_path = Path(__file__).parent.parent / config_file
    with config_path.open('r') as file:
        config = yaml.safe_load(file)
    return config

config = load_config('secrets.yaml')

def delete_all_tables(db_params):
    try:
        with psycopg2.connect(**db_params) as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                # Disable foreign key checks
                cur.execute("SET session_replication_role = 'replica';")
                
                # Get all table names in the current schema
                cur.execute("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = current_schema();
                """)
                tables = cur.fetchall()
                
                if tables:
                    # Generate DROP TABLE statements
                    drop_statements = [f'DROP TABLE IF EXISTS "{table[0]}" CASCADE;' for table in tables]
                    
                    # Execute all DROP TABLE statements in a single command
                    cur.execute('\n'.join(drop_statements))
                    print(f"Successfully deleted {len(tables)} tables.")
                else:
                    print("No tables found to delete.")
                
                # Re-enable foreign key checks
                cur.execute("SET session_replication_role = 'origin';")
    
    except psycopg2.Error as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    db_params = {
        'dbname': config['demodbname'],
        'user': config['demouser'],
        'password': config['demopassword'],
        'host': config['demohost'],
        'port': 5432
    }
    delete_all_tables(db_params)