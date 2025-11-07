from time import sleep

from pqnstack.pqn.drivers.powermeter import PM100DDevice

powermeter = PM100DDevice(name="bob", desc="desk", address="/dev/usbtmc0")
powermeter.start()
sleep(5)
while True:
    sleep(0.5)
