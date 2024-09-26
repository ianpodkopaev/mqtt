import json

# Load the JSON file with base_tag, start, and end
json_file = "tags.json"
try:
    with open(json_file, 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"Error: The file {json_file} was not found.")
    exit(1)

# Extract base tag and range from the JSON
base_tag = data["base_tag"]
start_hex = int(data["start"], 16)
end_hex = int(data["end"], 16)

# Generate the list of topics
topics = []
for i in range(start_hex, end_hex + 1):
    hex_suffix = f"{i:04X}"  # Convert to uppercase hex, 4 digits with padding
    topics.append(f"{base_tag}{hex_suffix}")

# Save the generated topics to a file
output_file = "generated_topics.txt"
with open(output_file, 'w') as f:
    for topic in topics:
        f.write(f"{topic}\n")

print(f"Generated {len(topics)} topics. Saved to {output_file}")
