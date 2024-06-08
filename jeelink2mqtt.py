import asyncio
import logging
import sys
import time
import paho

import paho.mqtt
import paho.mqtt.client
import serial_asyncio


class Serial:
    async def main(self):
        try:
            self.reader, self.writer = await serial_asyncio.open_serial_connection(
                url="/dev/ttyUSB0", baudrate=57600
            )
        except IOError:
            log.error("Can not open USB device!")
            exit("No device")

        # wait till jeelink has settled to ensure init sequence will be received
        time.sleep(2)
        log.info("Start receiving...")
        await asyncio.gather(self.receive())

    async def receive(self):
        while True:
            msg = await self.reader.readuntil(b"\n")
            msg = LaCrosse.decodeMessage(msg)


class LaCrosse:
    """
    Class for decoding the LaCrosse messages.
    Protocol: http://fredboboss.free.fr/articles/tx29.php
    """

    @staticmethod
    def decodeMessage(message):
        # log.debug(f"LaCrosse: Decoding message: {message}")
        values = message.split()

        if len(values) == 0:
            # if message != b"\n":
            log.debug(f"LaCrosse: Received empty message {message}")
            return

        if values[0].startswith(b"[LaCrosse"):
            log.debug(f"LaCrosse: Receiver is {str(values[0])}")
            return

        if values[0] != b"OK" or values[1] != b"9":
            log.debug(f"LaCrosse: Unknown message received {message}")
            return

        id = int(values[2])
        batteryNew = int(values[3]) >> 7
        # type = int(values[3]) & 0x7F
        temperature = int(values[4]) * 256 + int(values[5])
        temperature = (float(temperature) - 1000) / 10
        batteryWeak = int(values[6]) >> 7
        humidity = int(values[6]) & 0x7F

        log.debug(
            f"LaCrosse: Sensor reporting: ID {id}, Temperature {temperature}, Humidity {humidity}, Battery new {batteryNew}, Battery weak {batteryWeak}"
        )


def mqtt_on_connect(client, userdata, connect_flags, reason_code, properties):
    if reason_code == 0:
        log.info("MQTT: Connected successfully to the MQTT broker")
    else:
        log.error(f"MQTT: Failed to connect with code {reason_code}")


def mqtt_on_disconnect(client, userdata, reason_code):
    log.info("MQTT: Disconnected from the MQTT broker")


def mqtt_on_log(client, userdata, level, buf):
    log.debug(f"MQTT: Message {buf}")


if __name__ == "__main__":
    log = logging.getLogger(__name__)
    log.setLevel("DEBUG")
    fmt = logging.Formatter("%(asctime)s %(levelname)7s: %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(sh)

    mqtt = paho.mqtt.client.Client(
        paho.mqtt.enums.CallbackAPIVersion.VERSION2, client_id="jeelink2mqtt"
    )
    mqtt.on_connect = mqtt_on_connect
    # mqtt.on_log = mqtt_on_log
    mqtt.on_disconnect = mqtt_on_disconnect

    mqtt.connect("localhost", 1883, 60)
    mqtt.loop_start()

    while not mqtt.is_connected():
        log.debug("MQTT: Waiting for connection")
        time.sleep(1)

    try:
        s = Serial()
        asyncio.run(s.main())
    except KeyboardInterrupt:
        mqtt.loop_stop()
        mqtt.disconnect()
        time.sleep(2)
        print("Terminated")
