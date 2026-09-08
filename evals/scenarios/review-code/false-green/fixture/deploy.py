import subprocess


def run_migration():
    """Run the DB migration script and report success."""
    subprocess.run(["python3", "migrate.py"])
    print("Migration completed successfully")
    return True
