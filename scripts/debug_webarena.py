from pathlib import Path
import logging
from typing import Dict, Any
import json

from osw_eval_core.data import MultiAgentDataset

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trajectory-debug")

def debug_instance(dataset: MultiAgentDataset, instance_id: str):
    """Debug a specific instance's data loading"""
    logger.info(f"Debugging instance: {instance_id}")
    
    # 1. Check instance metadata
    try:
        metadata = dataset.get_instance_metadata(instance_id)
        logger.info(f"Found instance metadata: {metadata}")
        logger.info(f"Agents in metadata: {list(metadata.agents.keys())}")
    except Exception as e:
        logger.error(f"Error loading instance metadata: {e}")
        return
    
    # 2. Check each agent's trajectory
    for agent_id in metadata.agents:
        logger.info(f"\nChecking trajectory for agent: {agent_id}")
        try:
            trajectory = dataset.get_trajectory(instance_id, agent_id)
            logger.info(f"Trajectory object created: {trajectory}")
            logger.info(f"Number of points: {len(trajectory.points)}")
            
            # Check trajectory storage paths
            if hasattr(trajectory, 'media_storage'):
                logger.info(f"Storage path: {trajectory.media_storage.base_path}")
                if hasattr(trajectory.media_storage, 'h5_file'):
                    logger.info("H5 file exists")
            
            # Check first few points if they exist
            for i, point in enumerate(trajectory.points[:3]):
                logger.info(f"Point {i}: {point}")
                
        except Exception as e:
            logger.error(f"Error loading trajectory: {e}")

def check_data_files(dataset_path: Path):
    """Check the existence and structure of data files"""
    logger.info("\nChecking data files:")
    
    # Check basic directory structure
    logger.info(f"Dataset path exists: {dataset_path.exists()}")
    instances_path = dataset_path / "instances"
    logger.info(f"Instances directory exists: {instances_path.exists()}")
    
    if instances_path.exists():
        # Check a few instance directories
        instance_dirs = list(instances_path.glob("*"))
        logger.info(f"Found {len(instance_dirs)} instance directories")
        
        for instance_dir in instance_dirs[:3]:
            logger.info(f"\nChecking instance directory: {instance_dir}")
            
            # Check metadata file
            metadata_file = instance_dir / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    logger.info(f"Metadata contains: {list(metadata.keys())}")
                except Exception as e:
                    logger.error(f"Error reading metadata: {e}")
            else:
                logger.error("No metadata.json found")
            
            # Check for agent directories
            agent_dirs = list(instance_dir.glob("*"))
            logger.info(f"Found directories: {[d.name for d in agent_dirs]}")

def main():
    dataset_path = Path(".data/webarena")
    logger.info(f"Starting debug for dataset at: {dataset_path}")
    
    # Initialize dataset
    try:
        dataset = MultiAgentDataset(
            name="WebArena Interactions",
            base_path=dataset_path
        )
        logger.info("Dataset initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing dataset: {e}")
        return
    
    # Check data files
    check_data_files(dataset_path)
    
    # Get list of instances
    try:
        instances = dataset.list_instances()
        logger.info(f"\nFound {len(instances)} instances")
        
        # Debug specific instance
        if instances:
            test_instance = instances[100]  # The problematic instance
            debug_instance(dataset, test_instance)
    except Exception as e:
        logger.error(f"Error listing instances: {e}")

if __name__ == "__main__":
    main()