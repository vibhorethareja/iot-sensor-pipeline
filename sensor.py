import json
import time
import random
import boto3
import ssl
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# Config
ENDPOINT = os.getenv("AWS_IOT_ENDPOINT")
REGION = os.getenv("AWS_REGION")
TOPIC = os.getenv("IOT_TOPIC")
CLIENT_ID = "sensor-device-01"

# Certificate paths
CERT_DIR = os.path.join(os.path.dirname(__file__), "certs")
CA_PATH = os.path.join(CERT_DIR, "AmazonRootCA1.pem")

# Find cert and key files dynamically
def find_cert_file(suffix):
    for f in os.listdir(CERT_DIR):
        if f.endswith(suffix):
            return os.path.join(CERT_DIR, f)
    raise FileNotFoundError(f"No file ending with {suffix} in certs/")

CERT_PATH = find_cert_file("-certificate.pem.crt")
KEY_PATH = find_cert_file("-private.pem.key")

# CloudWatch client
cloudwatch = boto3.client("cloudwatch", region_name=REGION)

def generate_sensor_data():
    return {
        "device_id": CLIENT_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "temperature": round(random.uniform(18.0, 35.0), 2),
        "humidity": round(random.uniform(30.0, 80.0), 2),
        "pressure": round(random.uniform(1000.0, 1025.0), 2)
    }

def publish_to_cloudwatch(data):
    cloudwatch.put_metric_data(
        Namespace="IoTSensorPipeline",
        MetricData=[
            {
                "MetricName": "Temperature",
                "Value": data["temperature"],
                "Unit": "None",
                "Dimensions": [{"Name": "DeviceId", "Value": data["device_id"]}]
            },
            {
                "MetricName": "Humidity",
                "Value": data["humidity"],
                "Unit": "None",
                "Dimensions": [{"Name": "DeviceId", "Value": data["device_id"]}]
            },
            {
                "MetricName": "Pressure",
                "Value": data["pressure"],
                "Unit": "None",
                "Dimensions": [{"Name": "DeviceId", "Value": data["device_id"]}]
            }
        ]
    )
    print(f"✅ CloudWatch metrics published")

# MQTT callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ Connected to AWS IoT Core")
    else:
        print(f"❌ Connection failed with code {rc}")

def on_publish(client, userdata, mid, reason_code=None, properties=None):
    print(f"✅ Message published to {TOPIC}")

# MQTT setup
mqtt_client = mqtt.Client(
    client_id=CLIENT_ID,
    protocol=mqtt.MQTTv5
)

mqtt_client.tls_set(
    ca_certs=CA_PATH,
    certfile=CERT_PATH,
    keyfile=KEY_PATH,
    tls_version=ssl.PROTOCOL_TLS_CLIENT
)

mqtt_client.on_connect = on_connect
mqtt_client.on_publish = on_publish

print(f"🔌 Connecting to {ENDPOINT}...")
mqtt_client.connect(ENDPOINT, 8883, keepalive=60)
mqtt_client.loop_start()

# Wait for connection
time.sleep(2)

# Main loop — publish every 10 seconds
print("🚀 Starting sensor simulation — publishing every 10 seconds")
print("Press Ctrl+C to stop\n")

try:
    while True:
        data = generate_sensor_data()
        payload = json.dumps(data)

        # Publish to IoT Core
        mqtt_client.publish(TOPIC, payload, qos=1)

        # Publish to CloudWatch directly
        publish_to_cloudwatch(data)

        print(f"📊 Data: temp={data['temperature']}°C | "
              f"humidity={data['humidity']}% | "
              f"pressure={data['pressure']}hPa")
        print(f"⏱  Next reading in 10 seconds...\n")

        time.sleep(10)

except KeyboardInterrupt:
    print("\n🛑 Stopping sensor simulation")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    print("✅ Disconnected cleanly")