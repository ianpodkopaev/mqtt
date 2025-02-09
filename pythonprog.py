import paho.mqtt.client as mqtt
import json
import time
import threading
import os

# Define the MQTT broker details
broker = os.getenv('MQTT_BROKER', 'localhost')
port = int(os.getenv('MQTT_PORT', 1883))
publish_interval = int(os.getenv('PUBLISH_INTERVAL', 60))

# Global flags for stopping the script and timed publishing
running = True
timed_publishing = os.getenv('TIMED_PUBLISHING', 'True') == 'True'

# Load the payload data from the files
try:
    with open("/app/pisat.json", "r") as file:
        pisat_data = json.load(file)

    with open("/app/d2meshdata.json", "r") as file:
        d2mesh_data = json.load(file)
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

        # Publish act_value data on startup
        act_value_data = d2mesh_data.get("act_value", {})
        client.publish("d2mesh/gate2DB48EC0/act_value", json.dumps(act_value_data))
        print("Published act_value data on startup")
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
                act_value_data = pisat_data.get(tag, {})  # Get data for the specific tag

                response_data = {variable: act_value_data.get(variable) for variable in request_payload if variable in act_value_data}

                if response_data:
                    client.publish(f"{topic_base}/response", json.dumps(response_data))
                    print(f"Published matching data to {topic_base}/response: {json.dumps(response_data, indent=4)}")
                else:
                    print("No matching data found for the requested variables.")
            else:
                # Prepare the response data based on the requested payload
                act_value_data = d2mesh_data.get("act_value", {})
                response_data = {variable: act_value_data.get(variable) for variable in request_payload if variable in act_value_data}

                if response_data:
                    client.publish(f"{topic_base}/response", json.dumps(response_data))
                    print(f"Published matching data to {topic_base}/response: {json.dumps(response_data, indent=4)}")
                else:
                    print("No matching data found for the requested variables.")
        except json.JSONDecodeError:
            print("Error decoding the request payload.")

    # Check if the topic is for a request and handle accordingly
    if "request" in msg.topic:
        request_payload = json.loads(msg.payload.decode())
        handle_request_message(request_payload, msg.topic)

    # Function to handle config messages
    def handle_config_message(config_payload, topic_base):
        try:
            if "lightpost" in topic_base:  # Non-core (lightpost) topics update pisat.json
                file_path = "/app/pisat.json"
                tag = msg.topic.split("/")[3]
                act_value = pisat_data.get(tag, {})
                act_value.update(config_payload)  # Update specific fields
                pisat_data[tag] = act_value
            else:  # Core topics update d2meshdata.json
                file_path = "/app/d2meshdata.json"
                act_value = d2mesh_data.get("act_value", {})
                act_value.update(config_payload)  # Update specific fields
                d2mesh_data["act_value"] = act_value

            # Save the updated data back to the respective file
            with open(file_path, "w") as f:
                json.dump(pisat_data if "lightpost" in topic_base else d2mesh_data, f, indent=4)

            # Print the updated data
            print(f"Updated data in {file_path}: {json.dumps(pisat_data if 'lightpost' in topic_base else d2mesh_data, indent=4)}")

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
        topic_base = msg.topic.rsplit("/", 1)[0]
        handle_config_message(config_payload, topic_base)

# Function for timed publishing
def publish_timed(client):
    while running and timed_publishing:
        publish_all_topics(client)
        time.sleep(publish_interval)

# Publish all topics from pisat.json
def publish_all_topics(client):
    for topic, payload in pisat_data.items():
        topic_full = f"d2mesh/gate2DB48EC0/lightpost/{topic}/act_value"
        client.publish(topic_full, json.dumps(payload))
        print(f"Published to {topic_full}: {payload}")

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

    if timed_publishing:
        thread = threading.Thread(target=publish_timed, args=(client,))
        thread.start()
    # Let the program run indefinitely
    try:
        while running:
            time.sleep(60)  # Sleep to simulate periodic processing or publishing if needed
    except KeyboardInterrupt:
        print("Program interrupted. Exiting.")

    # Stop the loop when exiting
    client.loop_stop()
    print("MQTT loop stopped.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Program interrupted. Exiting.")
