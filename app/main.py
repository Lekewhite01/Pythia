import json
from fastapi import (FastAPI, 
                     HTTPException, 
                     Depends, 
                     File, 
                     UploadFile, 
                     Form)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import reflection
from mangum import Mangum
from pydantic import ValidationError
from typing import List, Dict, Any
from sqlalchemy.inspection import inspect
from openai import OpenAI
from datetime import datetime
from utils.database import  *
from utils.response_model import *
import matplotlib.pyplot as plt
import pandas as pd
import ast
import base64
import re
import io
import logging
import instructor
import sqlalchemy as sa

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a custom formatter that includes timestamp and request ID
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
)

# Add handlers if needed (console, file, etc.)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


OPENAI_API_KEY = config['OPENAI_API_KEY']
    
# Patch the OpenAI client
client = instructor.from_openai(OpenAI(api_key=OPENAI_API_KEY))

app = FastAPI()

# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

@app.post("/convert-nl-to-sql")
async def convert_nl_to_sql(data: dict, db: Session = Depends(get_demo_db)):
    prompt = data['prompt']

    try:
        table_names = "\n".join(db.get_table_names())

        system = f"""Identify and return the names of ALL SQL tables that are directly relevant to the input prompt: "{prompt}". 

            The tables available in the database are:

            {table_names}

            Guidelines:
            - **Only include tables from the provided list**.
            - If the input prompt contains irrelevant or unrelated questions (i.e., not tied to the available tables or their content), **return an empty list**.
            - Ensure that the identified tables are **meaningfully connected** to the input question's context.
            - Do not infer or assume the presence of additional tables beyond those listed.

            Return the result strictly as a **list of strings**."""

        
        try:
            response = client.chat.completions.create(
                model="gpt-4-0125-preview",
                response_model=TableOutput,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ]
            )
            # print(ast.literal_eval(str(response).split('=')[1]))
            relevant_tables = ast.literal_eval(str(response).split('=')[1])
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            # logger.error(f"Unexpected error: {e}")
            # raise HTTPException(status_code=500, detail=str(e))
            logger.error("This query is unrelated to the data and there is no data available to answer it")
        
        # Assuming db is your database connection or engine
        inspector = inspect(db.engine if hasattr(db, 'engine') else db)

        # Get schema information for relevant tables, including data types
        table_schemas = {}
        for table_name in relevant_tables:
            try:
                columns = inspector.get_columns(table_name)
                # Store both column names and data types
                table_schemas[table_name] = [{col['name']: str(col['type'])} for col in columns]
            except SQLAlchemyError as e:
                logger.error(f"SQLAlchemy error fetching schema for table {table_name}: {e}")
                table_schemas[table_name] = []
            except Exception as e:
                logger.error(f"Unexpected error fetching schema for table {table_name}: {e}")
                table_schemas[table_name] = []

        if not any(table_schemas.values()):
            for table_name in relevant_tables:
                try:
                    # Raw SQL to fetch both column names and data types
                    query = sa.text(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = :table_name
                    """)
                    result = db.execute(query, {"table_name": table_name})
                    # Store both column names and data types in table_schemas
                    table_schemas[table_name] = [{row['column_name']: row['data_type']} for row in result]
                except Exception as e:
                    logger.error(f"Error fetching schema for table {table_name} using raw SQL: {e}")
                    table_schemas[table_name] = []

        # Format table schemas for the AI model, including both column names and types
        formatted_schemas = "\n".join([f"{table}: {', '.join([f'{col_name} ({col_type})' for col_dict in columns for col_name, col_type in col_dict.items()])}" 
                                    for table, columns in table_schemas.items()])


        system_for_sql = f'''Given an input question, generate three distinct outputs:

            1. A SQL query that fulfills the request.
            2. A very detailed answer to the user's question including context and proof. 
            3. A suggested chart type (bar, pie, line, scatter, area, or table) based on the analysis being queried.
            4. A JSON of relevant datapoints from the data to visualize the suggested chart type.

            Use the following format:

            {{
                "sql_query": "Syntactically correct and executable SQL query that answers the user's question",
                "natural_language": "Detailed answer to the user's question",
                "chart_type": "A suggested chart type (bar, pie, line, scatter, area, or table) based on the analysis being queried",
                "visualization_data": "A JSON of relevant datapoints from the data to visualize the suggested chart type"
            }}

            Only use the following tables and their respective columns with proper data types:
            {formatted_schemas}

            Question: {prompt}

            Do not make up or use columns that don't exist in the tables.
            Use appropriate joins where necessary and ensure to use aggregation and grouping for the results.
            Ensure your output does not include any additional formatting symbols or code block indicators. 
            The response should begin and end with curly braces, consistent with standard JSON format.

            For the "natural_language" key, provide a direct answer to the question as if the SQL query has been executed. Do not describe the query or the results, just state the answer.

            Now, please provide the response for the given question using this format and level of directness.'''

        response = client.chat.completions.create(
            model="gpt-4-0125-preview",
            response_model=Nltosql,
            temperature=0,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates SQL queries based on questions."},
                {"role": "user", "content": system_for_sql}
            ]
        )

        # Extract SQL query from the response
        sql_query = response.SQLQuery
        natural_language = response.NaturalLanguage
        chart_type = response.ChartType
        visualization_data = json.loads(response.VisualizationData)

        df = pd.read_sql(sql=sql_query, con=engine)

        print("Query executed successfully")

        print(df.head())
    
        # Prepare the response
        response_data = {
            "sql_query": sql_query,
            "natural_language": natural_language,
            "chart_type": chart_type,
            "visualization_data": visualization_data
        }

        return JSONResponse(content=response_data)
        # return response

    except Exception as e:
        error_message = "This query is unrelated to the data and there is no data available to answer it"
        logger.error(f"{error_message}: {e}")
        raise HTTPException(status_code=500, detail=error_message)


@app.get("/tables_in_creation_order/")
async def tables_in_creation_order(db: Session = Depends(get_db)):
    try:
        tables_order = get_tables_in_creation_order(db)
        return JSONResponse(content={"tables_in_creation_order": tables_order}, status_code=200)
    except SQLAlchemyError as e:
        return HTTPException(status_code=500, detail=str(e))

@app.get("/execute_query/")
async def execute_query(table_name: str, db: Session = Depends(get_db)):
    try:
        result_df = query_to_dataframe(db, table_name)
        json_result = result_df.to_json(orient="records")
        return HTMLResponse(content=json_result, status_code=200)
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/createtable/")
async def create_table_csv(table_name: str = Form(...), file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        df.to_sql(table_name, con=demo_engine.connect(), if_exists='append', index=False)
        response_data = {
            "table_name": table_name,
            "filename": file.filename,
            "rows": len(df)
        }
        return JSONResponse(content=jsonable_encoder(response_data), status_code=200)
    
    except Exception as e:
        return JSONResponse(
            content={
                'status': 'Failed',
                'body': json.dumps({"error": repr(e)})
            },
            status_code=500
        )
    
@app.get("/questions/")
def generate_questions(table_name: str):
    try:
        df = read_table(table_name)
        
        nl_query = f"""
            Using the provided table named "{table_name}", please generate this output:

            1. A list of four user questions for analysis of the data in "{table_name}"

            Your response must be a valid Python list containing exactly four dictionaries. 
            Each dictionary should have two key-value pairs:
                - "actual_question": The actual question asked by the user.
                - "summary_question": A summary version or title of the question.

            Ensure your output follows this format:
            [
                {{ "actual_question": "Question 1", "summary_question": "Summary 1" }},
                {{ "actual_question": "Question 2", "summary_question": "Summary 2" }},
                {{ "actual_question": "Question 3", "summary_question": "Summary 3" }},
                {{ "actual_question": "Question 4", "summary_question": "Summary 4" }}
            ]

            Ensure your output contains no additional formatting symbols or code block indicators.
            """

        response = client.chat.completions.create(
            model="gpt-4-0125-preview",
            response_model=QuestionsOutput,
            temperature=0,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates analytical questions based on table data."},
                {"role": "user", "content": nl_query}
            ]
        )

        questions_list = json.loads(response.choices[0].message.content)
        response_data = {"questions": questions_list}
        return JSONResponse(content=jsonable_encoder(response_data), status_code=200)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred while processing the request.")

@app.post("/bi-dashboard-data")
async def bi_data(data: dict, db_config: DatabaseConfig = Depends(), db: Session = Depends(get_bi_db)):
    """
    Endpoint to retrieve BI dashboard data based on user roles.
    """
    request_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    log_context = {'request_id': request_id}
    
    logger.info("Received BI dashboard data request", extra={
        **log_context,
        'input_data': json.dumps(data, default=str)
    })

    try:
        # Input validation
        if not data:
            logger.error("Empty request body", extra=log_context)
            raise HTTPException(status_code=400, detail="Request body is empty")
        
        # Normalize input to handle both single role and array of roles
        roles = data.get("roles", [data.get("role")])
        if not roles:
            logger.error("No roles provided in request", extra=log_context)
            raise HTTPException(status_code=400, detail="No roles provided")
        
        if not isinstance(roles, list):
            roles = [roles]
            logger.info(f"Normalized single role to list: {roles}", extra=log_context)

        # Validate that all roles are strings
        if not all(isinstance(role, str) for role in roles):
            logger.error(f"Invalid role types found in request: {roles}", extra=log_context)
            raise HTTPException(status_code=400, detail="All roles must be strings")
        
        # Add timeout for database operations
        timeout = 29000  # 29 seconds (Lambda has 30s default timeout)
        engine = db.get_bind() if hasattr(db, 'get_bind') else db.engine
        engine = engine.execution_options(timeout=timeout)
        
        logger.info(f"Fetching table names for database", extra=log_context)
        try:
            with engine.connect() as connection:
                table_names = "\n".join(inspect(connection).get_table_names())
        except SQLAlchemyError as e:
            logger.error(f"Database timeout while fetching tables: {str(e)}", extra=log_context)
            raise HTTPException(status_code=503, detail="Database operation timed out")
            
        logger.debug(f"Retrieved tables: {table_names}", extra=log_context)

        # Define dashboard questions for each role
        dashboard_questions = {
            "marketing": """what is the Campaign ROI, Customer acquisition cost, Conversion rates,
                Click-through rates (CTR) on advertisements, Engagement rates?""",
            "vip": """what is the Number of VIP customers, VIP customer lifetime value (CLV), VIP churn rate,
                VIP engagement (events attended, exclusive offers used)""",
            "fraud": "what is the Number of detected fraud cases, Amount of money involved in fraud, Fraud detection rate, \
                Types of fraud detected (account takeover, payment fraud, etc.)",
            "product": "Product popularity (number of plays/bets), Average session duration, Revenue generated per product, \
                Customer satisfaction/feedback scores",
            "finance": "what is the total revenue, Operating expenses, Profit margins, Cash flow, \
                Key financial ratios (ROA, ROE, etc.)",
            "support": "what is the Number of support tickets, Average resolution time, Customer satisfaction scores, \
                First contact resolution rate",
            "retail": "what is the Number of retail outlets, Revenue per outlet, Foot traffic \
                Customer engagement in retail settings"
        }

        # Validate roles against available dashboard questions
        valid_roles = set(dashboard_questions.keys()) | {"overview"}
        invalid_roles = [role for role in roles if role not in valid_roles]
        if invalid_roles:
            logger.error(f"Invalid roles found in request: {invalid_roles}", extra=log_context)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid roles provided: {', '.join(invalid_roles)}"
            )

        # If 'overview' is in roles, process roles in batches
        if "overview" in roles:
            batch_size = 3  # Process 3 roles at a time
            original_roles = list(dashboard_questions.keys())
            results = []
            
            for i in range(0, len(original_roles), batch_size):
                batch_roles = original_roles[i:i + batch_size]
                logger.info(f"Processing batch of roles: {batch_roles}", extra=log_context)
                
                try:
                    batch_result = await process_batch(
                        batch_roles,
                        dashboard_questions,
                        table_names,
                        engine,
                        log_context,
                        client
                    )
                    results.extend(batch_result)
                except Exception as e:
                    logger.error(f"Error processing batch {batch_roles}: {str(e)}", extra=log_context)
                    continue
                
            if not results:
                raise HTTPException(status_code=503, detail="Failed to process admin role queries")
            
            return {"Roles": ["admin"], "SQLQueries": results}
        else:
            # Process non-admin roles normally
            return await process_batch(
                roles,
                dashboard_questions,
                table_names,
                engine,
                log_context,
                client
            )

    except HTTPException as he:
        logger.error(f"HTTP Exception: {he.detail}", extra=log_context)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in bi_data endpoint: {str(e)}", extra=log_context)
        return JSONResponse(
            status_code=500,
            content={"status": "Failed", "error": "An unexpected error occurred"}
        )
    finally:
        logger.info("Request processing completed", extra=log_context)

async def process_batch(
    roles: List[str],
    dashboard_questions: Dict[str, str],
    table_names: str,
    engine: Any,
    log_context: Dict[str, str],
    client: Any
) -> Dict[str, Any]:
    """
    Process a batch of roles and generate corresponding SQL queries.
    
    Args:
        roles: List of roles to process
        dashboard_questions: Dictionary mapping roles to questions
        table_names: String containing available table names
        engine: SQLAlchemy engine
        log_context: Logging context dictionary
        client: AI client for generating queries
    
    Returns:
        Dictionary containing roles and generated SQL queries
    """
    try:
        # Collect questions for all requested roles
        combined_questions = set()
        for role in roles:
            if role in dashboard_questions:
                combined_questions.add(dashboard_questions[role])
                logger.debug(f"Added questions for role: {role}", extra=log_context)

        if not combined_questions:
            logger.error("No valid questions found for provided roles", extra=log_context)
            raise HTTPException(
                status_code=400,
                detail="No valid questions found for the provided roles"
            )

        # Join all questions
        combined_questions = " ".join(combined_questions)
        
        # Get relevant tables from AI model
        system = f"""Return the names of ALL the SQL tables that MIGHT be relevant to {combined_questions}. \
        The tables are:

        {table_names}

        Remember to include only tables from the database,
        and return the names as strings not table types."""
        
        try:
            logger.info("Requesting table information from AI model", extra=log_context)
            table_response = client.chat.completions.create(
                model="gpt-4-0125-preview",
                response_model=TableOutput,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": combined_questions}
                ]
            )
            
            if not table_response:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get table information from AI model"
                )
                
            relevant_tables = ast.literal_eval(str(table_response).split('=')[1])
            logger.info(f"Retrieved relevant tables: {relevant_tables}", extra=log_context)
            
        except Exception as e:
            logger.error(f"Error getting table information: {str(e)}", extra=log_context)
            raise HTTPException(status_code=500, detail="Failed to get table information")

        # Get schema information for relevant tables
        table_schemas = {}
        inspector = reflection.Inspector(engine)
        
        for table_name in relevant_tables:
            try:
                columns = inspector.get_columns(table_name)
                table_schemas[table_name] = [{col['name']: str(col['type'])} for col in columns]
            except Exception as e:
                logger.error(f"Error getting schema for {table_name}: {str(e)}", extra=log_context)
                continue

        if not table_schemas:
            logger.warning("Falling back to raw SQL for schema retrieval", extra=log_context)
            try:
                with engine.connect() as connection:
                    for table_name in relevant_tables:
                        query = sa.text("""
                            SELECT column_name, data_type 
                            FROM information_schema.columns 
                            WHERE table_name = :table_name
                        """)
                        result = connection.execute(query, {"table_name": table_name})
                        table_schemas[table_name] = [
                            {row['column_name']: row['data_type']} 
                            for row in result
                        ]
            except Exception as e:
                logger.error(f"Error in raw SQL schema retrieval: {str(e)}", extra=log_context)
                raise HTTPException(status_code=500, detail="Failed to retrieve schema information")

        # Format schema information
        formatted_schemas = "\n".join([
            f"{table}: {', '.join([f'{list(col.keys())[0]} ({list(col.values())[0]})' for col in columns])}" 
            for table, columns in table_schemas.items()
        ])

        # Generate SQL queries
        system_for_sql = f'''Given an input question(s), create syntactically correct SQL queries to run in order to retrieve the required data in **PostgreSQL**.

            Use the following format:

            {{
                "Roles": {roles},
                "SQLQueries": [
                    JSON objects each with key-value pairs of the metric and corresponding SQL query.
                ]
            }}

            Only use the following tables and their respective columns with proper data types:
            {formatted_schemas}

            Question: {combined_questions}
            The metrics to be queried have been mentioned in the question.
            - **Use only PostgreSQL-compatible functions and syntax**. 
            - Ensure to **avoid SQLite-specific functions like `julianday`** and stick to PostgreSQL alternatives (e.g., `EXTRACT`, `AGE`, `INTERVAL`).
            - Do not use or assume columns that do not exist in the provided schemas.
            - Use appropriate **JOINs** where necessary, and ensure aggregation and grouping as required by the question.

            Ensure your output does not include any additional formatting symbols or code block indicators. 
            The response should begin and end with curly braces, consistent with standard JSON format.'''


        try:
            logger.info("Requesting SQL queries from AI model", extra=log_context)
            sql_response = client.chat.completions.create(
                model="gpt-4-0125-preview",
                response_model=BiOutput,
                temperature=0,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates SQL queries based on questions."},
                    {"role": "user", "content": system_for_sql}
                ]
            )
            
            if not sql_response:
                raise HTTPException(status_code=500, detail="Failed to generate SQL queries")
                
            logger.info("Successfully generated SQL queries", extra={
                **log_context,
                'response_size': len(str(sql_response))
            })
            
            return sql_response
            
        except Exception as e:
            logger.error(f"Error generating SQL queries: {str(e)}", extra=log_context)
            raise HTTPException(status_code=500, detail="Failed to generate SQL queries")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in process_batch: {str(e)}", extra=log_context)
        raise HTTPException(status_code=500, detail="Failed to process batch")

handler = Mangum(app)