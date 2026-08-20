import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    connection = mysql.connector.connect(
        host=os.environ.get("MYSQLHOST"),
        port=int(os.environ.get("MYSQLPORT", 3306)),
        user=os.environ.get("MYSQLUSER"),
        password=os.environ.get("MYSQLPASSWORD"),
        database=os.environ.get("MYSQLDATABASE", "job_portal")
    )

    return connection