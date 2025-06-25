import os
import json
import psycopg2
import re
import pandas as pd
from pathlib import Path
from openai import OpenAI
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set.")
client = OpenAI(api_key=API_KEY)
MODEL_NAME = "gpt-4o-mini"

# Database connection
conn = psycopg2.connect(
    dbname="inspiciodb",
    user="postgres",
    password="Yankayee123",
    host="localhost"
)
cursor = conn.cursor()

BASE_DIR = os.path.join(os.getcwd(),".data", "webvoyager-nnetnav-openweb-3")

def ensure_description_column() -> None:
    cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='files' AND column_name='description'
    """)
    
    if not cursor.fetchone():
        logging.info("Adding description column to files table...")
        cursor.execute("ALTER TABLE files ADD COLUMN description VARCHAR(255)")
        cursor.execute("CREATE INDEX idx_files_description ON files(description)")
        conn.commit()
        logging.info("Column added successfully")

def generate_label(log_content: str) -> str:
    try:
        system_prompt = """You are an expert summarizer. Generate a concise 2-3 word label summarizing the core task of the web navigation log. Focus on the main goal or subject. Output only the label, without any extra text like "Label:".
            Examples:
            Log: "Navigating to Amazon.com to search for headphones"
            Label: Headphone Shopping
            
            Log: "Looking up weather forecast for New York"
            Label: NY Weather Forecast
            
            Log: "Researching information about climate change"
            Label: Climate Research"""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate a 2-3 word description for this web navigation task log:\n\n{log_content}"},
            ],
            temperature=0.5,
            max_tokens=10,
            n=1,
            stop=None,
        )
        description = response.choices[0].message.content
        if description is not None:
            description = description.strip().strip('"')
            description = re.sub(r'^["\']|["\']$', '', description)
            return description
        return "Unknown Task"
    
    except Exception as e:
        logging.error(f"Error generating task description: {e}")
        return "Unknown Task"

def update_task_descriptions() -> None:
    ensure_description_column()
    
    cursor.execute("""
        SELECT DISTINCT regexp_replace(filepath, '/[^/]*$', '') as folder_path
        FROM files 
        WHERE filepath LIKE '%experiment.log'
    """)
    
    experiment_folders = cursor.fetchall()
    logging.info(f"Found {len(experiment_folders)} experiment folders in database")
    
    for (folder_path,) in experiment_folders:
        logging.info(f"\nProcessing folder: {folder_path}")
        
        log_file_path = os.path.join(BASE_DIR, folder_path.lstrip('/'), "experiment.log")
        
        logging.info(f"Looking for log file at: {log_file_path}")
        
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read(5000)  
   
            task_description = generate_label(log_content)
            logging.info(f"Generated task description: {task_description}")
            
            cursor.execute("""
                UPDATE files 
                SET description = %s 
                WHERE filepath LIKE %s
            """, (task_description, f"{folder_path}/%"))
            
            updated_rows = cursor.rowcount
            logging.info(f"Updated {updated_rows} files with task description: {task_description}")
            
        except FileNotFoundError:
            logging.error(f"Could not find experiment.log file at {log_file_path}")
    
            summary_path = os.path.join(BASE_DIR, "nnetnav_openweb_3", "summary_df.csv")
            logging.info(f"Trying to find summary data at: {summary_path}")
            
            if os.path.exists(summary_path):
                try:
                    df = pd.read_csv(summary_path)
                    folder_name = folder_path.split('/')[-1]
                    
                    matching_rows = df[df['folder'].str.contains(folder_name, na=False)]
                    
                    if not matching_rows.empty and 'task' in matching_rows.columns:
                        task = matching_rows.iloc[0]['task']
                        logging.info(f"Using task from summary_df: {task}")
                        
                        cursor.execute("""
                            UPDATE files 
                            SET description = %s 
                            WHERE filepath LIKE %s
                        """, (task, f"{folder_path}/%"))
                        
                        updated_rows = cursor.rowcount
                        logging.info(f"Updated {updated_rows} files with task description from summary_df")
                except Exception as e:
                    logging.error(f"Error using summary_df: {e}")
        
        except Exception as e:
            logging.error(f"Error processing folder {folder_path}: {e}")
    
    conn.commit()
    logging.info("All task descriptions updated successfully!")

if __name__ == "__main__":
    try:
        update_task_descriptions()
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        cursor.close()
        conn.close() 