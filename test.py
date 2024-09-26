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

        # Also subscribe to lightpost topics for each tag
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
            print("Published act_value data on startup:")

        except FileNotFoundError:
            print("Error: d2meshdata.json file not found.")
        except json.JSONDecodeError:
            print("Error: Invalid JSON format in act_value data.")
    else:
        print(f"Failed to connect, return code {rc}")


# Callback when a message is received
def on_message(client, userdata, msg):
    print(f"Message received from {msg.topic}: {msg.payload.decode()}")

    # Automatically copy the message from config topic to the response topic and update act_value data
    if msg.topic == "d2mesh/gate2DB48EC0/config":
        config_payload = json.loads(msg.payload.decode())

        # Load current act_value data from the file
        with open("d2meshdata.json", "r") as f:
            act_value_data = json.load(f)

        # Create a new dictionary for act_value instead of using the 'payloads' key
        act_value = {}

        # Update the act_value data with the new values from the config message
        for key, value in config_payload.items():
            act_value[key] = value

        # Save the updated act_value data back to the file
        with open("d2meshdata.json", "w") as f:
            json.dump({"act_value": act_value}, f, indent=4)

        # Print the updated act_value data
        print(f"Updated act_value data: {json.dumps(act_value, indent=4)}")

        # Publish the updated act_value data to the act_value topic
        act_value_topic = "d2mesh/gate2DB48EC0/act_value"
        client.publish(act_value_topic, json.dumps(act_value))
        print(f"Published updated act_value data to {act_value_topic}")

        # Publish the config message to the response topic
        client.publish("d2mesh/gate2DB48EC0/response", msg.payload)
        print("Copied config message to response topic and updated act_value")

    # Handle request message and extract variable names from it
    elif msg.topic == "d2mesh/gate2DB48EC0/request":
        try:
            request_payload = json.loads(msg.payload.decode())

            # Expecting the payload to be a list of variables (e.g., ["Timestamp", "Longitude"])
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
                    client.publish("d2mesh/gate2DB48EC0/response", json.dumps(response_data))
                    print(f"Published matching data to response topic: {json.dumps(response_data, indent=4)}")
                else:
                    print("No matching data found for the requested variables.")
            else:
                print("Invalid request format. Expected a list of variables.")

        except json.JSONDecodeError:
            print("Error decoding the request payload.")

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

    payload = input("Enter the message payload (JSON format): ").strip()
    try:
        json_payload = json.loads(payload)
        client.publish(request_topic, json.dumps(json_payload))
        print(f"Published to {request_topic}: {json.dumps(json_payload, indent=4)}")
    except json.JSONDecodeError:
        print("Invalid JSON format.")

# Function to toggle timed publishing on/off
def toggle_timed_publishing():
    global timed_publishing
    if not timed_publishing:
        print("Timed publishing is now ON.")
        timed_publishing = True
        threading.Thread(target=timed_publish, args=(client,), daemon=True).start()  # Start timed publishing in a thread
    else:
        print("Timed publishing is now OFF.")
        timed_publishing = False

# Function to handle timed publishing to act_value topics
def timed_publish(client):
    global timed_publishing
    print("Timed publishing started.")
    while timed_publishing:
        for topic in act_value_payload.keys():
            client.publish(f"d2mesh/gate2DB48EC0/act_value/{topic}", json.dumps(act_value_payload[topic]))
            print(f"Published timed act_value data to topic: d2mesh/gate2DB48EC0/act_value/{topic}")
            time.sleep(5)  # Adjust the interval as needed
    print("Timed publishing stopped.")

# Clear the console screen
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# Show options menu
def show_options_menu():
    print("\nOptions:")
    print("1. Publish to core config topic")
    print("2. Publish to core request topic")
    print("3. Publish to non-core config topic")
    print("4. Publish to non-core request topic")
    print("5. Toggle timed publishing")
    print("6. Exit")

# Main function to start the MQTT client
def main():
    global client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker, port, 60)

    # Start the client loop in a separate thread
    client.loop_start()

    try:
        manual_publish(client)
    finally:
        client.loop_stop()
        client.disconnect()
        print("MQTT client disconnected.")

if __name__ == "__main__":
    main()
