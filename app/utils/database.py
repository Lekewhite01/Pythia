"""
Database engine setup and lightweight query helpers.

This module wires up two SQLAlchemy engines from the credentials in
``secrets.yaml``:

    * ``engine``      — points at the BI database (the canonical analytics
      warehouse the role-based dashboard queries run against).
    * ``demo_engine`` — points at the demo database used by the
      ``/convert-nl-to-sql`` and CSV-upload endpoints.

It also exposes a handful of small helpers that wrap the most common
introspection / read patterns so the route handlers stay tidy.
"""

from sqlalchemy import create_engine, inspect
from sqlalchemy import text
import pandas as pd
import yaml


def load_config(config_file):
    """Read a YAML configuration file from disk and return it as a dict."""
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config


# Credentials and other secrets are kept in ``secrets.yaml`` so they don't
# leak into source control. NOTE: in production, prefer environment variables
# or a managed secret store (e.g. AWS Secrets Manager) over a YAML file.
config = load_config('secrets.yaml')

# ---------------------------------------------------------------------------
# BI database (default analytics target)
# ---------------------------------------------------------------------------
dbname = config['bidbname']
user = config['biuser']
password = config['bipassword']
host = config['bihost']
port = config['port']
DATABASE_URL = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"

engine = create_engine(DATABASE_URL)

# ---------------------------------------------------------------------------
# Demo database (used by NL-to-SQL and CSV-upload flows)
# ---------------------------------------------------------------------------
demo_dbname = config['demodbname']
demo_user = config['demouser']
demo_password = config['demopassword']
demo_host = config['demohost']
demo_port = config['port']
demo_DATABASE_URL = (
    f"postgresql+psycopg2://{demo_user}:{demo_password}"
    f"@{demo_host}:{port}/{demo_dbname}"
)

demo_engine = create_engine(demo_DATABASE_URL)


def get_demo_db():
    """
    Return a SQLAlchemy inspector for the demo database.

    Wrapped as a function so it can be used as a FastAPI dependency
    (``Depends(get_demo_db)``), giving each request its own inspector handle.
    """
    db = inspect(demo_engine)
    return db


def get_db():
    """
    Return a SQLAlchemy inspector for the BI database.

    Wrapped as a function for the same reason as :func:`get_demo_db` — it
    plugs straight into FastAPI's dependency-injection system.
    """
    db = inspect(engine)
    return db


def get_tables_in_creation_order(engine):
    """
    Return all table names in the given database.

    Parameters
    ----------
    engine : sqlalchemy.engine.base.Engine
        The SQLAlchemy engine (or inspector) connected to the database.

    Returns
    -------
    list[str]
        Table names, in the order the inspector reports them — for most
        backends this corresponds to creation order.
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    return table_names


def query_to_dataframe(db, table_name: str):
    """
    Return a 5-row preview of ``table_name`` as a pandas DataFrame.

    Designed for the frontend's "show me a sample" feature — we cap the
    result at 5 rows to keep the payload small.

    Parameters
    ----------
    db : sqlalchemy inspector
        Inspector bound to the target engine.
    table_name : str
        Name of the table to preview.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing the first 5 rows of the table.

    Raises
    ------
    sqlalchemy.exc.SQLAlchemyError
        If the underlying query fails.
    """
    sql_query = text(f"SELECT * FROM {table_name} LIMIT 5")

    # Use the bound engine to open a short-lived connection.
    with db.bind.connect() as conn:
        result = conn.execute(sql_query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

    return df


def read_table(table_name: str) -> pd.DataFrame:
    """
    Load an entire table from the BI database into a pandas DataFrame.

    Useful when the LLM needs to inspect the actual contents of a table
    (e.g. when suggesting analytical questions).

    Parameters
    ----------
    table_name : str
        The name of the table to fetch.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing every row of the requested table.
    """
    df = pd.read_sql_table(table_name, engine)
    return df
