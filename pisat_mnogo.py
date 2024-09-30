import paho.mqtt.client as mqtt
import json
import threading
import time


# Load data from d2meshdata.json
def load_d2meshdata():
    try:
        with open('d2meshdata.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: d2meshdata.json not found.")
        return None
    except json.JSONDecodeError:
        print("Error: d2meshdata.json contains invalid JSON.")
        return None


# Function to handle the lookup of requested variables
def lookup_variable(variable, data):
    if 'act_value' in data and variable in data['act_value']:
        return data['act_value'][variable]
    else:
        print(f"Variable '{variable}' not found in the core data.")
        return None


# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Successfully connected to the broker.")
        # Subscribe to core and non-core topics
        client.subscribe("d2mesh/gate2DB48EC0/request")
        print("Subscribed to core topics and lightpost topics for each tag.")
    else:
        print(f"Failed to connect with result code {rc}")


def on_message(client, userdata, message):
    print(f"Message received from {message.topic}: {message.payload.decode()}")

    try:
        requested_vars = json.loads(message.payload.decode())

        data = load_d2meshdata()
        if data:
            for var in requested_vars:
                value = lookup_variable(var, data)
                if value is not None:
                    print(f"Found {var}: {value}")
                else:
                    print(f"No matching data found for {var}.")
        else:
            print("Failed to load data from d2meshdata.json.")

    except json.JSONDecodeError:
        print("Error: Received message is not valid JSON.")


def publish_data(client, topic, variables):
    data = load_d2meshdata()
    if data:
        result = {}
        for var in variables:
            value = lookup_variable(var, data)
            if value is not None:
                result[var] = value
        client.publish(topic, json.dumps(result))
        print(f"Published to {topic}: {json.dumps(result)}")
    else:
        print("Failed to load data for publishing.")


# Timed publishing function
def timed_publish(client, interval):
    while True:
        data = load_d2meshdata()
        if data:
            client.publish("d2mesh/gate2DB48EC0/act_value", json.dumps(data['act_value']))
            print("Published act_value data on interval.")
        time.sleep(interval)


# User interface and menu handling
def menu(client):
    while True:
        print("\nOptions:")
        print("1. Publish to core config")
        print("2. Publish to core request")
        print("3. Publish to non-core config")
        print("4. Publish to non-core request")
        print("5. Toggle timed publishing")
        print("6. Set time interval for publishing")
        print("7. Quit")

        choice = input("Choose an option (1, 2, 3, or 4): ")

        if choice == '1':
            variables = input("Enter the requested variables (JSON list format): ")
            variables = json.loads(variables)
            publish_data(client, "d2mesh/gate2DB48EC0/config", variables)

        elif choice == '2':
            variables = input("Enter the requested variables (JSON list format): ")
            variables = json.loads(variables)
            publish_data(client, "d2mesh/gate2DB48EC0/request", variables)

        elif choice == '3':
            variables = input("Enter the requested variables (JSON list format): ")
            variables = json.loads(variables)
            publish_data(client, "d2mesh/gate2DB48EC0/non-core-config", variables)

        elif choice == '4':
            variables = input("Enter the requested variables (JSON list format): ")
            variables = json.loads(variables)
            publish_data(client, "d2mesh/gate2DB48EC0/non-core-request", variables)

        elif choice == '5':
            toggle_timed_publish(client)

        elif choice == '6':
            interval = input("Set new time interval (in seconds): ")
            interval = int(interval)
            change_time_interval(interval)

        elif choice == '7':
            print("Exiting the program...")
            break
        else:
            print("Invalid option, please try again.")


# Toggling timed publishing and changing interval
timed_publishing_enabled = False
time_interval = 10


def toggle_timed_publish(client):
    global timed_publishing_enabled
    timed_publishing_enabled = not timed_publishing_enabled
    if timed_publishing_enabled:
        threading.Thread(target=timed_publish, args=(client, time_interval)).start()
        print(f"Timed publishing enabled with interval {time_interval} seconds.")
    else:
        print("Timed publishing disabled.")


def change_time_interval(new_interval):
    global time_interval
    time_interval = new_interval
    print(f"Time interval changed to {time_interval} seconds.")


# Main function
def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # Start MQTT connection
    client.connect("mqtt-broker-url", 1883, 60)

    # Start menu in a separate thread
    threading.Thread(target=menu, args=(client,)).start()

    # Blocking call to process network traffic and handle reconnecting
    client.loop_forever()


if __name__ == '__main__':
    main()
