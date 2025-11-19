import time, network, ubinascii, urequests
import ntptime
import machine

WIFI_SSID = "Wokwi-GUEST"
WIFI_PASS = ""

def connect_wifi():
    print("Conectando ao Wi-Fi...", end="")
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.connect(WIFI_SSID, WIFI_PASS)

    while not sta.isconnected():
        print(".", end="")
        time.sleep(0.3)
    print("Wifi Conectado!")
    return sta

def get_device_config():
    wlan = connect_wifi()
    # mac = ubinascii.hexlify(wlan.config('mac')).decode()
    mac = "teste1"
    print("MAC:", mac)

    url = f"https://api.tailfox.cloud/dv/mqtt/credentials?mac={mac}"
    try:
        resp = urequests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            print(data)
            resp.close()
            config_data = data.get("data")
            if not config_data:
                print("Nenhum dado recebido da API.")
                return None


            device_id = config_data["deviceId"]
            hostname = config_data["iotHubHost"]
            key = config_data["sasToken"]
            current_config = config_data["current_config"]
            config = {
                "MQTT_CLIENT_ID": device_id,
                "MQTT_BROKER": hostname,
                "MQTT_PORT": 8883,
                "MQTT_USER": f"{hostname}/{device_id}/?api-version=2021-04-12",
                "MQTT_PASSWORD": key,
                "MQTT_TOPIC": f"devices/{device_id}/messages/events/",
                "MQTT_TOPIC_CMD": f"devices/{device_id}/messages/devicebound/#",
            }

            print("Configuração MQTT recebida:")
            print(config)
            return config, current_config
        else:
            print("HTTP ERRO:", resp.status_code)
            resp.close()
    except Exception as e:
        print("Erro ao buscar config:", e)
    return None


def sync_relogio_ntp():
    try:
        ntptime.settime()
        print("Relógio sincronizado com NTP")
    except Exception as e:
        print("Erro ao sincronizar NTP:", e)