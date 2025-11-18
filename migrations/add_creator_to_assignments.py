import os
import sys
from sqlalchemy import create_engine, text

# Add project root to sys.path to allow importing project modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment variables
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable is not set. Please configure it in your .env file.")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def upgrade():
    """Applies the database migration."""
    try:
        with engine.connect() as connection:
            print("Connecting to the database to apply migration...")
            
            # Using a transaction ensures that all statements are executed successfully or none are.
            with connection.begin() as transaction:
                print("Step 1: Adding 'creator_id' column to the 'assignments' table...")
                
                # SQL statement to add the new column.
                # It's nullable to accommodate existing assignments that don't have a creator.
                add_column_sql = text("""
                    ALTER TABLE assignments
                    ADD COLUMN creator_id VARCHAR(20) NULL;
                """)
                connection.execute(add_column_sql)
                print("'creator_id' column added successfully.")

                print("Step 2: Adding foreign key constraint to 'creator_id'...")
                
                # SQL statement to add the foreign key constraint.
                # This links the new column to the 'users' table.
                # ON DELETE SET NULL means if a user is deleted, their created assignments' creator_id will be set to NULL.
                add_constraint_sql = text("""
                    ALTER TABLE assignments
                    ADD CONSTRAINT fk_assignments_creator
                    FOREIGN KEY (creator_id) REFERENCES users(student_id)
                    ON DELETE SET NULL;
                """)
                connection.execute(add_constraint_sql)
                print("Foreign key constraint 'fk_assignments_creator' added successfully.")
                
            # The transaction is automatically committed here if no exceptions were raised.
            print("\nMigration 'add_creator_to_assignments' applied successfully!")
            
    except Exception as e:
        print(f"\nAn error occurred during the migration: {e}")
        print("The migration failed and the transaction has been rolled back.")
        # The transaction is automatically rolled back on exception.

if __name__ == "__main__":
    print("=====================================================================")
    print("  Running migration script: add_creator_to_assignments.py")
    print("=====================================================================")
    upgrade()
