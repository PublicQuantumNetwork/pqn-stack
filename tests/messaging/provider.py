import logging

from pqnstack.network.instrument_provider import InstrumentProvider

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    instruments = {
        "dummy1": {
            "import": "pqnstack.pqn.drivers.dummies.DummyInstrument",
            "desc": "Dummy Instrument 1",
            "hw_address": "123456",
        }
    }
    provider = InstrumentProvider("provider1", "127.0.0.1", 5555, **instruments)
    provider.start()
