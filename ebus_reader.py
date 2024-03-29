import sys
import os
import time
import threading

from PyQt5 import QtCore, QtGui, QtWidgets, uic

import numpy as np

import pyebus as ebus


# see https://www.learnpyqt.com/tutorials/multithreading-pyqt-applications-qthreadpool/
# for the particular style of coding up the multithreading using PyQt5:
class SignalsDefines(QtCore.QObject):
    """ this is needed since PyQt requires an object to be a subclass of QObject
    in order to define signals, but QRunnable is not. """
    newImage = QtCore.pyqtSignal(object, object, object)
    serialReadComplete = QtCore.pyqtSignal(int, str, str, str)

class EbusReader(QtCore.QRunnable):
    """
    Worker thread
    """
    def __init__(self, use_mock=False, camera=None):
        super().__init__()
        self.use_mock = use_mock
        self.signals  = SignalsDefines()
        self.quit_thread_flag = False # semaphore used to stop the thread
        self.connected = False
        self.streamOpened = False
        self.camera = camera # will get called on a connection event

        if self.use_mock:
            ebus.useMock()

    def quitThread(self):
        """ call this from the gui thread in order to stop the processing in the worker thread """
        self.quit_thread_flag = True

    def list_devices(self):
        """ Returns a list of unique device IDs for all devices found over all interfaces """
        id_list = []

        findEthernetTimeout = 1 # 1500 ms is recommended for the API, but we have no Ethernet camera, so we skip this process (USB cameras do require waiting with a timeout)
        ebus.findDevices(findEthernetTimeout)

        for if_id in range(ebus.getInterfaceCount()):
            if_name = ebus.getInterfaceDisplayID(if_id)
            print("if_name = %s, devices count = %d" % (if_name, ebus.getDeviceCount(if_id)))
            for dev_id in range(ebus.getDeviceCount(if_id)):
                id_list.append(ebus.getDeviceConnectionID(if_id, dev_id))
                print("\tdevice_unique_id = ", id_list[-1])

        return id_list

    def connect(self, device_unique_id):
        t1 = time.perf_counter()
        ebus.connectToDevice(device_unique_id)
        self.device_unique_id = device_unique_id
        t2 = time.perf_counter(); print(t2-t1)
        t1 = time.perf_counter()
        ebus.openDeviceSerialPort()
        t2 = time.perf_counter(); print(t2-t1)
        t1 = time.perf_counter()
        if self.camera:
            self.camera.on_connected(ebus.writeSerialPort, ebus.readSerialPort)
        t2 = time.perf_counter(); print(t2-t1)
        self.connected = True

    def openStream(self, resolution_dict=None):
        self.setupResolution(resolution_dict)
        ebus.openStream(self.device_unique_id)
        self._createBuffers()
        ebus.startAcquisition()
        # self.quit_thread_flag = True
        self.streamOpened = True

    def closeStream(self):
        if self.streamOpened:
            self.streamOpened = False
            ebus.stopAcquisition()
            ebus.closeStream()
            ebus.releaseBuffers()

    def disconnect(self):
        if self.connected:
            ebus.closeDeviceSerialPort()
            ebus.closeDevice()
        self.connected = False

    def setupResolution(self, resolution_dict=None):
        if resolution_dict is None:
            resolution_dict = {
                "Width":       640,
                "Height":      512,
                "PixelFormat": "Mono12",
                "TestPattern": "Off",
                # "TestPattern": "iPORTTestPattern",
                "PixelBusDataValidEnabled": "1"
            }
        for key, value in resolution_dict.items():
            if isinstance(value, int):
                ebus.setDeviceIntegerValue(key, value)
            elif isinstance(value, str):
                ebus.setDeviceEnumValue(key, value)
            else:
                print("Warning! no conversion known for %s, %s" % (key, value))

    def _createBuffers(self):
        (buffer_size, buffer_count) = ebus.getBufferRequirements()
        print("buffer_size = ", buffer_size, ", buffer_count = ", buffer_count)
        # allocate "buffer_count" buffers of size "buffer_size"!
        self.buffers = []
        for k in range(buffer_count):
            self.buffers.append(bytearray(buffer_size))
            ebus.addBuffer(self.buffers[-1])

    @QtCore.pyqtSlot()
    def run(self):
        timeoutMS = 1000

        print("ebus reader thread id: ", threading.get_native_id())
        while not self.quit_thread_flag:
            if self.connected and self.streamOpened:
                (img_buffer, img_info) = ebus.getImage(timeoutMS)
                img_np = np.frombuffer(img_buffer, np.uint16)
                info = ebus.expand_img_info_tuple(img_info)
                img_np = img_np.reshape(info['Height'], info['Width'])
                frame_timestamp = img_np[0, 0]

                # img_copy = np.delete(img_np, 1, axis=1) # remove column that contains the frame timestamps, also creates a copy
                img_copy = img_np.copy() # make a copy so that we can release the ebus buffer for the driver to re-use, while still doing operations on it
                ebus.releaseImage()

                # img_copy = img_copy[0:img_copy.shape[0], 1:img_copy.shape[1]].copy()
                img_copy[:, 0] = img_copy[:, 1] # blank out the timestamp column... couldn't get delete() or slicing operations to work without issues...

                if self.quit_thread_flag:
                    break
                self.signals.newImage.emit(img_copy, frame_timestamp, time.perf_counter())
            else:
                time.sleep(0.1) # idle while not connected

        self.disconnect()

# class EbusSerial(QtCore.QRunnable):
#     """
#     Worker thread for the device serial connection.
#     Requests come in via a queue object, and answers come back as Qt Signals.
#     Currently unused, since I realized that I can just poll the answers on a timer...
#     """
#     def __init__(self, request_queue):
#         super().__init__()
#         self.request_queue = request_queue
#         self.signals       = SignalsDefines()

#     def run(self):
#         quit_thread_flag = False
#         while not quit_thread_flag:
#             request = self.request_queue.get()
#             request_id, request_type, request_param = request
#             assert request_type in ['write', 'query', 'read', 'exit']

#             if request_type == 'write':
#                 ebus.writeSerialPort(request_param)
#             if request_type == 'query':
#                 ebus.writeSerialPort(request_param)
#                 self.signals.serialReadComplete.emit(request_id, request_type, request_param, self.readline())
#             elif request_type == 'read':
#                 self.signals.serialReadComplete.emit(request_id, request_type, request_param, self.readline())
#             elif request_type == 'exit':
#                 quit_thread_flag = True

#     def readline(self):
#         """ Read one byte at a time from the serial port until we get a newline character (CR).
#         FIXME: This might not be what we need: see the manual for the camera response format """
#         timeoutMS = 500
#         retval = ''
#         reply = ''
#         while reply != '\r':
#             reply = ebus.readSerialPort(1, timeoutMS)
#             result += reply
#         return retval
