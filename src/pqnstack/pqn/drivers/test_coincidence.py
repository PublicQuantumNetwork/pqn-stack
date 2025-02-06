from TimeTagger import Coincidence, Coincidences, CoincidenceTimestamp, createTimeTagger, Counter, Correlation, SynchronizedMeasurements
import numpy as np

tagger = createTimeTagger()
coinc = Coincidences(tagger, [[1,2]], coincidenceWindow=300, timestamp=CoincidenceTimestamp.ListedFirst)
channels = coinc.getChannels()
counting = Counter(tagger, channels, 100, 1000)

measurementDuration = 10e12 # 10 s
counting.startFor(measurementDuration)
counting.waitUntilFinished()

index = counting.getIndex()
counts = counting.getData()

print("Unmodified input delay values")
print(counts)

coinc = Coincidences(tagger, [[1,2]], coincidenceWindow=300, timestamp=CoincidenceTimestamp.ListedFirst)
channels = coinc.getChannels()
counting = Counter(tagger, channels, 100, 1000)

measurementDuration = 10e12 # 10 s
counting.startFor(measurementDuration)
counting.waitUntilFinished()

index = counting.getIndex()
counts = counting.getData()

print("Unmodified input delay values")
print(counts)

corr = Correlation(tagger, 1, 2, binwidth=100, n_bins=1000)
corr.startFor(measurementDuration)
corr.waitUntilFinished()
data=corr.getData()
print(data)
print(f"Max Value at {np.argmax(data)}")

print("Modified input delay values")
tagger.setInputDelay(1, 0)
tagger.setInputDelay(2, 0)
sm = SynchronizedMeasurements(tagger)
corr = Correlation(sm.getTagger(), 1, 2, binwidth=100, n_bins=1000)
sm.startFor(int(30e12), clear=True)
sm.waitUntilFinished()
hist_t = corr.getIndex()
hist_c = corr.getData()
dt = int((1000 - np.argmax(hist_c)) * 100)
print(f"Measured Delay = {dt}")

tagger.setInputDelay(1, dt)
coinc = Coincidences(tagger, [[1,2]], coincidenceWindow=300, timestamp=CoincidenceTimestamp.ListedFirst)
channels = coinc.getChannels()
counting = Counter(tagger, channels, 100, 1000)

measurementDuration = 10e12 # 10 s
counting.startFor(measurementDuration)
counting.waitUntilFinished()

index = counting.getIndex()
counts = counting.getData()

print(counts)
