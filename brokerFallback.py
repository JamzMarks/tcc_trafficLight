import time

class BrokerFallback:
    def __init__(self, mqtt_service, get_config_func):
        self.mqtt = mqtt_service
        self.get_config_func = get_config_func
        self.last_retry = 0

    async def ensure_connected(self):
        # Evita reconectar com muita frequência
        if self.mqtt.connected:
            return

        now = time.time()
        if now - self.last_retry < 10: 
            return

        print("⚠️ MQTT desconectado! Tentando reconectar...")
        self.last_retry = now

        try:
            new_cfg = self.get_config_func()  
            self.mqtt.config = new_cfg
            self.mqtt.connect()
            print("✅ MQTT reconectado.")
        except Exception as e:
            print("❌ Falha ao reconectar MQTT:", e)
