from sqlalchemy import create_engine, inspect
from sqlalchemy import text
import pandas as pd
import yaml
# import sys
# sys.path.append('..')

# Function to load configuration from a YAML file
def load_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config

# Load the configuration
config = load_config('secrets.yaml')

# For the General DB instance
# dbname = config['dbname']
# user = config['user']
# password = config['password']
# host = config['host'] 
# port = config['port']
# DATABASE_URL = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"

# For the BI DB instance
dbname = config['bidbname']
user = config['biuser']
password = config['bipassword']
host = config['bihost'] 
port = config['port']
DATABASE_URL = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"

# Create SQLAlchemy engine for Postgres database
engine = create_engine(DATABASE_URL)

# For demo (Players an withdrawals)
demo_dbname = config['demodbname']
demo_user = config['demouser']
demo_password = config['demopassword']
demo_host = config['demohost'] 
demo_port = config['port']
demo_DATABASE_URL = f"postgresql+psycopg2://{demo_user}:{demo_password}@{demo_host}:{port}/{demo_dbname}"


demo_engine = create_engine(demo_DATABASE_URL)

def get_demo_db():
    """
    Create and return a SQLAlchemy database engine.

    Returns:
    - sqlalchemy.engine.base.Engine: An instance of the SQLAlchemy database engine.
    """
    db = inspect(demo_engine)
    return db

def get_db():
    """
    Create and return a SQLAlchemy database engine.

    Returns:
    - sqlalchemy.engine.base.Engine: An instance of the SQLAlchemy database engine.
    """
    db = inspect(engine)
    return db

def get_tables_in_creation_order(engine):
    """
    Retrieve a list of table names in the database in the order they were created.

    Parameters:
    - engine (sqlalchemy.engine.base.Engine): The SQLAlchemy engine connected to the database.

    Returns:
    - list: A list of table names in the order they were created.
    """
    # Create an inspector for the provided engine
    inspector = inspect(engine)

    # Get a list of table names in the database
    table_names = inspector.get_table_names()

    return table_names


def query_to_dataframe(db, table_name: str):
    """
    Executes an SQL query to fetch a limited number of rows from a specified table
    using a PGInspector object and returns the results as a DataFrame.

    Parameters:
        db: The database object (assumed to be a PGInspector or similar)
        table_name (str): The name of the table from which data will be fetched.

    Returns:
        pandas.DataFrame: A DataFrame containing the limited results of the SQL query.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: If there is an error executing the SQL query.
    """
    # Constructing the SQL query to select all columns from the specified table with a limit of 5 rows
    sql_query = text(f"SELECT * FROM {table_name} LIMIT 5")

    # Execute the query using the db object's execute method
    with db.bind.connect() as conn:
        result = conn.execute(sql_query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

    return df

def read_table(table_name: str) -> pd.DataFrame:
    """
    Fetches data from the specified database table and returns it as a pandas DataFrame.

    This function uses SQLAlchemy to connect to a database, reads the entire table 
    specified by the table_name parameter, and loads it into a pandas DataFrame.

    Parameters:
    ----------
    table_name : str
        The name of the table to be fetched from the database.

    Returns:
    -------
    pd.DataFrame
        A DataFrame containing the data from the specified table.
    """
    # Use pandas to read the specified table from the database
    df = pd.read_sql_table(table_name, engine)
    
    # Return the resulting DataFrame
    return df