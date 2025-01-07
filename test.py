from collections import deque
import sys
import time

from pyfirmata2 import Arduino

from pqnstack.pqn.drivers.polarimeter import ArduinoPolarimeter

if __name__ == "__main__":
    board: Arduino = Arduino(Arduino.AUTODETECT)
    board.samplingOn(1000 // 4)
    buffer = deque(maxlen=10)
    print(board.analog)
    board.analog[0].register_callback(buffer.append)
    board.analog[0].enable_reporting()
    # polarimeter = ArduinoPolarimeter(board=board)
    # polarimeter.start_normalizing()

    try:
        while True:
            # print(buffer)
            # print(polarimeter._buffers[0])
            # print(polarimeter)
            # input()
            # result = polarimeter.read()
            # print(f"{result:.2f} {result.theta=:+.2f}")
            # input()
            sys.stdout.write(f"\r{buffer}")
            sys.stdout.flush()
            time.sleep(0.05)

    except KeyboardInterrupt:
        sys.stdout.write("\n")
    finally:
        board.exit()
        # polarimeter.close()
