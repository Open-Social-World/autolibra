import psycopg2

# Database connection
conn = psycopg2.connect(
    dbname="inspiciodb",
    user="postgres",
    password="Yankayee123",
    host="localhost"
)
cursor = conn.cursor()

# Update file paths in the database
try:
    # This will update all file paths to use the correct location
    cursor.execute("""
        UPDATE files
        SET filepath = REPLACE(filepath, 'extracted_data/', '.data/extracted/')
        WHERE filepath LIKE 'extracted_data/%'
    """)
    
    updated_rows = cursor.rowcount
    print(f"Updated {updated_rows} file paths in the database")
    
    # Commit the changes
    conn.commit()
    
except Exception as e:
    print(f"Error updating file paths: {e}")
    conn.rollback()
finally:
    cursor.close()
    conn.close() 