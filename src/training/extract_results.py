import json
import polars as pl


def convert_jsonl_to_table(file_path):
    # Read records into a list
    records = []
    with open(file_path, "r") as file:
        for line in file:
            if line.strip():  # Skip empty lines
                record = json.loads(line)
                records.append(record)

    # Convert to Polars DataFrame
    df = pl.DataFrame(records)

    # Reorder columns to group reasoning and scores together
    reasoning_columns = [col for col in df.columns if col.endswith("_reasoning")]
    score_columns = [col for col in df.columns if not col.endswith("_reasoning")]

    # Combine columns in desired order
    df = df.select(reasoning_columns + score_columns)

    return df


if __name__ == "__main__":
    # Replace 'your_file.jsonl' with your actual file path
    file_path = "llm_eval_results.jsonl"
    try:
        df = convert_jsonl_to_table(file_path)

        # Save to CSV
        df.write_csv("converted_table.csv")
        print("\nTable has been saved to 'converted_table.csv'")

    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format in file")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
