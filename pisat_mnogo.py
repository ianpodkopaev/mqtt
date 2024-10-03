import paho.mqtt.client as mqtt
import json
import time
import threading

# Define the MQTT broker details
broker = 'localhost'
port = 1883

# Global flags for stopping the script and timed publishing
running = True
timed_publishing = False
publish_interval = 60  # Default interval (in seconds) for timed publishing

# Load the payload data from pisat.json
try:
    with open("pisat.json", "r") as file:
        payloads = json.load(file)
except FileNotFoundError as e:
    print(f"Error: Could not find the pisat.json file: {e}")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON format in pisat.json: {e}")
    exit(1)

# Callback when the client receives a CONNACK response from the server
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Successfully connected to the broker.")
    else:
        print(f"Failed to connect, return code {rc}")

# Function for timed publishing
def publish_timed(client):
    while running and timed_publishing:
        publish_all_topics(client)
        time.sleep(publish_interval)

# Publish all topics from pisat.json
def publish_all_topics(client):
    for topic, payload in payloads.items():
        topic_full = f"d2mesh/gate2DB48EC0/lightpost/{topic}/act_value"
        client.publish(topic_full, json.dumps(payload))
        print(f"Published to {topic_full}: {payload}")

# Start timed publishing thread
def start_timed_publishing(client):
    global timed_publishing
    timed_publishing = True
    thread = threading.Thread(target=publish_timed, args=(client,))
    thread.start()

# Stop timed publishing
def stop_timed_publishing():
    global timed_publishing
    timed_publishing = False

# Set a custom timer interval for timed publishing
def set_publish_interval():
    global publish_interval
    try:
        interval = int(input("Enter the timer interval (in seconds): "))
        if interval > 0:
            publish_interval = interval
            print(f"Timer interval set to {publish_interval} seconds.")
        else:
            print("Please enter a positive integer.")
    except ValueError:
        print("Invalid input. Please enter a valid number.")

# Create an MQTT client instance and configure callbacks
client = mqtt.Client()
client.on_connect = on_connect

# Connect to the MQTT broker
client.connect(broker, port, 60)

# Main loop
try:
    client.loop_start()

    while running:
        print("\nOptions:")
        print("1. Publish all topics once")
        print("2. Start timed publishing")
        print(f"3. Set timer interval (currently {publish_interval} seconds)")
        print("4. Stop timed publishing")
        print("5. Exit")

        choice = input("Select an option: ")

        if choice == "1":
            publish_all_topics(client)
        elif choice == "2":
            start_timed_publishing(client)
        elif choice == "3":
            set_publish_interval()
        elif choice == "4":
            stop_timed_publishing()
        elif choice == "5":
            running = False
            stop_timed_publishing()
            client.loop_stop()
            print("Exiting the program.")
        else:
            print("Invalid option. Please try again.")

except KeyboardInterrupt:
    print("Interrupted by user. Exiting...")
    running = False
    client.loop_stop()
