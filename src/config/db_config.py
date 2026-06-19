import pyodbc
DB_SERVER = '.\\SQLEXPRESS'
DB_NAME = 'shipdb'

def get_connection():
    try:
        connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};DATABASE={DB_NAME};Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;'
        conn = pyodbc.connect(connection_string)
        return conn
    except pyodbc.Error as e:
        print(f'LỖI KẾT NỐI CSDL: {e}')
        try:
            connection_string = f'DRIVER={{SQL Server}};SERVER={DB_SERVER};DATABASE={DB_NAME};Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;'
            conn = pyodbc.connect(connection_string)
            return conn
        except pyodbc.Error as e2:
            print(f'LỖI FALLBACK KẾT NỐI CSDL: {e2}')
            return None
