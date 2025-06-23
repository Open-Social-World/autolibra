import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import psycopg2
        print("✓ psycopg2 is installed")
    except ImportError:
        print("✗ psycopg2 is not installed. Please install it with: pip install psycopg2-binary")
        return False
    
    try:
        # Add the package directory to the Python path
        sys.path.append(str(Path(__file__).parent.parent.parent / "packages"))
        from osw_data.dataset import MultiAgentDataset
        print("✓ osw_data package is available")
    except ImportError as e:
        print(f"✗ osw_data package is not available: {e}")
        return False
    
    return True

def check_database_connection():
    """Check if database connection is working"""
    try:
        from unified_migration import DB_CONFIG
        import psycopg2
        
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        print("✓ Database connection successful")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("Please check your database configuration in the unified_migration.py file")
        return False

def check_data_paths():
    """Check if required data paths exist"""
    from unified_migration import DATASET_CONFIGS
    
    all_exist = True
    for dataset_name, config in DATASET_CONFIGS.items():
        print(f"\nChecking {dataset_name} data paths...")
        
        paths_to_check = [
            (config["dataset_path"], f"{dataset_name} dataset"),
            (config["annotation_path"], f"{dataset_name} annotations"),
            (config["metrics_file"], f"{dataset_name} metrics file")
        ]
        
        for path, description in paths_to_check:
            if path.exists():
                print(f"  ✓ {description} found at: {path}")
            else:
                print(f"  ✗ {description} not found at: {path}")
                all_exist = False
    
    return all_exist

def run_migration(dataset_name):
    """Run the migration for a specific dataset"""
    print(f"\n" + "="*60)
    print(f"RUNNING {dataset_name.upper()} MIGRATION")
    print("="*60)
    
    try:
        # Import and run the migration
        from unified_migration import UnifiedMigration
        
        migration = UnifiedMigration(dataset_name)
        migration.run_migration()
        
        print(f"\n✓ {dataset_name} migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n✗ {dataset_name} migration failed: {e}")
        return False

def main():
    """Main function to run migrations"""
    print("\n" + "="*60)
    print("UNIFIED MIGRATION SCRIPT")
    print("="*60)
    
    # Check dependencies
    print("\nChecking dependencies...")
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.")
        return
    
    # Check database connection
    print("\nChecking database connection...")
    if not check_database_connection():
        print("\nPlease fix database connection issues and try again.")
        return
    
    # Check data paths
    print("\nChecking data paths...")
    if not check_data_paths():
        print("\nSome data paths are missing. Migration may be incomplete.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return
    
    # Ask user which datasets to migrate
    print("\nWhich datasets would you like to migrate?")
    print("1. Sotopia only")
    print("2. WebArena only")
    print("3. Both Sotopia and WebArena")
    
    while True:
        choice = input("\nEnter your choice (1-3): ").strip()
        if choice in ["1", "2", "3"]:
            break
        print("Please enter 1, 2, or 3")
    
    datasets_to_migrate = []
    if choice == "1":
        datasets_to_migrate = ["sotopia"]
    elif choice == "2":
        datasets_to_migrate = ["webarena"]
    else:
        datasets_to_migrate = ["sotopia", "webarena"]
    
    # Run migrations
    success_count = 0
    for dataset_name in datasets_to_migrate:
        if run_migration(dataset_name):
            success_count += 1
    
    # Summary
    print(f"\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    print(f"Successfully migrated {success_count}/{len(datasets_to_migrate)} datasets")
    
    if success_count == len(datasets_to_migrate):
        print("All migrations completed successfully!")
    else:
        print("Some migrations failed. Please check the error messages above.")

if __name__ == "__main__":
    main() 