import os
import json
import hashlib
import psycopg2
import mimetypes
from datetime import datetime

conn = psycopg2.connect(
    dbname="inspiciodb",
    user="postgres",
    password="Yankayee123", 
    host="localhost"
)
cursor = conn.cursor()

# Base directory where files were extracted
base_dir = ".data"  # Change this if you extracted to a different location

# Function to calculate file hash (SHA-256)
def calculate_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash in chunks for large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# Function to extract metadata from file (customize as needed)
def extract_metadata(file_path, file_type):
    metadata = {
        "extracted_date": datetime.now().isoformat(),
        "source": "nnetnav_openweb"
    }
    
    # Add specific metadata based on file type
    if file_type == "image/png":
        # For PNG files, you might want to add dimensions, etc.
        metadata["image_type"] = "screenshot"
    elif file_type == "application/gzip":
        # For tar.gz files
        metadata["archive_type"] = "tar.gz"
    elif file_type == "text/plain":
        # For log files
        metadata["log_type"] = "web_navigation"
        
    return json.dumps(metadata)

# Extract and import files from tar.gz archives
def extract_and_import():
    # First, extract the tar.gz files if not already done
    import tarfile
    
    tar_files = [
        os.path.join(base_dir, "nnetnav_openweb_1.tar.gz"),
        os.path.join(base_dir, "nnetnav_openweb_2.tar.gz"),
        os.path.join(base_dir, "nnetnav_openweb_3.tar.gz")
    ]
    
    extract_dir = os.path.join(base_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)
    
    for tar_file in tar_files:
        if os.path.exists(tar_file):
            print(f"Extracting {tar_file}...")
            with tarfile.open(tar_file) as tar:
                tar.extractall(path=extract_dir)
    
    # Now walk through the extracted directory and import files
    for root, dirs, files in os.walk(extract_dir):
        for file in files:
            if file.endswith(('.png', '.tar.gz', '.log')):
                full_path = os.path.join(root, file)
                # Calculate relative path to maintain structure
                rel_path = os.path.relpath(full_path, extract_dir)
                
                # Get file information
                file_size = os.path.getsize(full_path)
                file_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
                file_hash = calculate_hash(full_path)
                
                # Extract metadata
                metadata = extract_metadata(full_path, file_type)
                
                # Check if file already exists in database
                cursor.execute(
                    "SELECT id FROM files WHERE hash = %s", (file_hash,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    print(f"File already exists in database: {rel_path}")
                    continue
                
                # Insert into database
                cursor.execute(
                    """
                    INSERT INTO files 
                    (filename, filepath, filetype, filesize, hash, metadata) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (file, rel_path, file_type, file_size, file_hash, metadata)
                )
                
                print(f"Imported: {rel_path}")
    
    # Commit changes
    conn.commit()
    print("Import completed successfully!")

def create_indexes():
    print("Creating indexes for performance optimization...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_files_hash ON files(hash)",
        "CREATE INDEX IF NOT EXISTS idx_files_filepath ON files(filepath)",
        "CREATE INDEX IF NOT EXISTS idx_files_filetype ON files(filetype)",
        "CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename)",
        "CREATE INDEX IF NOT EXISTS idx_files_metadata ON files USING GIN (metadata)",
        "CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at)"
    ]
    
    for index_sql in indexes:
        try:
            cursor.execute(index_sql)
            print(f"Created index: {index_sql}")
        except Exception as e:
            print(f"Error creating index: {e}")
    
    conn.commit()
    print("Index creation completed")

if __name__ == "__main__":
    try:
        extract_and_import()
        create_indexes()
    except Exception as e:
        print(f"Error during import: {e}")
    finally:
        cursor.close()
        conn.close() 