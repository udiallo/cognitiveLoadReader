import time
from collections import deque, OrderedDict
from itertools import islice
from threading import Thread, Lock

import numpy as np
from pylsl import resolve_stream, StreamInlet, local_clock
from scipy.signal import periodogram

from bandpower import bandpower
import matplotlib.pyplot as plt

class Lsl_receiver:

    def __init__(self):
        self.inlet = None
        self.stream = None
        self.data_buffer = deque(maxlen=125*5) #efficient implemented list object, thread safe, 256*5 == 5 seconds (with sampling rate 256)
        self.time_buffer = deque(maxlen=125*5) #buffer for timestemps
        self.offset = 0.0
        self.recording = False
        self.collection_thread = Thread(target=self.grab_data)
        self.lock = Lock() # lock buffer so that only one process is working on it


    def auto_resolve(self):
        streams = resolve_stream() # get all current streams
        for stream in streams:
            print(stream)
            if stream.name() == "openbci_eeg": #looking for stream with name ...
                self.stream = stream
                print("Found stream!!!!!!!")

        if self.stream is None:
            print("No stream found")
            return False

        self.inlet = StreamInlet(self.stream) #inlet for handeling data from stream
        print("Sampling rate:", self.inlet.info().nominal_srate())

        self.offset = self.inlet.time_correction(timeout=3)

    def grab_data(self):
        while self.recording:
            data, times = self.inlet.pull_chunk(timeout=0.0) # data contains sample (e.g. 16 values for 16 channels), if CPU to slow, data can contain more than one sample (list of lists == chunks)

            if data: #if more than 0 elements is in data
                #print(data)
                # f = open("eeg_eyes_closed.txt", "a")
                # np.savetxt(f, data)
                # f.write("\n")
                # f.close()

                with self.lock: # use lock to protect buffer from other processes
                    self.data_buffer.extend(data) # extend: puts data into data_buffer
                    self.time_buffer.extend(np.array(times) + self.offset)

            time.sleep(0.0001) #wait so CPU is not crashing

    def cut_segment(self, timestamp, segment_size_in_sec): #timestamp we are interested in, second argument: segment_size
        data_segment = None
        time_segment = None
        with self.lock:
            diffs = np.abs([timestamp-ts for ts in self.time_buffer])  # create list of differences from timestamp
            index = int(diffs.argmin()) #index of timestamp with smallest difference
            segment_size = int(self.inlet.info().nominal_srate() * segment_size_in_sec)

            print(index, segment_size, len(self.data_buffer))
            #sanity checks: segment_size not bigger than buffer_size, index+segment_length not bigger than buffer

            data_segment = list(islice(self.data_buffer, index, index + segment_size))
            time_segment = list(islice(self.time_buffer, index, index + segment_size))

        return data_segment, time_segment




    def start_recording(self):
        self.recording = True
        self.collection_thread.daemon = True #automatic ending if main is finished
        self.collection_thread.start()

    def stop_recording(self):
        self.recording = False
        self.collection_thread.join() #clean up threads



    def plot_theta_alpha(self, mat):
        mat = np.array(mat)
        #print(band_mat.shape)
        #print(band_mat[:, 0, :])
        plt.plot(mat[:, 0, 0] / mat[:, 0, 1])
        plt.show()




if __name__ == '__main__':
    lsl = Lsl_receiver()
    lsl.auto_resolve()
    lsl.start_recording()



    try:
        time.sleep(1)
        data, _ = lsl.cut_segment(local_clock(), 1)
        band = bandpower(data_segment=data)
        band_mat = []
        try:
            while True:
                time.sleep(2) #time.sleep, otherwise CPU will be 100% used
                data, times = lsl.cut_segment(local_clock()-1.5, 1) #current time minus 1.5 seconds for an interval of 1 (Second argument)
                segment_powers = band.calculate_bandpower(data, times, 125)
                band_mat.append(segment_powers)
                # print("segment_powers", segment_powers)
                lsl.plot_theta_alpha(band_mat)
        except KeyboardInterrupt:
            pass




        ###later: wait for trigger, than start lsl.cut_segment with argument which could be passed from unreal?
        ### So, in main, while loop is waiting for input?


    except KeyboardInterrupt:
        lsl.stop_recording()
        lsl.plot_theta_alpha()
        print("Done.")


# plug in dongle, turn on cyton, start "sudo python openbci_lsl.py /dev/ttyUSB0 --stream" in OpenBCI_LSL directory
# then /start for streaming, /stop and /exit