import paho.mqtt.client as mqtt
import json
import time
import threading
import os  # For clearing the screen

# Define the MQTT broker details
broker = 'localhost'
port = 1883

# Global flags for stopping the script and timed publishing
running = True
timed_publishing = False
publish_interval = 60  # Default interval (in seconds) for timed publishing

# Load the payload data from the file (pisat.json for act_value and d2meshdata.json for act_value)
try:
    with open("pisat.json", "r") as file:
        act_value_payload = json.load(file)

    with open("d2meshdata.json", "r") as file:
        initial_payload = json.load(file)
except FileNotFoundError as e:
    print(f"Error: Could not find the required JSON files: {e}")
    exit(1)

# Load tags from the generated_topics.txt file
try:
    with open("generated_topics.txt", "r") as file:
        tags = [line.strip() for line in file.readlines() if line.strip()]
except FileNotFoundError as e:
    print(f"Error: Could not find 'generated_topics.txt' file: {e}")
    exit(1)

# Load the JSON payloads from the file
try:
    with open("badpisat.json", "r") as file:
        data = json.load(file)
        payloads = data.get("payloads", [])
except (json.JSONDecodeError, FileNotFoundError) as e:
    print(f"Error loading JSON file: {e}")
    exit(1)

# Callback when the client receives a CONNACK response from the server
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Successfully connected to the broker.")

        # Subscribe to core topics (config, request, response)
        client.subscribe("d2mesh/gate2DB48EC0/config")
        client.subscribe("d2mesh/gate2DB48EC0/response")
        client.subscribe("d2mesh/gate2DB48EC0/request")

        # Subscribe to non-core (lightpost) topics for each tag
        for tag in tags:
            config_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/config"
            response_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/response"
            request_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/request"
            client.subscribe(config_topic)
            client.subscribe(response_topic)
            client.subscribe(request_topic)

        print("Subscribed to core topics and lightpost topics for each tag.")

        try:
            with open("d2meshdata.json", "r") as f:
                act_value_data = json.load(f)

            # Publish only the inner act_value data to the response topic
            client.publish("d2mesh/gate2DB48EC0/act_value", json.dumps(act_value_data.get("act_value", {})))
            print("Published act_value data on startup")

        except FileNotFoundError:
            print("Error: d2meshdata.json file not found.")
        except json.JSONDecodeError:
            print("Error: Invalid JSON format in act_value data.")
    else:
        print(f"Failed to connect, return code {rc}")

# Callback when a message is received
def on_message(client, userdata, msg):
    print(f"Message received from {msg.topic}: {msg.payload.decode()}")

    def handle_request_message(request_payload, topic_base):
        try:
            # Determine if the topic is a core topic (e.g., "d2mesh/gate2DB48EC0")
            if "lightpost" in topic_base:
                # Handling for non-core topics
                tag = topic_base.split("/")[-1]  # Extract tag (e.g., D202E7DF0000)
                with open("pisat.json", "r") as f:
                    non_core_data = json.load(f)

                act_value_data = non_core_data.get(tag, {})  # Get data for the specific tag

                response_data = {}
                for variable in request_payload:
                    if variable in act_value_data:
                        response_data[variable] = act_value_data[variable]
                    else:
                        print(f"Variable '{variable}' not found in data for tag '{tag}'.")

                if response_data:
                    client.publish(f"{topic_base}/response", json.dumps(response_data))
                    print(f"Published matching data to {topic_base}/response: {json.dumps(response_data, indent=4)}")
                else:
                    print("No matching data found for the requested variables.")
            else:
                # Load data from d2meshdata.json for core requests
                with open("d2meshdata.json", "r") as f:
                    core_data = json.load(f)
                act_value_data = core_data.get("act_value", {})  # Get act_value data

                # Prepare the response data based on the requested payload
                response_data = {}
                for variable in request_payload:
                    if variable in act_value_data:
                        response_data[variable] = act_value_data[variable]
                    else:
                        print(f"Variable '{variable}' not found in core data.")

                if response_data:
                    # Publish the response to the response topic
                    client.publish(f"{topic_base}/response", json.dumps(response_data))
                    print(f"Published matching data to {topic_base}/response: {json.dumps(response_data, indent=4)}")
                else:
                    print("No matching data found for the requested variables.")



        except json.JSONDecodeError:
            print("Error decoding the request payload.")
        except FileNotFoundError:
            print("Error: JSON file not found.")

    # Check if the topic is for a request and handle accordingly
    if "request" in msg.topic:
        request_payload = json.loads(msg.payload.decode())
        handle_request_message(request_payload, msg.topic)

    # Function to handle config messages
    def handle_config_message(config_payload, topic_base):
        try:
            if "lightpost" in topic_base:  # Non-core (lightpost) topics update pisat.json
                file_path = "pisat.json"
            else:  # Core topics update d2meshdata.json
                file_path = "d2meshdata.json"

            # Load current data from the appropriate file
            with open(file_path, "r") as f:
                data = json.load(f)

            # Determine if it's core or non-core, and update the respective "act_value"
            if "lightpost" in topic_base:  # Non-core topics in pisat.json
                tag = msg.topic.split("/")[3]
                act_value = data.get(tag, {})
                act_value.update(config_payload)  # Update specific fields
                data[tag] = act_value
            else:  # Core topics in d2meshdata.json
                act_value = data.get("act_value", {})
                act_value.update(config_payload)  # Update specific fields
                data["act_value"] = act_value

            # Save the updated data back to the respective file
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)

            # Print the updated data
            print(f"Updated data in {file_path}: {json.dumps(data, indent=4)}")

            # Publish the updated act_value data
            act_value_topic = f"{topic_base}/act_value"
            client.publish(act_value_topic, json.dumps(act_value))
            print(f"Published updated data to {act_value_topic}")

            # Publish the config message to the response topic
            client.publish(f"{topic_base}/response", json.dumps(config_payload))
            print(f"Copied config message to {topic_base}/response and updated act_value")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error: {e}")

    # Handle config or request messages based on the topic
    if "config" in msg.topic:
        config_payload = json.loads(msg.payload.decode())

        if "lightpost" in msg.topic:  # Non-core (lightpost) topics
            tag = msg.topic.split("/")[3]  # Extract tag
            topic_base = f"d2mesh/gate2DB48EC0/lightpost/{tag}"
            handle_config_message(config_payload, topic_base)
        else:  # Core topics
            topic_base = "d2mesh/gate2DB48EC0"
            handle_config_message(config_payload, topic_base)

    elif "request" in msg.topic:
        request_payload = json.loads(msg.payload.decode())

        if "lightpost" in msg.topic:  # Non-core (lightpost) topics
            tag = msg.topic.split("/")[3]  # Extract tag
            topic_base = f"d2mesh/gate2DB48EC0/lightpost/{tag}"
            handle_request_message(request_payload, topic_base)
        else:  # Core topics
            topic_base = "d2mesh/gate2DB48EC0"
            handle_request_message(request_payload, topic_base)

# Function to manually publish to core config or request topics
def manual_publish(client):
    global running  # Declare the global variable at the start of the function
    while running:
        clear_screen()
        show_options_menu()

        option = input("Choose an option (1, 2, 3, or 4): ").strip()

        if option == "1":
            publish_to_config(client, core=True)

        elif option == "2":
            publish_to_request(client, core=True)

        elif option == "3":
            publish_to_config(client, core=False)

        elif option == "4":
            publish_to_request(client, core=False)

        elif option == "5":
            running = False
            break

        else:
            print("Invalid option.")

# Function to publish a manually entered message to config topic
def publish_to_config(client, core=True):
    if core:
        config_topic = "d2mesh/gate2DB48EC0/config"
    else:
        print("\nAvailable tags:")
        for index, tag in enumerate(tags, 1):
            print(f"{index}. {tag}")
        tag_choice = input("Enter the number of the tag you want to publish to: ")
        try:
            tag_index = int(tag_choice) - 1
            if 0 <= tag_index < len(tags):
                config_topic = f"d2mesh/gate2DB48EC0/lightpost/{tags[tag_index]}/config"
            else:
                print("Invalid tag choice.")
                return
        except ValueError:
            print("Invalid input. Please enter a number.")
            return

    payload = input("Enter the JSON payload: ")
    try:
        json_payload = json.loads(payload)
        client.publish(config_topic, json.dumps(json_payload))
        print(f"Published to {config_topic}: {json_payload}")
    except json.JSONDecodeError:
        print("Invalid JSON format. Please try again.")

# Function to publish a manually entered message to request topic
def publish_to_request(client, core=True):
    if core:
        request_topic = "d2mesh/gate2DB48EC0/request"
    else:
        print("\nAvailable tags:")
        for index, tag in enumerate(tags, 1):
            print(f"{index}. {tag}")
        tag_choice = input("Enter the number of the tag you want to publish to: ")
        try:
            tag_index = int(tag_choice) - 1
            if 0 <= tag_index < len(tags):
                request_topic = f"d2mesh/gate2DB48EC0/lightpost/{tags[tag_index]}/request"
            else:
                print("Invalid tag choice.")
                return
        except ValueError:
            print("Invalid input. Please enter a number.")
            return

    payload = input("Enter the JSON payload: ")
    try:
        json_payload = json.loads(payload)
        client.publish(request_topic, json.dumps(json_payload))
        print(f"Published to {request_topic}: {json_payload}")
    except json.JSONDecodeError:
        print("Invalid JSON format. Please try again.")

# Function to clear the screen
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# Function to show options menu
def show_options_menu():
    print("\nOptions Menu:")
    print("1. Publish to Core Config Topic")
    print("2. Publish to Core Request Topic")
    print("3. Publish to Non-Core Config Topic")
    print("4. Publish to Non-Core Request Topic")
    print("5. Exit")

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to the MQTT broker
    try:
        client.connect(broker, port)
        print("Connected to the broker.")
    except Exception as e:
        print(f"Could not connect to broker: {e}")
        return

    # Start the loop in a separate thread for non-blocking execution
    client.loop_start()
    print("Started MQTT loop in background.")

    # Start the manual publishing function in the main thread
    manual_publish(client)

    # Stop the loop when exiting
    client.loop_stop()
    print("MQTT loop stopped.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program interrupted. Exiting.")
