from sqlalchemy import create_engine, inspect, text, MetaData
from sqlalchemy.schema import CreateTable, DropTable
from sqlalchemy.orm import sessionmaker
import click
from typing import List, Optional
import sys

from src.database.models import Base, ConversationGroup, Message, Agent, ConversationParticipant
from src.database.config import DatabaseConfig

class DatabaseManager:
    def __init__(self, config: DatabaseConfig):
        self.engine = create_engine(config.connection_string)
        self.Session = sessionmaker(bind=self.engine)
        self.inspector = inspect(self.engine)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)

    def wipe_structure(self):
        """Completely drops and recreates the database structure"""
        Base.metadata.drop_all(self.engine)
        print("Database structure has been dropped.")
        
        Base.metadata.create_all(self.engine)
        print("Database structure has been recreated.")

    def wipe_messages(self):
        """Wipes all data but keeps the structure"""
        session = self.Session()
        try:
            # Delete in proper order to respect foreign keys
            session.execute(text('DELETE FROM messages'))
            session.execute(text('DELETE FROM conversation_participants'))
            session.execute(text('DELETE FROM conversation_groups'))
            session.execute(text('DELETE FROM agents'))
            session.commit()
            print("All data has been wiped while preserving structure.")
        except Exception as e:
            session.rollback()
            print(f"Error wiping data: {str(e)}")
        finally:
            session.close()

    def list_structure(self):
        """Lists current database structure"""
        print("\nCurrent Database Structure:")
        print("==========================")
        
        for table_name in self.inspector.get_table_names():
            print(f"\nTable: {table_name}")
            print("-" * (len(table_name) + 7))
            
            # Get columns
            columns = self.inspector.get_columns(table_name)
            print("Columns:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f"DEFAULT {col['default']}" if col['default'] else ""
                print(f"  - {col['name']}: {col['type']} {nullable} {default}")
            
            # Get primary keys
            pks = self.inspector.get_pk_constraint(table_name)
            if pks['constrained_columns']:
                print("\nPrimary Keys:")
                print(f"  {', '.join(pks['constrained_columns'])}")
            
            # Get foreign keys
            fks = self.inspector.get_foreign_keys(table_name)
            if fks:
                print("\nForeign Keys:")
                for fk in fks:
                    print(f"  {', '.join(fk['constrained_columns'])} -> {fk['referred_table']}.{', '.join(fk['referred_columns'])}")
            
            # Get indices
            indices = self.inspector.get_indexes(table_name)
            if indices:
                print("\nIndices:")
                for index in indices:
                    unique = "UNIQUE " if index['unique'] else ""
                    print(f"  {unique}INDEX {index['name']} ON ({', '.join(index['column_names'])})")

    def add_column(self, table_name: str, column_name: str, column_type: str, nullable: bool = True, default: Optional[str] = None):
        """Adds a new column to specified table"""
        session = self.Session()
        try:
            # Construct ALTER TABLE statement
            nullable_str = "" if nullable else "NOT NULL"
            default_str = f"DEFAULT {default}" if default else ""
            
            alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {nullable_str} {default_str}"
            session.execute(text(alter_stmt))
            session.commit()
            print(f"Added column {column_name} to table {table_name}")
        except Exception as e:
            session.rollback()
            print(f"Error adding column: {str(e)}")
        finally:
            session.close()

    def remove_column(self, table_name: str, column_name: str):
        """Removes a column from specified table"""
        session = self.Session()
        try:
            alter_stmt = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
            session.execute(text(alter_stmt))
            session.commit()
            print(f"Removed column {column_name} from table {table_name}")
        except Exception as e:
            session.rollback()
            print(f"Error removing column: {str(e)}")
        finally:
            session.close()

@click.group()
def cli():
    """Database management CLI"""
    pass

@cli.command()
def wipe_structure():
    """Wipes and recreates database structure"""
    if click.confirm('Are you sure you want to wipe the entire database structure?', abort=True):
        db_manager = DatabaseManager(DatabaseConfig())
        db_manager.wipe_structure()

@cli.command()
def wipe_data():
    """Wipes all data but keeps structure"""
    if click.confirm('Are you sure you want to wipe all data from the database?', abort=True):
        db_manager = DatabaseManager(DatabaseConfig())
        db_manager.wipe_messages()

@cli.command()
def show_structure():
    """Shows current database structure"""
    db_manager = DatabaseManager(DatabaseConfig())
    db_manager.list_structure()

@cli.command()
@click.argument('table_name')
@click.argument('column_name')
@click.argument('column_type')
@click.option('--nullable', is_flag=True, default=True, help='Whether the column can be NULL')
@click.option('--default', help='Default value for the column')
def add_column(table_name: str, column_name: str, column_type: str, nullable: bool, default: Optional[str]):
    """Adds a new column to a table"""
    db_manager = DatabaseManager(DatabaseConfig())
    db_manager.add_column(table_name, column_name, column_type, nullable, default)

@cli.command()
@click.argument('table_name')
@click.argument('column_name')
def remove_column(table_name: str, column_name: str):
    """Removes a column from a table"""
    if click.confirm(f'Are you sure you want to remove column {column_name} from {table_name}?', abort=True):
        db_manager = DatabaseManager(DatabaseConfig())
        db_manager.remove_column(table_name, column_name)

if __name__ == '__main__':
    cli()