import sqlite3
from logger import logger
from models.schemas import ExperimentSchema
from pydantic import ValidationError

class TrackerController:
    def __init__(self, db_name="lab_tracker.db"):
        self.db_name = db_name

    def check_duplicate_title(self, title):
        """Checks if an experiment title already exists (case-insensitive)."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM experiments WHERE LOWER(title) = LOWER(?)", (title,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except sqlite3.Error as e:
            logger.error(f"Error checking duplicate: {e}")
            return False

    def fetch_all_experiments(self):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, student_id, status FROM experiments")
            rows = cursor.fetchall()
            conn.close()
            return rows
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch records: {e}")
            return []

    def add_experiment(self, title, student_id, status):
        # Final safety check before inserting
        if self.check_duplicate_title(title):
            return False, f"An experiment titled '{title}' already exists."

        try:
            validated = ExperimentSchema(title=title, student_id=student_id, status=status)
        except ValidationError as e:
            msg = e.errors()[0]['msg']
            logger.warning(f"Add experiment validation failed: {msg}")
            return False, f"Validation Error: {msg}"
            
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO experiments (title, student_id, status) VALUES (?, ?, ?)", 
                (validated.title, validated.student_id, validated.status)
            )
            conn.commit()
            conn.close()
            logger.info(f"New experiment added: '{validated.title}'")
            return True, "Experiment added successfully!"
        except sqlite3.Error as e:
            logger.error(f"Error adding experiment: {e}")
            return False, "Database insertion failed."

    def update_status(self, exp_id, new_status):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("UPDATE experiments SET status = ? WHERE id = ?", (new_status, exp_id))
            conn.commit()
            conn.close()
            logger.info(f"Experiment ID {exp_id} updated to '{new_status}'")
            return True, f"Status updated to '{new_status}'!"
        except sqlite3.Error as e:
            logger.error(f"Error updating status: {e}")
            return False, "Failed to update status."

    def delete_experiment(self, exp_id):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))
            conn.commit()
            conn.close()
            logger.info(f"Experiment ID {exp_id} deleted.")
            return True, "Record deleted successfully!"
        except sqlite3.Error as e:
            logger.error(f"Error deleting record: {e}")
            return False, "Failed to delete record."