"""
MicroPython IoT Weather Station Example for Wokwi.com

To view the data:

1. Go to http://www.hivemq.com/demos/websocket-client/
2. Click "Connect"
3. Under Subscriptions, click "Add New Topic Subscription"
4. In the Topic field, type "wokwi-weather" then click "Subscribe"

Now click on the DHT22 sensor in the simulation,
change the temperature/humidity, and you should see
the message appear on the MQTT Broker, in the "Messages" pane.

Copyright (C) 2022, Uri Shaked
https://wokwi.com/projects/322577683855704658
https://wokwi.com/arduino/projects/322577683855704658
"""

import network
import time
from machine import Pin
import dht
import ujson
from umqtt.simple import MQTTClient
import time

# MQTT Server Parameters
MQTT_CLIENT_ID = "micropython-weather-demo"
MQTT_BROKER    = "broker.mqttdashboard.com"
MQTT_USER      = ""
MQTT_PASSWORD  = ""
MQTT_TOPIC     = "wokwi-weather"

# ----- Configura LEDs -----
ledVermelho     = Pin(27, Pin.OUT)
ledAmarelo      = Pin(12, Pin.OUT)
ledVerde        = Pin(14, Pin.OUT)
ledAzul         = Pin(13, Pin.OUT)

print("Connecting to WiFi", end="")
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('Wokwi-GUEST', '')
while not sta_if.isconnected():
  print(".", end="")
  time.sleep(0.1)
print(" Connected!")

print("Connecting to MQTT server... ", end="")
client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, user=MQTT_USER, password=MQTT_PASSWORD)
client.connect()

print("Connected!")

leds = [ledVermelho, ledAmarelo, ledVerde, ledAzul]

ledVermelho.value(1)
signal_times = {"green": 60, "red": 60}
yellow_duration = 5
update_received = False


# ----- Função de teste -----
def mqtt_callback(topic, msg):
    global signal_times, update_received
    print("Mensagem recebida:", topic, msg)
    if topic.decode() == MQTT_TOPIC_CMD:
        try:
            data = ujson.loads(msg)
            if "green" in data:
                signal_times["green"] = int(data["green"])
            if "red" in data:
                signal_times["red"] = int(data["red"])
            update_received = True
            print("Tempos atualizados:", signal_times)
        except Exception as e:
            print("Erro ao ler JSON:", e)


def changeSignal():
    if(ledVermelho.value() == 1):
        ledVermelho.value(0)
        time.sleep(0.2)
        ledVerde.value(1)
    else:
        ledVerde.value(0)
        ledAmarelo.value(1)
        time.sleep(4)
        ledAmarelo.value(0)
        ledVermelho.value(1)


# ----- Loop principal -----

while True:
    for i, led in enumerate(leds):
        testSignals(led)
