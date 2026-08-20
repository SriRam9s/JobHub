import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    connection = mysql.connector.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT", 3306)),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        ssl_ca=os.path.join(os.path.dirname(__file__), "ca.pem"),
        ssl_verify_cert=True
    )

    return connection