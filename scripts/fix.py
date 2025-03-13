import re
import json
import os

# File paths
input_file = os.path.expanduser("~/data/chsh_long_results.txt")
output_file = os.path.expanduser("~/data/chsh_long_results_formatted.txt")  # Avoid overwriting


# Function to clean and standardize JSON
def clean_json_like_content(content):
    cleaned_lines = []
    for line in content.splitlines():
        # Skip lines that don't look like JSON
        if not line.strip().startswith("{") and not line.strip().startswith("'timestamp'"):
            continue
        # Replace single quotes with double quotes for JSON compatibility
        line = re.sub(r"'", '"', line)
        # Remove `np.` type wrappers
        line = re.sub(r"np\.(int32|float64)\((.*?)\)", r"\2", line)
        # Fix trailing commas
        line = re.sub(r",\\s*}", "}", line)
        line = re.sub(r",\\s*]", "]", line)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


# Read the input file
with open(input_file, "r") as file:
    raw_content = file.read()

# Clean the content
cleaned_content = clean_json_like_content(raw_content)

# Process the cleaned content
entries = cleaned_content.split("}\n{")
formatted_entries = []
for i, entry in enumerate(entries):
    try:
        # Ensure entry is a valid JSON object
        entry = entry if entry.startswith("{") else f"{{{entry}}}"
        entry = entry if entry.endswith("}") else f"{entry}}}"
        json_entry = json.loads(entry)  # Parse JSON
        formatted_entries.append(json.dumps(json_entry, indent=4))  # Pretty-print JSON
    except json.JSONDecodeError as e:
        # Log invalid entries
        print(f"Error decoding entry {i}: {entry[:200]}...\nError: {e}")
        formatted_entries.append(f"INVALID ENTRY {i}:\n{entry}")

# Write the results to a new file
with open(output_file, "w") as file:
    file.write("\n---\n".join(formatted_entries))

print(f"Formatted content has been saved to {output_file}")
