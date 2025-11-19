
from wifi import get_device_config, connect_wifi, sync_relogio_ntp

class NetworkFallback:
    def __init__(self):
        self.wifi = None

    def ensure_connected(self):
        if not self.wifi or not self.wifi.isconnected():
            print("⚠️ Wi-Fi desconectado! Tentando reconectar...")
            self.wifi = connect_wifi()
            if self.wifi and self.wifi.isconnected():
                print("✅ Wi-Fi reconectado.")
                sync_relogio_ntp()
            else:
                print("❌ Falha ao reconectar Wi-Fi.")
                return False
        return True
