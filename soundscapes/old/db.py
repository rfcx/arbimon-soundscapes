import os
import mysql.connector

config = {
    'db_host': os.getenv('DB_HOST'),
    'db_user': os.getenv('DB_USER'),
    'db_password': os.getenv('DB_PASSWORD'),
    'db_name': os.getenv('DB_NAME'),
}

def connect():
    return mysql.connector.connect(
        host=config['db_host'],
        user=config['db_user'],
        password=config['db_password'], 
        database=config['db_name']
    )
