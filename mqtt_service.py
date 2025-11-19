import ujson, uasyncio as asyncio
from umqtt.simple import MQTTClient
import time
import _thread
# ----- MQTT Server Parameters -----
# MQTT_CLIENT_ID  = "teste1" 
# MQTT_BROKER     = "tcc-traffic-light.azure-devices.net"
# MQTT_PORT       = 8883
# Senha = chave do dispositivo (SharedAccessKey)
# MQTT_PASSWORD   = "SharedAccessSignature sr=tcc-traffic-light.azure-devices.net%2Fdevices%2Fteste1&sig=aZpy3cvSBjXZGBpUtHyGb0NkOiBiUZdCrOah%2FmzmJnE%3D&se=1758160645"

# Usuário = {IoTHubHostname}/{DeviceId}/?api-version=2021-04-12
# MQTT_USER       = f"{MQTT_BROKER}/{MQTT_CLIENT_ID}/?api-version=2021-04-12"
# Tópicos
# MQTT_TOPIC      = f"devices/{MQTT_CLIENT_ID}/messages/events/"
# MQTT_TOPIC_CMD  =  f"devices/{MQTT_CLIENT_ID}/messages/devicebound/#"

class MQTTService:
    def __init__(self, config, callback=None):
        self.config = config
        self.client = None
        self.connected = False
        self._external_handler = callback 

    def set_external_handler(self, handler):
        self._external_handler = handler

    def connect(self):
        cfg = self.config
        self.client = MQTTClient(
            client_id=cfg["MQTT_CLIENT_ID"],
            server=cfg["MQTT_BROKER"],
            port=cfg["MQTT_PORT"],
            user=cfg["MQTT_USER"],
            password=cfg["MQTT_PASSWORD"],
            ssl=True,
            ssl_params={"server_hostname": cfg["MQTT_BROKER"]},
        )
        self.client.set_callback(self.callback)
        self.client.connect()
        self.client.subscribe(cfg["MQTT_TOPIC_CMD"])
        self.connected = True
        print("Conectado ao MQTT!")

        _thread.start_new_thread(self._listener_thread, ())
   
    # def is_connected(self){
    #     a = self.client.ping()
    #    print(a)
    # }
    
    def publish(self, payload: dict):
        if self.connected:
            msg = ujson.dumps(payload)
            print("📤 Publicando:", msg)
            self.client.publish(self.config["MQTT_TOPIC"], msg.encode())

    def check_messages(self):
        if self.connected:
            try:
                self.client.check_msg()
            except Exception as e:
                print("Erro MQTT:", e)
                self.connected = False

    async def loop(self):
        while True:
            self.check_messages()
            await asyncio.sleep(0.3)

    def _internal_callback(self, topic, msg):
        try:
            obj = ujson.loads(msg)
            print("📩 Mensagem MQTT recebida:", obj)

            if self._external_handler:
                self._external_handler(obj)  

        except Exception as e:
            print("⚠️ Erro ao processar MQTT:", e)

    def _listener_thread(self):
        print("🔍 Listener MQTT iniciado.")
        while True:
            try:
                self.client.wait_msg()   # bloqueia até chegar mensagem
            except Exception as e:
                print("⚠️ Erro listener MQTT:", e)
                self.connected = False
                time.sleep(3)


# Response esperada
# {
#   "semaforoID": "S1",
#   "green_start": 0,
#   "green_duration": 50,
#   "cycle_total": 180,
#   "cycle_start": 815513830
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