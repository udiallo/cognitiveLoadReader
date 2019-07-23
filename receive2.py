import time
from collections import deque, OrderedDict
from itertools import islice
from threading import Thread, Lock

import numpy as np
from pylsl import resolve_stream, StreamInlet, local_clock
from scipy.signal import periodogram

from bandpower import bandpower
import matplotlib.pyplot as plt

import json, requests

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

        self.cl_min = 0
        self.cl_max = 0
        self.threshold = 0
        self.threshold_calculated = False


    def auto_resolve(self):
        streams = resolve_stream() # get all current streams
        for stream in streams:
            print(stream)
            if stream.name() == "obci_eeg1": #looking for stream with name ...
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


            #print("index of timestamp with smallest difference: ", index)
            #print("current segment_size: ", segment_size)
            #print("length of data_buffer: ", len(self.data_buffer))
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


    def cl_index(self, segment_powers, alpha_channel, theta_channel):
        # alpha_channel, theta_channel -> choosing channel of interest for each band

        segment_powers = np.array(segment_powers)
        theta = segment_powers[theta_channel, 0]  # mat -> second values rows, third values columns
        alpha = segment_powers[alpha_channel, 1]  # currently over all channels

        cli_all_channel = theta / alpha # calculate cognitive load

        if len(cli_all_channel) > 1:
            cli_mean_of_channel = np.mean(cli_all_channel)
        else:
            cli_mean_of_channel = cli_all_channel
        return cli_mean_of_channel, cli_all_channel

    ####################################################################################################################
    #  Calculates Cognitive Load adapted from Pfurtscheller, 1999
    def erd_ers(self, absolute_power, alpha_channel, theta_channel, baseline):
        baseline = np.array(baseline)
        absolute_power = np.array(absolute_power)
        theta = absolute_power[theta_channel, 0]
        alpha = absolute_power[alpha_channel, 1]

        abs_power = np.zeros(2)  # erstellt array für [theta alspha]
        # abs_power_ = [theta, alpha]
        abs_power[0] = theta
        abs_power[1] = alpha

        cog_load = np.zeros(len(abs_power))

        for i in range(2):

            # ERD/ERS% percentage of power decrease or increase
            cog_load[i] = ((baseline[i]- abs_power[i])/ baseline[i])*100

        #print("Cog Load", cog_load)

        return cog_load
    ####################################################################################################################


    # plot of Cog Load CLi
    def plot_cli(self, cli_list):
        plt.figure(1)
        plt.plot(cli_list)
        plt.show()



    def send_hint(self, cli_list):
        # send hint, if mean of last three cli values is under threshold

        threshold = 4
        num_of_last_values = 10
        if (do_pretest):
            threshold = lsl.threshold

        cli_last_values = cli_list[-num_of_last_values:-1] # == cli_list[len(cli_list)-4 : len(cli_list)-1]
        if (len(cli_last_values) >= 2):
            cli_mean = np.mean(cli_last_values)
            print("mean of last cli values: ", cli_mean)

            if (cli_mean > threshold): # choose threshold as hard coded, lsl.threshold as calculated from pretest
                print("Show hint!!!")

                requests.post("http://localhost:25080", json.dumps({'hint': 1}))

    ####################################################################################################################
    def plot_cogload(self, cog_load_theta):

        plt.figure(2)
        plt.plot(cog_load_theta)
        plt.xlabel('time in sec')
        plt.ylabel('ERD/ERS %')
        plt.show()
    
    ####################################################################################################################

    # calculates mean of first test phase
    def calculate_cl_min(self, cli_list):
        num_last_values = 30
        cli_list = cli_list[-num_last_values:-1]
        cli_list = np.asarray(cli_list)
        min_value = np.mean(cli_list)
        self.cl_min = min_value

    ####################################################################################################################
    # Calculates mean of theta and alpha of 29 last values in selected channel for first test phase
    def calculate_baseline(self, baseline_list):
        baseline_list = np.array(baseline_list)
        # 34 werte
        num_last_values = 30
        # theta_baseline = baseline_list
        baseline_list = baseline_list[-num_last_values:-1]  # --> 2x29 values
        baseline_list = np.asanyarray(baseline_list)
        baseline = np.mean(baseline_list, axis=0)

        self.cl_baseline = baseline

        return baseline
    ####################################################################################################################

    def calculate_cl_max(self, cli_list):
        num_last_values = 40
        cli_list = cli_list[-num_last_values:-1]
        cli_list = np.asarray(cli_list)
        max_value = max(cli_list)
        self.cl_max = max_value

    def calculate_threshold(self):
        self.threshold = 0.9 * self.cl_max

    def start_task2(self):
        requests.post("http://localhost:25080",
                      json.dumps({'canvasText': "Please remember the sequences and speak them out loud after the sequence disappears"}))
        time.sleep(5)

        requests.post("http://localhost:25080",
                      json.dumps({'sequence': ["392", "5346",  "28975", "640901", "8475132", "10738295", "923717562", "2846105304"]}))


    def end_task2(self):

        requests.post("http://localhost:25080",
                      json.dumps({'canvasText': "Thank you"}))
        #time.sleep(4)




if __name__ == '__main__':
    lsl = Lsl_receiver()
    lsl.auto_resolve()
    lsl.start_recording()

    requests.post("http://localhost:25080",
          json.dumps({'reset': True}))

    alpha_channel = [0]#, 2]  # choose channel of interest for alpha_band
    theta_channel = [1]#, 3]  # choose channel of interest for theta_band

    do_pretest = True  #

    #calculate threshold

    requests.post("http://localhost:25080",
                  json.dumps({'canvasText': "Please look at the fixation-cross for the next seconds"}))
    time.sleep(3)
    requests.post("http://localhost:25080",
                  json.dumps({'showFixationPoint': True}))

    if do_pretest:

        try:
            time.sleep(1)
            data, _ = lsl.cut_segment(local_clock(), 1)
            band = bandpower(data_segment=data)
            cli_list = []
            baseline = []
            baseline_list = []
            cog_load_theta = []
            cog_load_alpha = []
            counter = 0
            time_stop_task1 = 34
            time_stop_task2 = 60
            time_after_task2 = 70
            try:
                while not lsl.threshold_calculated:
                    time.sleep(1)  # time.sleep, otherwise CPU will be 100% used

                    # data contains for 1 second 125 arrays with each 8 values (for every channel)
                    data, times = lsl.cut_segment(local_clock() - 5.5,
                                                  5)  # current time minus x seconds for an interval of y (Second argument)

                    ####################################################################################################
                    # calculates baseline before test // mean von 34 sek in counter = 34
                    if counter < time_stop_task1:
                        baseline_power = band.calculate_abspower(data, times,
                                                                 125)  # baseline == baseline_band_mat from bandpower.py //  [theta, alpha]
                        baseline_power = np.array(baseline_power)

                        theta = baseline_power[theta_channel, 0]  # mat -> second values rows, third values columns
                        alpha = baseline_power[alpha_channel, 1]  # currently over all channels

                        baseline_ = np.zeros(2)  # erstellt array für [theta alspha]
                        # baseline_ = [theta, alpha]

                        baseline_[0] = theta
                        baseline_[1] = alpha

                        # baseline list of theta, alpha values for each sec
                        baseline_list.append(baseline_)  # appends baseline for each sec, so 29 times


                    if counter == time_stop_task1:
                        lsl.calculate_cl_min(cli_list)
                        baseline = lsl.calculate_baseline(baseline_list)  # calculates mean of 29 last Sec
                        # print("Baseline Mean Value of Theta Channel and Alpha Channel  == ", theta_channel,
                        #     alpha_channel, baseline)

                        cli_list = []
                        lsl.start_task2()

                    if counter == time_stop_task2:
                        lsl.end_task2()

                    if counter == time_after_task2:
                        lsl.calculate_cl_max(cli_list)
                        lsl.calculate_threshold()
                        lsl.threshold_calculated = True





                    segment_powers = band.calculate_bandpower(data, times, 125)

                    #band_mat.append(segment_powers)  # band_mat == band powers

                    cli, _ = lsl.cl_index(segment_powers, alpha_channel, theta_channel)

                    cli_list.append(cli)


                    lsl.plot_cli(cli_list)  # plot list of cli for channel chan

                    ####################################################################################################
                    # calculate absolute power for test phase

                    if len(baseline) == 0:
                        pass
                        #print("baseline empty", baseline)
                    else:
                        # calculate absolute power for test phase
                        absolute_power = band.calculate_abspower(data, times, 125)

                        # ERD/ERS
                        cog_load = lsl.erd_ers(absolute_power, alpha_channel, theta_channel, baseline)

                        cog_load_theta.append(cog_load[0])
                        cog_load_alpha.append(cog_load[1])
                        # print("cog load tehta", cog_load_theta)
                        lsl.plot_cogload(cog_load_theta)

                    ####################################################################################################

                    counter+=1
                    print(counter)




            except KeyboardInterrupt:
                pass


        except KeyboardInterrupt:
            lsl.stop_recording()

            print("Done.")


# skills lab is starting

    requests.post("http://localhost:25080",
                  json.dumps({'canvasText': "You can start with the skillslab task now!"}))

    print("cl_threshold: " + str(lsl.threshold))
    print("cl_min: " + str(lsl.cl_min))
    print("cl_max: " + str(lsl.cl_max))

    time.sleep(3)

    requests.post("http://localhost:25080",
                  json.dumps({'finishedPreparation': True}))



    try:
        time.sleep(1)
        data, _ = lsl.cut_segment(local_clock(), 1)
        band = bandpower(data_segment=data)
        band_mat = []
        cli_list = []

        try:
            while True:
                time.sleep(1) #time.sleep, otherwise CPU will be 100% used
                # data contains for 1 second 125 arrays with each 8 values (for every channel)
                data, times = lsl.cut_segment(local_clock()-5.5, 5) #current time minus x seconds for an interval of y (Second argument)
                segment_powers = band.calculate_bandpower(data, times, 125)

                #band_mat.append(segment_powers) # band_mat == band powers

                cli, _ = lsl.cl_index(segment_powers, alpha_channel, theta_channel)  # could also give cli_all_channel, which is an array of cli for every channel

                cli_list.append(cli)

                lsl.send_hint(cli_list)

                lsl.plot_cli(cli_list)



                #lsl.plot_cli(cli_list) # plot list of cli for channel chan

        except KeyboardInterrupt:
            pass




        ###later: wait for trigger, than start lsl.cut_segment with argument which could be passed from unreal?
        ### So, in main, while loop is waiting for input?


    except KeyboardInterrupt:
        lsl.stop_recording()

        print("Done.")


# plug in dongle, turn on cyton, start "sudo python openbci_lsl.py /dev/ttyUSB0 --stream" in OpenBCI_LSL directory
# then /start for streaming, /stop and /exit