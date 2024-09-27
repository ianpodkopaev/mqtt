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

    # Parse payload as JSON
    try:
        config_payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from {msg.topic}")
        return

    # Split topic to determine base and tag (if any)
    topic_parts = msg.topic.split('/')
    topic_base = '/'.join(topic_parts[:-1])  # Base topic without the last part
    tag = topic_parts[3] if "lightpost" in topic_parts else None  # Get the tag if it's a non-core topic

    # Function to handle config messages
    def handle_config_message(config_payload, topic_base, tag=None):
        try:
            if tag:  # Non-core topics (lightpost)
                # Load pisat.json for non-core topics
                with open("pisat.json", "r") as f:
                    pisat_data = json.load(f)

                # Check if the tag exists, if not initialize it
                if tag not in pisat_data:
                    pisat_data[tag] = {}  # Initialize empty data for this tag

                # Get the existing data for this tag
                tag_data = pisat_data.get(tag, {})

                # Update only existing keys for this tag's payload
                for key, value in config_payload.items():
                    if key in tag_data:
                        tag_data[key] = value  # Update the existing key
                    else:
                        print(f"Warning: Key '{key}' does not exist in the payload for tag '{tag}'. Ignoring it.")

                # Save the updated data back to pisat.json for this tag
                pisat_data[tag] = tag_data
                with open("pisat.json", "w") as f:
                    json.dump(pisat_data, f, indent=4)

                # Print the updated data for this tag
                print(f"Updated data for tag '{tag}': {json.dumps(tag_data, indent=4)}")

                # Publish the updated data to the act_value topic for this tag
                act_value_topic = f"{topic_base}/act_value"
                client.publish(act_value_topic, json.dumps(tag_data))
                print(f"Published updated data to {act_value_topic}")

                # Publish the config message to the response topic for this tag
                client.publish(f"{topic_base}/response", json.dumps(config_payload))
                print(f"Copied config message to {topic_base}/response and updated act_value for tag '{tag}'")

            else:  # Core topics
                # Use d2meshdata.json for core topics
                with open("d2meshdata.json", "r") as f:
                    act_value_data = json.load(f)

                # Get the existing act_value data
                act_value = act_value_data.get("act_value", {})

                # Update only existing keys for core topics
                for key, value in config_payload.items():
                    if key in act_value:
                        act_value[key] = value  # Update the existing key
                    else:
                        print(f"Warning: Key '{key}' does not exist in act_value. Ignoring it.")

                # Save the updated act_value data back to the file
                with open("d2meshdata.json", "w") as f:
                    json.dump({"act_value": act_value}, f, indent=4)

                # Print the updated act_value data
                print(f"Updated act_value data: {json.dumps(act_value, indent=4)}")

                # Publish the updated act_value data to the act_value topic
                act_value_topic = f"{topic_base}/act_value"
                client.publish(act_value_topic, json.dumps(act_value))
                print(f"Published updated act_value data to {act_value_topic}")

                # Publish the config message to the response topic
                client.publish(f"{topic_base}/response", json.dumps(config_payload))
                print(f"Copied config message to {topic_base}/response and updated act_value")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error: {e}")

    # Call the config message handler with the parsed config payload and topic info
    handle_config_message(config_payload, topic_base, tag)


    # Function to handle request messages
    def handle_request_message(request_payload, topic_base):
        try:
            if isinstance(request_payload, list):
                response_data = {}

                # Load the updated act_value data
                with open("d2meshdata.json", "r") as f:
                    act_value_data = json.load(f)

                # Search for each requested variable in the act_value data
                for variable in request_payload:
                    if variable in act_value_data.get("act_value", {}):
                        response_data[variable] = act_value_data["act_value"][variable]

                if response_data:
                    # Publish the response to the response topic
                    client.publish(f"{topic_base}/response", json.dumps(response_data))
                    print(f"Published matching data to {topic_base}/response: {json.dumps(response_data, indent=4)}")
                else:
                    print("No matching data found for the requested variables.")
            else:
                print("Invalid request format. Expected a list of variables.")
        except json.JSONDecodeError:
            print("Error decoding the request payload.")

    # Determine if the message is from a core or non-core topic and handle accordingly
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
            toggle_timed_publishing()

        elif option == "6":
            set_publish_interval()

        elif option == "7":
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
        tag_choice = input("Enter the number of the tag to publish to: ").strip()

        try:
            tag_index = int(tag_choice) - 1
            if tag_index < 0 or tag_index >= len(tags):
                raise ValueError("Invalid choice")
            selected_tag = tags[tag_index]
            config_topic = f"d2mesh/gate2DB48EC0/lightpost/{selected_tag}/config"
        except ValueError as e:
            print(f"Error: {e}")
            return

    payload = input("Enter the message payload (JSON format): ").strip()
    try:
        json_payload = json.loads(payload)
        client.publish(config_topic, json.dumps(json_payload))
        print(f"Published to {config_topic}: {json.dumps(json_payload, indent=4)}")
    except json.JSONDecodeError:
        print("Invalid JSON format.")


# Function to publish to the request topic
def publish_to_request(client, core=True):
    if core:
        request_topic = "d2mesh/gate2DB48EC0/request"
    else:
        print("\nAvailable tags:")
        for index, tag in enumerate(tags, 1):
            print(f"{index}. {tag}")
        tag_choice = input("Enter the number of the tag to publish to: ").strip()

        try:
            tag_index = int(tag_choice) - 1
            if tag_index < 0 or tag_index >= len(tags):
                raise ValueError("Invalid choice")
            selected_tag = tags[tag_index]
            request_topic = f"d2mesh/gate2DB48EC0/lightpost/{selected_tag}/request"
        except ValueError as e:
            print(f"Error: {e}")
            return

    payload = input("Enter the requested variables (JSON list format): ").strip()
    try:
        json_payload = json.loads(payload)
        client.publish(request_topic, json.dumps(json_payload))
        print(f"Published to {request_topic}: {json.dumps(json_payload, indent=4)}")
    except json.JSONDecodeError:
        print("Invalid JSON format.")


# Function to clear the terminal screen
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


# Function to toggle timed publishing on or off
def toggle_timed_publishing():
    global timed_publishing
    timed_publishing = not timed_publishing
    print(f"Timed publishing {'enabled' if timed_publishing else 'disabled'}.")


# Function to set the time interval for publishing
def set_publish_interval():
    global publish_interval
    try:
        interval = int(input("Enter the time interval for timed publishing (in seconds): ").strip())
        if interval <= 0:
            print("Time interval must be a positive number.")
        else:
            publish_interval = interval
            print(f"Publish interval set to {publish_interval} seconds.")
    except ValueError:
        print("Invalid input. Please enter a positive integer.")


# Function to display options menu
def show_options_menu():
    print("\nOptions:")
    print("1. Publish to core config")
    print("2. Publish to core request")
    print("3. Publish to non-core config")
    print("4. Publish to non-core request")
    print("5. Toggle timed publishing")
    print("6. Set time interval for publishing")
    print("7. Quit")


# Function for timed publishing
def timed_publish(client):
    while running:
        if timed_publishing:
            for tag in tags:
                response_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/response"
                client.publish(response_topic, json.dumps(act_value_payload))
                print(f"Published act_value to {response_topic}")

            # If no tags are published, publish to the core topic
            if not tags:
                client.publish("d2mesh/gate2DB48EC0/response", json.dumps(act_value_payload))
                print("Published act_value to core response topic")

        time.sleep(publish_interval)


# Main function
def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(broker, port, 60)

    # Start the MQTT client loop in a separate thread
    threading.Thread(target=client.loop_forever, daemon=True).start()

    # Start the manual publish interface in the main thread
    manual_publish(client)


if __name__ == "__main__":
    try:
        threading.Thread(target=timed_publish, daemon=True).start()
        main()
    except KeyboardInterrupt:
        print("Program interrupted. Exiting.")
