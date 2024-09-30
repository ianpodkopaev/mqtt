# import paho.mqtt.client as mqtt
# import json
# import time
#
# # Define the MQTT broker details
# broker = 'localhost'
# port = 1883
#
# # Initialize global variables to store values from the config topic
# config_data = {
#     "Timestamp": None,
#     "Longitude": None,
#     "Latitude": None,
#     "LightPower": None,
#     "Interval": None,
#     "RFChannel": None
# }
#
# # Callback when the client receives a CONNACK response from the server
# def on_connect(client, userdata, flags, rc):
#     print(f"Connected with result code {rc}")
#     # Subscribe to both response and config topics
#     for tag in tags:
#         client.subscribe(f"d2mesh/gate2DB48EC0/lightpost/{tag}/response")
#         client.subscribe(f"d2mesh/gate2DB48EC0/lightpost/{tag}/config")
#
# # Callback when a PUBLISH message is received from the server
# def on_message(client, userdata, msg):
#     print(f"Message received from topic {msg.topic}: {msg.payload.decode()}")
#
# # Create a new MQTT client instance
# client = mqtt.Client()
#
# # Assign event callbacks
# client.on_connect = on_connect
# client.on_message = on_message
#
# # Connect to the MQTT broker
# client.connect(broker, port, 60)
#
# # Define tags
# tags = ["D202E7DF0814", "D202E7DF0815"]  # Add your tags here
#
# # Choose tag
# print("Select a tag:")
# for index, tag in enumerate(tags, 1):
#     print(f"{index}. {tag}")
#
# tag_choice = input("Enter the number of the tag to use: ")
#
# try:
#     tag_index = int(tag_choice) - 1
#     if tag_index < 0 or tag_index >= len(tags):
#         raise ValueError("Invalid choice")
#     tag = tags[tag_index]
# except ValueError as e:
#     print(f"Error: {e}")
#     exit(1)
#
# # Ask the user which fields to publish and their values
# fields_to_publish = input("Enter the fields to publish (e.g., Timestamp, Longitude, Latitude): ").split(',')
# payload = {}
#
# for field in fields_to_publish:
#     field = field.strip()
#     if field in config_data:
#         value = input(f"Enter value for {field}: ")
#         if field in ["Longitude", "Latitude"]:
#             try:
#                 value = float(value)  # Ensure longitude and latitude are floats
#             except ValueError:
#                 print(f"Invalid value for {field}. Must be a number.")
#                 continue
#         payload[field] = value
#     else:
#         print(f"Invalid field: {field}")
#
# # Publish the payload to the MQTT response topic
# response_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/response"
# client.publish(response_topic, json.dumps(payload))
# print(f"Published to topic: {response_topic}")
# print(f"Payload: {json.dumps(payload, indent=4)}")
#
# # Blocking loop to process network traffic, dispatch callbacks, and handle reconnecting
# client.loop_start()  # Use loop_start() to avoid blocking
#
# # Run for a few seconds to allow messages to be processed
# time.sleep(10)
#
# # Stop the loop and disconnect
# client.loop_stop()
# client.disconnect()

import paho.mqtt.client as mqtt
import json
import time

import paho.mqtt.client as mqtt
import json
import time
import threading
import os  # For clearing the screen

# Define the MQTT broker details
broker = 'localhost'  # Adjust if needed for your Docker network
port = 1883

# Global flag for stopping the script and timed publishing
running = True
timed_publishing = False  # Switch for toggling timed publishing


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
        # Subscribe to config and response topics for each tag
        for tag in tags:
            config_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/config"
            response_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/response"
            client.subscribe(config_topic)
            client.subscribe(response_topic)
        print("Successfully subscribed to all config and response topics.")
    else:
        print(f"Failed to connect, return code {rc}")


# Callback when a message is received from the config topic
def on_message(client, userdata, msg):
    print(f"Message received from {msg.topic}: {msg.payload.decode()}")

    # Automatically copy the message from config topic to the response topic
    for tag in tags:
        config_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/config"
        response_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/response"

        if msg.topic == config_topic:
            client.publish(response_topic, msg.payload)
            print(f"Copied config message to response topic: {response_topic}")


# Function to manually publish to config topic
def manual_publish(client):
    global running  # Declare the global variable at the start of the function
    while running:
        clear_screen()
        show_options_menu()

        option = input("Choose an option (1, 2, 3, or 4): ").strip()
        print()  # Add a blank line to ensure a clean separation after input

        if option == "1":
            publish_to_config(client)

        elif option == "2":
            toggle_timed_publishing()

        elif option == "3":
            running = False  # Update the global running flag
            break

        elif option == "4":
            publish_full_json_separate_messages(client)

        else:
            print("Invalid option.")


# Function to publish a manually entered message to a config topic
def publish_to_config(client):
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

        payload = input("Enter the message payload (JSON format): ").strip()
        try:
            json_payload = json.loads(payload)
            client.publish(config_topic, json.dumps(json_payload))
            print(f"Published to {config_topic}: {json.dumps(json_payload, indent=4)}")
        except json.JSONDecodeError:
            print("Invalid JSON format.")
    except ValueError as e:
        print(f"Error: {e}")


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


# Function to publish the entire JSON payload as separate messages
def publish_full_json_separate_messages(client):
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

        # Check if payloads is a list
        if isinstance(payloads, list):
            # Publish each payload (which should be a dictionary) in the list as a separate message
            for payload in payloads:
                if isinstance(payload, dict):  # Ensure each payload is a dictionary
                    message = json.dumps(payload)
                    client.publish(config_topic, message)
                    print(f"Published to {config_topic}: {message}")
                else:
                    print("Invalid payload format. Expected a dictionary.")
        else:
            print("Error: 'payloads' should be a list of JSON objects.")

    except ValueError as e:
        print(f"Error: {e}")


# Function to handle timed publishing every minute (adjustable)
def timed_publish(client):
    global timed_publishing
    print("Timed publishing started.")

    # Interval selection
    interval = 60  # Default to 1 minute
    custom_interval = input("Enter custom interval (in seconds): ").strip()
    try:
        interval = int(custom_interval)
    except ValueError:
        print("Invalid custom interval. Using default 60 seconds.")

    while timed_publishing:
        for tag in tags:  # Iterate through all tags
            act_value_topic = f"d2mesh/gate2DB48EC0/lightpost/{tag}/act_value"
            for payload in payloads:  # Iterate through the list of payloads
                if isinstance(payload, dict):  # Ensure it's a dictionary
                    message = json.dumps(payload)
                    client.publish(act_value_topic, message)
                    print(f"Published timed message to {act_value_topic}: {message}")

                # Check if timed publishing has been turned off
                if not timed_publishing:
                    print("Timed publishing has been stopped.")
                    return  # Exit the function if stopped

            time.sleep(interval)  # Sleep after publishing all payloads for the current tag


# Function to clear the screen
def clear_screen():
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For Linux and MacOS
        os.system('clear')


# Function to show the options menu
def show_options_menu():
    print("\nOptions:")
    print("1. Publish a message to config topic")
    print("2. Toggle timed publishing (on/off)")
    print("3. Quit")
    print("4. Publish full JSON as separate messages")


# Create a new MQTT client instance
client = mqtt.Client()

# Assign event callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect to the MQTT broker
client.connect(broker, port, 60)

# Run the client in a separate thread to handle messages
client.loop_start()

# Start the manual publishing thread
manual_thread = threading.Thread(target=manual_publish, args=(client,))
manual_thread.start()

# Keep the script running until the user chooses to quit
try:
    while running:
        time.sleep(1)
except KeyboardInterrupt:
    running = False

# Stop the client loop and disconnect
client.loop_stop()
client.disconnect()

manual_thread.join()
print("Script stopped.")