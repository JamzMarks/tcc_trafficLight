# mrnotyet - do it all over again
import time
from machine import Pin
import ujson
from umqtt.simple import MQTTClient
import _thread
import random
import uasyncio as asyncio
import network, ubinascii
import urequests

# ----- Wifi Parameters -----
WIFI_PASSWORD = ""
WIFI_NAME = "Wokwi-GUEST"

# ----- Funções de Conexão -----
def connectWifi():
    global WIFI_PASSWORD, WIFI_NAME
    print("Connecting to WiFi", end="")
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.connect(WIFI_NAME, WIFI_PASSWORD)
    while not sta_if.isconnected():
        print(".", end="")
        time.sleep(0.3)
    print(" Connected!")
    return sta_if 

def getDevice():
    wlan = connectWifi()
    mac = ubinascii.hexlify(wlan.config('mac')).decode()  # melhor sem ':'
    print('MAC:', mac)

    url = f"http://utils/sas/token?device={mac}"
    try:
        response = urequests.get(url)
        if response.status_code == 200:
            data = response.json()
            response.close()
            return data
        else:
            print("Erro HTTP:", response.status_code)
            response.close()
            return None
    except Exception as e:
        print("Erro na requisição:", e)
        return None
    
# ----- MQTT Server Parameters -----
MQTT_CLIENT_ID  = "teste1" 
MQTT_BROKER     = "tcc-traffic-light.azure-devices.net"
MQTT_PORT       = 8883

# Usuário = {IoTHubHostname}/{DeviceId}/?api-version=2021-04-12
MQTT_USER       = "tcc-traffic-light.azure-devices.net/teste1/?api-version=2021-04-12"

# Senha = chave do dispositivo (SharedAccessKey)
MQTT_PASSWORD   = "SharedAccessSignature sr=tcc-traffic-light.azure-devices.net%2Fdevices%2Fteste1&sig=aZpy3cvSBjXZGBpUtHyGb0NkOiBiUZdCrOah%2FmzmJnE%3D&se=1758160645"

# Tópicos
MQTT_TOPIC      = "devices/teste1/messages/events/"
MQTT_TOPIC_CMD  = "devices/teste1/messages/devicebound/#"

async def startMqttData():
    global MQTT_CLIENT_ID, MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASSWORD, MQTT_TOPIC, MQTT_TOPIC_CMD
    try:
        result = await getDevice()

        if result and "data" in result:
            data = result["data"]
            MQTT_CLIENT_ID  = data.get("MQTT_CLIENT_ID", MQTT_CLIENT_ID)
            MQTT_BROKER     = data.get("MQTT_BROKER", MQTT_BROKER)
            MQTT_PORT       = data.get("MQTT_PORT", MQTT_PORT)
            MQTT_USER       = data.get("MQTT_USER", MQTT_USER)
            MQTT_PASSWORD   = data.get("MQTT_PASSWORD", MQTT_PASSWORD)
            MQTT_TOPIC      = data.get("MQTT_TOPIC", MQTT_TOPIC)
            MQTT_TOPIC_CMD  = data.get("MQTT_TOPIC_CMD", MQTT_TOPIC_CMD)

            print("MQTT configs atualizados!")
            return True
        else:
            raise Exception('Erros nos dados!')

    except Exception as e:
        print("Erro na requisição:", e)
        return False
# Response esperada
# {
#   "data": {
#     "MQTT_CLIENT_ID": "ESP02",
#     ...
#   }
# }

# Comandos NO CLI para obter MQTT_PASSWORD

## Comando para obter connection String.
# az iot hub device-identity connection-string show --hub-name tcc-traffic-light --device-id ESP02
# {
#   "cs": "HostName=tcc-traffic-light.azure-devices.net;DeviceId=ESP02;SharedAccessKey=xxxxxxxxxxxxxxxxxxxxxx="
# }

# az iot hub generate-sas-token --hub-name tcc-traffic-light --device-id teste1 --duration 3600
# {
#   "sas": "SharedAccessSignature sr=tcc-traffic-light.azure-devices.net%2Fdevices%2FESP02&sig=AbCdEfGhIjKlMn...&se=1736752876"
# }


# Estados do sistema
STATE_NORMAL = "NORMAL"
STATE_SERVER_FAIL = "SERVER_FAIL"
STATE_PACKET_FAIL = "PACKET_FAIL"
STATE_DEFAULT_RETRY = "DEFAULT_RETRY"
STATE_CRITICAL_FAIL = "CRITICAL_FAIL"

# ----- LEDs -----
ledVermelho = Pin(27, Pin.OUT)
ledAmarelo  = Pin(12, Pin.OUT)
ledVerde    = Pin(14, Pin.OUT)
ledError    = Pin(13, Pin.OUT)
leds = [ledVermelho, ledAmarelo, ledVerde, ledError]

# ----- Variáveis Globais -----
default_times = {"green": 60, "red": 60}
signal_times = default_times
yellow_duration = 5
update_received = False
server_health = False

def connect_mqtt():
    print("Connecting to Azure IoT Hub MQTT... ", end="")
    client = MQTTClient(
        client_id=MQTT_CLIENT_ID,
        server=MQTT_BROKER,
        port=MQTT_PORT,               
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        ssl=True,                     
        ssl_params={"server_hostname": MQTT_BROKER} 
    )

    client.connect()
    print("Connected!")
    return client

# ----- Função de valores padrão -----
async def setDefaultValues():
    global default_times, yellow_duration
    # vai vir do mqtt no startup da aplicação
    responseValues = {"green": 60, "red": 60, "yellow": 5}
    
    if responseValues:
        try:
            red_val = int(responseValues.get("red", default_times.get("red", 60)))
            green_val = int(responseValues.get("green", default_times.get("green", 60)))
            yellow_val = int(responseValues.get("yellow", yellow_duration))
            
            default_times["red"] = red_val
            default_times["green"] = green_val
            yellow_duration = yellow_val
        except (ValueError, TypeError) as e:
            print("Erro: algum valor não é um número.", e)

# ----- Callback MQTT -----
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

class TrafficFallBack:
    def __init__(self, server_health):
        self.server_health = server_health
        self.retry_count = 0
        pass
    
    # ----- Função de verificação do Servidor -----
    async def server_loop():
        global server_health
        print('loop do servidor')

        while server_health:
            x = random.random() 
            if x > 0.8:
                server_health = False
                print('Entrando no fallback')
    # ----- Fallbacks -----
    def fallback_server_fail():
        ledError(1)
        print("Fallback: servidor fora, usando valores padrão temporários")

    def fallback_packet_fail():
        ledError(1)
        print("Fallback: pacote de semáforos não responde, aplicando default")

    def fallback_default_retry():
        global retry_count, system_state
        ledError(1)
        retry_count += 1
        print(f"Fallback: aplicando valores padrão, tentativa {retry_count}")
        if retry_count > 3:
            system_state = STATE_CRITICAL_FAIL

    def fallback_critical_fail():
        ledError(1)
        print("Fallback: modo emergência")
        while True:
            ledAmarelo.value(1)
            time.sleep(0.5)
            ledAmarelo.value(0)
            time.sleep(0.5)

    def run(self):
        while True:
            if self.system_state == self.STATE_NORMAL:
                print("Semáforo operando normalmente")
                time.sleep(2)
            elif self.system_state == self.STATE_SERVER_FAIL:
                self.server_fail()
            elif self.system_state == self.STATE_PACKET_FAIL:
                self.packet_fail()
            elif self.system_state == self.STATE_DEFAULT_RETRY:
                self.default_retry()
                time.sleep(1)
            elif self.system_state == self.STATE_CRITICAL_FAIL:
                self.critical_fail()

class Signal:
    def __init__(self, leds):
        self.leds = leds

    # ----- Função de teste de LEDs -----
    def startTest(self):
        testResults = []
        for led in self.leds:
            try:
                led.value(1)
                time.sleep(0.5)
                led.value(0)
                testResults.append(1)
            except:
                return False
        return True   
    # ----- Função para alternar semáforo -----
    def signal_loop(reds, yellows, greens):
        global leds
        global yellow_duration
        if any(led.value() == 1 for led in reds):
            for led in reds:
                led.value(0)
            time.sleep(0.2)
            for led in greens:
                led.value(1)
        else:
            for led in greens:
                led.value(0)
            for led in yellows:
                led.value(1)
            time.sleep(yellow_duration)
            for led in yellows:
                led.value(0)
            for led in reds:
                led.value(1)
    # ----- Led Error Fallback
    async def errorLedFallBack(led, tempo_on: int, tempo_off: int, vezes: int =None):
        """
        Pisca o LED de Erro em tempos diferentes.
        
        :param led: objeto Pin
        :param tempo_on: tempo em segundos ligado
        :param tempo_off: tempo em segundos desligado
        :param vezes: número de piscadas; None = infinito
        """
        contador = 0
        while True:
            if vezes is not None and contador >= vezes:
                led.value(0)
                break
            led.value(1)
            time.sleep(tempo_on)
            led.value(0)
            time.sleep(tempo_off)
            contador += 1

class MQTTService:
    def __init__(self, client, topic_pub, topic_sub, callback=None):
        self.client = client
        self.topic_pub = topic_pub
        self.topic_sub = topic_sub
        self.callback = callback or self.default_callback
        self.connected = False

    def connect(self):
        self.client.set_callback(self.callback)
        self.client.subscribe(self.topic_sub)
        self.connected = True
        print("MQTTService conectado e inscrito em:", self.topic_sub)
    
    def publish(self, msg: str):
        """Publica no tópico padrão"""
        if self.connected:
            print("Publicando:", msg)
            self.client.publish(self.topic_pub, msg.encode())
        else:
            print("MQTTService não está conectado")

    def check_messages(self):
        """Checa mensagens recebidas"""
        try:
            self.client.check_msg()
        except Exception as e:
            print("Erro no check_msg:", e)
            self.connected = False
    
    async def loop(self):
        while True:
            if self.connected:
                self.check_messages()
            await asyncio.sleep(0.1)

    def default_callback(self, topic, msg):
        print("Mensagem recebida:", topic, msg)
    async def mqtt_loop(self):
        while True:
            self.client.check_msg()
            await asyncio.sleep(0.1)

    async def mqtt_health_loop(self):
        global MQTT_TOPIC
        self.client.publish(MQTT_TOPIC, b'{"status":"ok"}')

# ----- Função Main -----
async def main():
    global MQTT_TOPIC, MQTT_TOPIC_CMD, server_health, leds

    wifi = connectWifi()
    startMqttData()
    client = connect_mqtt()
    # isOk = startMqttData()
    # client.set_callback(mqtt_callback)
    # client.subscribe(MQTT_TOPIC_CMD)
    
    # Cria serviço MQTT
    # mqtt_service = MQTTService(client, MQTT_TOPIC, MQTT_TOPIC_CMD, mqtt_callback)
    # mqtt_service.connect()
    # asyncio.create_task(mqtt_service.loop())

    # Cria Signal
    # signal = Signal(leds)
    # signal.startTest()

    # # Testa LEDs
    # testResults: bool = signal.startTest()
    # if testResults != True:
    #     print('Erro nos Leds')
    #     return 

    # # Cria Fallbacks    
    # fallbacks = TrafficFallBack(server_health)
    # asyncio.create_task(fallbacks.server_loop())

    # # Função para valores padrão
    # try:
    #     await setDefaultValues()
    #     server_health = True
    # except:
    #     print('erro')

    # _thread.start_new_thread(server_loop, ())
    # asyncio.create_task(errorLedFallBack(ledError, 0.2, 0.2))

    # while True:
    #     # Checar mensagens MQTT
    #     client.check_msg()

    #     if server_health:
    #         changeSignal()
    #     else:
    #         ledError.value(1)  # fallback
    #         time.sleep(1)
    #         ledError.value(0)

asyncio.run(main())
