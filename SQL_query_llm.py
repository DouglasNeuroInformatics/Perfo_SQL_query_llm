import streamlit as st
import pandas as pd
import pypyodbc
from groq import Groq
import re
from PIL import Image
import time

# Initialize the Groq client
client = Groq(api_key='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')  # Replace with your actual API key

# Set Streamlit layout to wide and customize page background color
st.set_page_config(layout="wide")

# SQL Database Connection setup
def connect_db():
    return pypyodbc.connect("Driver={ODBC Driver 17 for SQL Server};"
                            "Server=DESKTOP-QT6VLDE\\SQLEXPRESS;"
                            "Database=AdventureWorks2022;"
                            "Trusted_Connection=yes;")

# Display banner image at the top of the app with reduced height
image1 = Image.open('ciusss.png')
st.sidebar.image(image1)

st.sidebar.header('Filters')

# Table name input
table_name = st.sidebar.text_input('Table Name', 'ProductListPriceHistory')

# Schema input
schema_name = st.sidebar.text_input('Schema', 'Production')

# Model selection
model_name = st.sidebar.selectbox(
    "Select an LLM from the list",
    ("llama-3.1-8b-instant", "gemma2-9b-it", "llama3-groq-8b-8192-tool-use-preview"),
)

# Sidebar Pic
image2 = Image.open('Douglas.png')
image3 = Image.open('D3SM.png')
st.image([image2,image3], width=200, output_format="PNG")
#st.image(image3, width=300, output_format="PNG")

# Set up two columns
left_col, right_col = st.columns(2)

# Function to extract metadata from the specified table
def extract_table_metadata(table_name, schema_name):
    connection = connect_db()
    cursor = connection.cursor()
    metadata_query = f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'"
    cursor.execute(metadata_query)
    columns = cursor.fetchall()
    column_metadata = {f"[{col[0]}]": col[1] for col in columns}
    connection.close()
    return column_metadata

# Function to generate SQL query
def generate_sql_query(question, column_metadata, table_name, schema_name):
    full_table_name = f"{schema_name}.[{table_name}]"
    prompt = f"""Generate only 1 SQL query based on this question: {question}.
    The table to use is '{full_table_name}'. The columns are: {', '.join(column_metadata.keys())}.
    Use only the columns needed to answer the question, not all of them.
    Make sure to convert values to the right format before aggregating."""
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        model=model_name,
    )
    response = chat_completion.choices[0].message.content.strip()
    return extract_sql_from_response(response)

# Function to extract SQL query from response
def extract_sql_from_response(response):
    queries = re.findall(r"SELECT.*?;", response, re.IGNORECASE | re.DOTALL)
    if queries:
        return queries[0].strip().rstrip(';')
    else:
        raise ValueError("No valid SQL query found.")

# Function to fetch data from SQL
def fetch_answer_from_db(sql_query):
    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(sql_query)
    columns = [column[0] for column in cursor.description]
    result = cursor.fetchall()
    df = pd.DataFrame(result, columns=columns)
    connection.close()
    return df

# Function to answer the question based on the DataFrame
def answer_question_from_df(question, df):
    df_json = df.to_json(orient='records')
    prompt = f"Based on the following data, answer this question: {question}. Here is the data: {df_json}"
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        model=model_name,
    )
    return chat_completion.choices[0].message.content.strip()

# Function to run the complete process (with retries)
def run_with_retries(question, retries=3):
    success = False
    attempt = 0
    result_df = None
    answer = None

    while attempt < retries and not success:
        try:
            attempt += 1
            column_metadata = extract_table_metadata(table_name, schema_name)
            sql_query = generate_sql_query(question, column_metadata, table_name, schema_name)
            
            # Display the generated SQL query
            st.subheader(f"Generated SQL Query (Attempt {attempt})")
            st.code(sql_query)  # Display SQL query in a code block

            result_df = fetch_answer_from_db(sql_query)
            answer = answer_question_from_df(question, result_df)
            
            success = True  # Mark as success if no errors occur
        except Exception as e:
            st.warning(f"Attempt {attempt} failed with error: {e}")
            time.sleep(1)  # Wait before retrying
    
    if success:
        return result_df, answer
    else:
        st.error("Failed to process the request after 3 attempts.")
        return None, None

# Main logic in the left column (Question input and Answer)
with left_col:
    st.header("Ask a Question")
    question = st.text_input("Enter your question", " List the 20 highest product prices ?")
    
    if st.button('Submit'):
        df, answer = run_with_retries(question)
        
        if df is not None and answer is not None:
            st.subheader("Answer")
            st.write(answer)

# Right column to display the DataFrame
with right_col:
    st.header("Extracted Data")
    if 'df' in locals() and df is not None:
        st.dataframe(df)


# Streamlit run multile_llms.py