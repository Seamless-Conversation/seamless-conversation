import psycopg2
from psycopg2 import sql
import os

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'conversation_db')

def setup_database():
    try:
        # Connect to the PostgreSQL server
        print("Connecting to the PostgreSQL database...")
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        connection.autocommit = True  # Enable auto-commit for database creation
        
        cursor = connection.cursor()
        
        # Check if the database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}';")
        db_exists = cursor.fetchone()
        
        if not db_exists:
            # Create the database
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
            print(f"Database '{DB_NAME}' created successfully.")
        else:
            print(f"Database '{DB_NAME}' already exists.")
        
        cursor.close()
        connection.close()
        
        # Connect to the newly created database
        print(f"Connecting to the database '{DB_NAME}'...")
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        
        print("Connection successful.")
        connection.close()
    
    except psycopg2.OperationalError as e:
        print("Error: Unable to connect to the database.")
        print(e)
    except Exception as e:
        print("An error occurred:")
        print(e)

if __name__ == "__main__":
    setup_database()
