import uasyncio as asyncio
import time
from machine import Pin

class Signal:
    def __init__(self, currentConfig, semaforo_id="S1"):
        self.red = Pin(27, Pin.OUT)
        self.yellow = Pin(12, Pin.OUT)
        self.green = Pin(14, Pin.OUT)
        self.blue = Pin(13, Pin.OUT)
        self.semaforo_id = semaforo_id
        self.yellowDuration = 5

        # Estado de conectividade
        self.wifi_ok = True
        self.mqtt_ok = True
        self.last_wifi_fail = None

        # Configuração atual e próxima
        self.current_config = currentConfig
        self.next_config = None

        # Controle de interrupção do ciclo
        self.cycle_interrupt = asyncio.Event()

    async def run_cycle(self):
        while True:
            config = self.current_config
            print(f"\n Novo ciclo iniciado: {config}")
            start = time.time()

            # Verde
            self.green.value(1)
            await self._sleep_interruptible(config["green_duration"] - self.yellowDuration)
            self.green.value(0)

            # Amarelo
            self.yellow.value(1)
            await self._sleep_interruptible(self.yellowDuration)
            self.yellow.value(0)

            # Vermelho — completa o ciclo
            red_time = config["cycle_total"] - config["green_duration"] - 5
            self.red.value(1)
            await self._sleep_interruptible(red_time)
            self.red.value(0)

            # Ao final do ciclo, verifica se há nova config
            if self.next_config:
                print("🔄 Atualizando para novo ciclo recebido.")
                self.current_config = self.next_config
                self.next_config = None
            else:
                print("⏱ Mantendo ciclo atual.")

    async def _sleep_interruptible(self, duration):
        """Permite interromper a espera caso chegue nova configuração."""
        try:
            await asyncio.wait_for(self.cycle_interrupt.wait(), duration)
        except asyncio.TimeoutError:
            # tempo normal expirou → segue o ciclo
            pass
        else:
            # nova config chegou
            self.cycle_interrupt.clear()

    def update_cycle(self, message):
        print(f"Nova configuração recebida: {message}")
        self.next_config = message
        self.cycle_interrupt.set()  # Interrompe o ciclo atual

    async def status_fallback(self):
        """
        Gerencia fallback do LED azul:
        - Pisca lento (2s) se Wi-Fi falhou recentemente
        - Pisca rápido (1s) se broker caiu
        - Fica aceso fixo se Wi-Fi ficou muito tempo sem reconectar
        - Apaga quando tudo normal
        """
        while True:
            # Se Wi-Fi falhou
            if not self.wifi_ok:
                if self.last_wifi_fail is None:
                    self.last_wifi_fail = time.time()

                # Se passou muito tempo sem reconectar (ex: 30s)
                if time.time() - self.last_wifi_fail > 30:
                    self.blue.value(1)  # aceso fixo
                    await asyncio.sleep(1)
                    continue

                # Pisca lento (2s)
                self.blue.value(1)
                await asyncio.sleep(0.3)
                self.blue.value(0)
                await asyncio.sleep(2)
                continue

            # Se broker caiu
            if not self.mqtt_ok:
                self.blue.value(1)
                await asyncio.sleep(0.3)
                self.blue.value(0)
                await asyncio.sleep(1)
                continue

            # Caso normal
            self.last_wifi_fail = None
            self.blue.value(0)
            await asyncio.sleep(10)

    def set_wifi_status(self, ok: bool):
        if ok != self.wifi_ok:
            print(f"📶 Wi-Fi {'restaurado' if ok else 'perdido'}")
        self.wifi_ok = ok
        if ok:
            self.last_wifi_fail = None

    def set_mqtt_status(self, ok: bool):
        if ok != self.mqtt_ok:
            print(f"🛰️ MQTT {'restaurado' if ok else 'desconectado'}")
        self.mqtt_ok = ok

    def test_leds(self):
        print("Testando LEDs...")
        for led in [self.red, self.yellow, self.green, self.blue]:
            led.value(1)
            time.sleep(1)
            led.value(0)
        print("LEDs OK!")

# ---------- Exemplo de uso ----------
# async def main():
#     s = Signal()
#     asyncio.create_task(s.run_cycle())
#
#     # Simula chegada de nova configuração após 10s
#     await asyncio.sleep(10)
#     s.update_cycle({
#         "semaforoID": "S1",
#         "green_start": 0,
#         "green_duration": 70,
#         "cycle_total": 200,
#         "cycle_start": time.time()
#     })
#
# asyncio.run(main())
