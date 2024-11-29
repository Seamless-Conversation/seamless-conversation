"""
Automatically create the database required for Seamless Conversation.
You need to have the postgresql service running.
"""
import logging
from models import Base
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine
from src.database.config import DatabaseConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseSetup:
    """Setup the database with the required tables"""
    def __init__(self, config: DatabaseConfig):
        self.config = config

    def setup_database(self) -> None:
        """Setup the database and initialize schema"""

        self._create_database_if_not_exists()

        self._initialize_schema()

        logger.info("Database setup completed successfully")

    def _create_database_if_not_exists(self):
        """Create the database if it doesn't exist"""
        try:
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                dbname='postgres'
            )
            conn.autocommit = True

            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"),
                    [self.config.database]
                )
                exists = cursor.fetchone()

                if not exists:
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {}").format(
                            sql.Identifier(self.config.database)
                        )
                    )
                    logger.info("Database '%s' created successfully", self.config.database)
                else:
                    logger.info("Database '%s' already exists", self.config.database)

        except Exception as e:
            logger.error("Error creating database: %s", str(e))
            raise
        finally:
            conn.close()

    def _initialize_schema(self):
        """Initialize database schema using SQLAlchemy models"""

        engine = create_engine(self.config.connection_string)

        try:
            Base.metadata.create_all(engine)
            logger.info("Database schema created successfully")

        except Exception as e:
            logger.error("Error creating schema: %s", str(e))
            raise
        finally:
            engine.dispose()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO
    )

    setup = DatabaseSetup(DatabaseConfig())

    setup.setup_database()
