"""
Destructive maintenance script that drops every table in the demo database.

Use with extreme care — there is no confirmation prompt. The script is meant
for resetting the demo environment between test runs, not for production use.
"""

import os
import psycopg2
import yaml
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path


def load_config(config_file):
    """Load a YAML configuration file located alongside this package."""
    config_path = Path(__file__).parent.parent / config_file
    with config_path.open('r') as file:
        config = yaml.safe_load(file)
    return config


config = load_config('secrets.yaml')


def delete_all_tables(db_params):
    """
    Drop every table in the current schema of the target database.

    Foreign-key checks are disabled for the duration of the operation so that
    tables can be dropped without worrying about declaration order.

    Args:
        db_params: Dict of psycopg2 connection kwargs
                   (``dbname``, ``user``, ``password``, ``host``, ``port``).
    """
    try:
        with psycopg2.connect(**db_params) as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                # Disable foreign key checks so DROPs are order-independent.
                cur.execute("SET session_replication_role = 'replica';")

                # Enumerate every user table in the current schema.
                cur.execute("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = current_schema();
                """)
                tables = cur.fetchall()

                if tables:
                    # Build one batched statement so we make a single round trip.
                    drop_statements = [
                        f'DROP TABLE IF EXISTS "{table[0]}" CASCADE;'
                        for table in tables
                    ]
                    cur.execute('\n'.join(drop_statements))
                    print(f"Successfully deleted {len(tables)} tables.")
                else:
                    print("No tables found to delete.")

                # Restore normal foreign-key enforcement before disconnecting.
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
