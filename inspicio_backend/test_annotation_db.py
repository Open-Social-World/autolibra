import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# Add the parent directory to the path to import the server module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server import save_annotation_to_db, get_db_connection

def test_annotation_db():
    """Test the annotation database functionality"""
    print("Testing annotation database functionality...")
    
    # Test data
    test_dataset = "sotopia"
    test_annotation_id = "test_annotation_001"
    test_instance_id = "test_instance_001"
    test_agent_id = "test_agent_001"
    test_annotator_id = "test_annotator_001"
    test_content = {
        "comment": {
            "comment_text": "This is a test comment",
            "selection_text": "Selected text for testing",
            "start_offset": 0,
            "end_offset": 10
        }
    }
    test_created_at = datetime.now()
    test_updated_at = datetime.now()
    test_start_time = datetime.now()
    test_end_time = datetime.now()
    test_confidence = 0.95
    test_metadata = {"test": True, "source": "test_script"}
    
    try:
        # Test saving annotation to database
        print(f"Testing save_annotation_to_db for dataset: {test_dataset}")
        save_annotation_to_db(
            dataset=test_dataset,
            annotation_id=test_annotation_id,
            instance_id=test_instance_id,
            agent_id=test_agent_id,
            annotator_id=test_annotator_id,
            content=test_content,
            created_at=test_created_at,
            updated_at=test_updated_at,
            start_time=test_start_time,
            end_time=test_end_time,
            confidence=test_confidence,
            metadata=test_metadata
        )
        print("✓ Annotation saved to database successfully")
        
        # Test retrieving annotation from database
        print("Testing annotation retrieval from database...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        table_name = f"{test_dataset}_annotations"
        cursor.execute(f"""
            SELECT annotation_id, instance_id, agent_id, annotator_id, content, metadata
            FROM {table_name} 
            WHERE annotation_id = %s
        """, (test_annotation_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            print("✓ Annotation retrieved from database successfully")
            print(f"  - Annotation ID: {result[0]}")
            print(f"  - Instance ID: {result[1]}")
            print(f"  - Agent ID: {result[2]}")
            print(f"  - Annotator ID: {result[3]}")
            print(f"  - Content: {result[4]}")
            print(f"  - Metadata: {result[5]}")
        else:
            print("✗ Failed to retrieve annotation from database")
            return False
        
        # Test unsupported dataset
        print("Testing unsupported dataset...")
        try:
            save_annotation_to_db(
                dataset="unsupported_dataset",
                annotation_id="test_annotation_002",
                instance_id=test_instance_id,
                agent_id=test_agent_id,
                annotator_id=test_annotator_id,
                content=test_content,
                created_at=test_created_at,
                updated_at=test_updated_at
            )
            print("✗ Should have failed for unsupported dataset")
            return False
        except Exception as e:
            if "Unsupported dataset" in str(e):
                print("✓ Correctly rejected unsupported dataset")
            else:
                print(f"✗ Unexpected error for unsupported dataset: {e}")
                return False
        
        print("All tests passed! ✓")
        return True
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_annotation_db()
    sys.exit(0 if success else 1) 