# mrnotyet - do it all over again
import time
import ujson
import _thread
import random
import uasyncio as asyncio
import network, ubinascii
import urequests
import random
from machine import Pin
from umqtt.simple import MQTTClient
from time import sleep
from signal import Signal
from wifi import get_device_config
from mqtt_service import MQTTService
from networkFallback import NetworkFallback
from brokerFallback import BrokerFallback

async def main():
    print("🔌 Iniciando sistema...")

    # Etapa 1: Inicialização de rede
    network_fallback = NetworkFallback()
    if not network_fallback.ensure_connected():
        print("❌ Falha inicial de Wi-Fi...")

    # Obter configuração do dispositivo
    device_config, current_config = get_device_config()
    mqtt_service = MQTTService(device_config)
    broker_fallback = BrokerFallback(mqtt_service, get_device_config)

    try:
        mqtt_service.connect()
        asyncio.create_task(mqtt_service.loop())
    except Exception as e:
        print("⚠️ Não foi possível conectar MQTT inicialmente:", e)

    # Etapa 2: Inicializa semáforo
    signal = Signal(current_config, device_config["MQTT_CLIENT_ID"],)
    signal.test_leds()
    asyncio.create_task(signal.run_cycle())
    asyncio.create_task(signal.status_fallback())

    # Etapa 3: Monitoramento
    async def watchdog():
        while True:
            # 1. Verifica Wi-Fi
            if not network_fallback.ensure_connected():
                await asyncio.sleep(5)
                continue 

            # 2. Verifica Broker MQTT
            # await broker_fallback.ensure_connected()

            await asyncio.sleep(15)

    asyncio.create_task(watchdog())
    
    try:
        mqtt_service.connect()
        # integração direta com o semáforo
        mqtt_service.set_external_handler(signal.update_cycle)

        asyncio.create_task(mqtt_service.loop())
    except Exception as e:
        print("⚠️ Não foi possível conectar MQTT inicialmente:", e)
    # Etapa 4: Simula chegada de mensagens



try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\n🛑 Execução interrompida pelo usuário.")
except Exception as e:
    print("❌ Erro inesperado:", e)
