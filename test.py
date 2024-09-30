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
# Callback when a message is received
def on_message(client, userdata, msg):
    print(f"Message received from {msg.topic}: {msg.payload.decode()}")

    def handle_request_message(request_payload, topic_base, core=True):
        try:
            # Determine the data file (core or non-core)
            if core:
                data_file = "d2meshdata.json"
            else:
                data_file = "pisat.json"
                tag = topic_base.split("/")[-1]  # Fetch tag for non-core topics (device ID)

            # Load the data from the respective file
            with open(data_file, "r") as f:
                data = json.load(f)

            # For non-core topics, fetch the data for the specific tag (device)
            if not core:
                act_value_data = data.get(tag, {})
            else:
                act_value_data = data.get("act_value", {})

            response_data = {}
            # Search for each requested variable in the data
            for variable in request_payload:
                if variable in act_value_data:
                    response_data[variable] = act_value_data[variable]
                else:
                    print(
                        f"Variable '{variable}' not found in the data for tag '{tag}'." if not core else f"Variable '{variable}' not found in the core data.")

            if response_data:
                # Publish the response to the response topic
                client.publish(f"{topic_base}/response", json.dumps(response_data))
                print(f"Published matching data to {topic_base}/response: {json.dumps(response_data, indent=4)}")
            else:
                print("No matching data found for the requested variables.")

        except json.JSONDecodeError:
            print("Error decoding the request payload.")
        except FileNotFoundError:
            print(f"Error: {data_file} not found.")

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