import paho.mqtt.client as mqtt
import time

broker = "46.39.226.183"
port = 1883
payload = "DeviceMode"  # Отправляем просто строку

# Список тегов, которые ты хочешь использовать
try:
    with open("generated_topics.txt", "r") as file:
        tags = [line.strip() for line in file.readlines() if line.strip()]
except FileNotFoundError as e:
    print(f"Error: Could not find 'generated_topics.txt' file: {e}")
    exit(1)

# Функция обработки входящих сообщений
def on_message(client, userdata, msg):
    if "response" in msg.topic:
        print(f"📩 Ответ от устройства!\nТопик: {msg.topic}\nСообщение: {msg.payload.decode()}\n")
    elif "act_value" in msg.topic:
        print(f"📩 Ответ от устройства!\nТопик: {msg.topic}\nСообщение: {msg.payload.decode()}\n")



# Функция обработки подключения
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Подключились, отправляем запрос...")

        # Подписываемся на все топики, чтобы увидеть, куда приходит ответ
        client.subscribe("#")

        # Отправляем запрос в каждый топик с тегом
        for tag in tags:
            topic_request = f"d2mesh/gate2DB48EC0/lightpost/{tag}/request"  # Формируем топик для каждого тега
            client.publish(topic_request, payload)

    else:
        print(f"❌ Ошибка подключения: {rc}")

# Создаем MQTT-клиента
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Подключаемся к брокеру
try:
    client.connect(broker, port, 60)
    client.loop_start()

    # Ждем ответ 10 секунд
    time.sleep(600)
    client.loop_stop()
except Exception as e:
    print(f"❌ Ошибка: {e}")
