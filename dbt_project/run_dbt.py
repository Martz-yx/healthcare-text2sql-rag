import os
import subprocess
from dotenv import load_dotenv

# Load env vars from project root .env
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if not os.path.exists(env_path):
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".env"))
print(f"Loading env from {env_path}")
load_dotenv(dotenv_path=env_path)

# Ensure DBT_PG_* variables are present by copying PG_* if missing
if 'DBT_PG_HOST' not in os.environ and 'PG_HOST' in os.environ:
    os.environ['DBT_PG_HOST'] = os.environ['PG_HOST']

print("DBT_PG_HOST:", os.environ.get("DBT_PG_HOST"))

try:
    # Explicitly pass the modified environment
    result = subprocess.run(
        ["dbt", "compile", "--write-catalog"],
        cwd=os.path.dirname(__file__),
        env=os.environ,
        check=True,
        capture_output=True,
        text=True
    )
    print("Success:")
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print("Failed:")
    print(e.stdout)
    print(e.stderr)
