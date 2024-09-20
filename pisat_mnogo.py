import paho.mqtt.client as mqtt
import json
import time

# Define the MQTT broker details
broker = 'localhost'
port = 1883


# Callback when the client receives a CONNACK response from the server
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")


# Callback when a PUBLISH message is received from the server
def on_message(client, userdata, msg):
    print(f"Message received from topic {msg.topic}: {msg.payload.decode()}")


# Create a new MQTT client instance
client = mqtt.Client()

# Assign event callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect to the MQTT broker
client.connect(broker, port, 60)

# Load tags from the generated_topics.txt file
try:
    with open("generated_topics.txt", "r") as file:
        tags = [line.strip() for line in file.readlines() if line.strip()]
except FileNotFoundError as e:
    print(f"Error: Could not find 'generated_topics.txt' file: {e}")
    exit(1)

# Load the JSON payloads from the file
try:
    with open("pisat.json", "r") as file:
        data = json.load(file)
        payloads = data.get("payloads", [])
except (json.JSONDecodeError, FileNotFoundError) as e:
    print(f"Error loading JSON file: {e}")
    exit(1)

# Present options for publishing
print("\nChoose an option:")
print("1. Publish to all topics")
print("2. Choose one topic")
print("3. Enter a range of topics (e.g., 'from-to')")
print("4. Publish to specific tags (e.g., 'tag1,tag2,...')")

option = input("Enter your choice (1, 2, 3, or 4): ").strip()


# Function to subscribe to and publish to specific tags
def subscribe_and_publish_to_tags(selected_tags):
    # Subscribe to selected topics
    for tag in selected_tags:
        act_value_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/act_value"
        client.subscribe(act_value_topic)
        print(f"Subscribed to: {act_value_topic}")

    # Publish to selected topics
    for payload in payloads:
        cleaned_payload = {key: value for key, value in payload.items() if value is not None}
        for tag in selected_tags:
            act_value_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/act_value"
            client.publish(act_value_topic, json.dumps(cleaned_payload))
            print(f"Published to topic: {act_value_topic}")
            print(f"Payload: {json.dumps(cleaned_payload, indent=4)}")
        time.sleep(1)


# Handle the user's choice
if option == "1":
    print("Subscribing and publishing to all topics...")
    subscribe_and_publish_to_tags(tags)

elif option == "2":
    print("\nAvailable tags:")
    for index, tag in enumerate(tags, 1):
        print(f"{index}. {tag}")

    tag_choice = input("Enter the number of the tag to publish to: ").strip()
    try:
        tag_index = int(tag_choice) - 1
        if tag_index < 0 or tag_index >= len(tags):
            raise ValueError("Invalid choice")
        selected_tag = [tags[tag_index]]
        subscribe_and_publish_to_tags(selected_tag)
    except ValueError as e:
        print(f"Error: {e}")
        exit(1)

elif option == "3":
    print(f"\nAvailable tags range from: {tags[0]} to {tags[-1]}")
    range_input = input("Enter the tag range (e.g., 'D202E7DF0000-D202E7DF00FF'): ").strip()

    try:
        start_tag, end_tag = range_input.split('-')
        # Filter tags based on the provided range
        selected_tags = [tag for tag in tags if start_tag <= tag <= end_tag]
        if not selected_tags:
            print("No tags found in the specified range.")
        else:
            print(f"Subscribing and publishing to tags from {start_tag} to {end_tag}")
            subscribe_and_publish_to_tags(selected_tags)
    except ValueError:
        print("Invalid range input.")
        exit(1)

elif option == "4":
    print("\nAvailable tags:")
    for index, tag in enumerate(tags, 1):
        print(f"{index}. {tag}")

    tags_input = input("Enter the tags to publish to (comma-separated, e.g., 'D202E7DF0001,D202E7DF0002'): ").strip()
    selected_tags = [tag.strip() for tag in tags_input.split(',') if tag.strip() in tags]
    if not selected_tags:
        print("No valid tags found in the input.")
    else:
        print(f"Subscribing and publishing to selected tags: {', '.join(selected_tags)}")
        subscribe_and_publish_to_tags(selected_tags)

else:
    print("Invalid option selected.")
    exit(1)

# Blocking loop to process network traffic, dispatch callbacks, and handle reconnecting
client.loop_start()

# Run for a few seconds to allow messages to be processed
time.sleep(5)

# Stop the loop and disconnect
client.loop_stop()
client.disconnect()
