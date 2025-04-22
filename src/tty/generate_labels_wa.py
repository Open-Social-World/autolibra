from openai import OpenAI
import json
import os
import logging
from pathlib import Path
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

# Initialize OpenAI client
client = OpenAI(api_key=API_KEY)

MODEL_NAME = "gpt-4o-mini" # Or another suitable OpenAI model like "gpt-3.5-turbo"
WEB_ARENA_DIR = Path(".data/webarena")
INSTANCES_DIR = WEB_ARENA_DIR / "instances"
OUTPUT_FILE = WEB_ARENA_DIR / "instance_labels.json"
# --- End Configuration ---

def generate_label(text: str) -> str | None:
    system_prompt = """You are an expert summarizer. Generate a concise 2-3 word label summarizing the core task of the user request. Focus on the main goal or subject. Output only the label, without any extra text like "Label:".

Examples:
User request: "What is the zip code of Yale University?"
Label: Yale Zip Code

User request: "Find the cheapest flight from SFO to LAX departing tomorrow."
Label: Cheap Flight SFO-LAX

User request: "Book a table for 2 at a Michelin-starred restaurant in Paris for next Friday evening."
Label: Paris Michelin Booking

User request: "What were the main points of the latest UN climate change report?"
Label: UN Climate Report"""

    user_prompt = f"""User request: "{text}"
Label:"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=10,
            n=1,
            stop=None,
        )
        label = response.choices[0].message.content.strip().strip('"')

        if 1 < len(label.split()) < 4:
            label = label.replace("Label:", "").strip()
            return label
        else:
            logging.warning(f"Generated label '{label}' has unexpected word count for text: '{text}'. Trying fallback.")
            short_label = " ".join(label.split()[:3])
            if 1 < len(short_label.split()) < 4:
                 return short_label
            else:
                 logging.warning(f"Fallback label '{short_label}' also has unexpected word count. Skipping.")
                 return None

    except Exception as e:
        logging.error(f"Error generating label for text '{text}': {e}")
        return None

def main():
    """Main function to generate labels for WebArena instances."""
    if not INSTANCES_DIR.is_dir():
        logging.error(f"Instances directory not found: {INSTANCES_DIR}")
        return

    instance_labels = {}

    instance_ids = [d.name for d in INSTANCES_DIR.iterdir() if d.is_dir()]
    logging.info(f"Found {len(instance_ids)} instances in {INSTANCES_DIR}")

    for instance_id in tqdm(instance_ids, desc="Generating Labels"):
        # Path to the directory that should contain the json file
        json_data_dir = INSTANCES_DIR / instance_id / "user" / "json_data"

        # Check if the directory exists
        if not json_data_dir.is_dir():
            logging.warning(f"Directory 'user/json_data' not found for instance {instance_id}. Skipping.")
            continue

        # Find the JSON file within the directory
        json_file = None
        try:
            json_files_in_dir = list(json_data_dir.glob('*.json')) # Find all .json files
            if len(json_files_in_dir) == 1:
                json_file = json_files_in_dir[0]
            elif len(json_files_in_dir) > 1:
                 logging.warning(f"Multiple JSON files found in {json_data_dir} for instance {instance_id}. Skipping.")
                 continue
            else: # No JSON files found
                 logging.warning(f"No JSON file found in {json_data_dir} for instance {instance_id}. Skipping.")
                 continue

        except Exception as e:
             logging.error(f"Error accessing directory {json_data_dir} for instance {instance_id}: {e}. Skipping.")
             continue


        # Proceed if we found a single JSON file
        if json_file and json_file.is_file():
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)

                request_text = data.get("text")
                if not request_text or not isinstance(request_text, str):
                    request_text = data.get("goal")
                    if not request_text or not isinstance(request_text, str):
                         logging.warning(f"Could not find 'text' or 'goal' field in {json_file} for instance {instance_id}. Content: {data}. Skipping.")
                         continue

                label = generate_label(request_text)
                if label:
                    instance_labels[instance_id] = label
                    logging.debug(f"Generated label for {instance_id}: {label}")
                else:
                     instance_labels[instance_id] = "Label Generation Failed"

            except json.JSONDecodeError:
                logging.error(f"Error decoding JSON from {json_file} for instance {instance_id}. Skipping.")
            except Exception as e:
                logging.error(f"An unexpected error occurred processing instance {instance_id} with file {json_file}: {e}")
        # else: # This case is handled by the checks above
            # logging.warning(f"Could not find a valid JSON file in {json_data_dir} for instance {instance_id}. Skipping.")


    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(instance_labels, f, indent=2)
        logging.info(f"Successfully generated labels for {len(instance_labels)} instances.")
        logging.info(f"Labels saved to {OUTPUT_FILE}")
    except IOError as e:
        logging.error(f"Error writing labels to {OUTPUT_FILE}: {e}")

if __name__ == "__main__":
    main()
