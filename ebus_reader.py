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
    newImage = QtCore.pyqtSignal(object)
    serialReadComplete = QtCore.pyqtSignal(int, str, str, str)

class EbusReader(QtCore.QRunnable):
    """
    Worker thread
    """
    def __init__(self, use_mock=False, camera=None):
        super().__init__()
        self.use_mock = use_mock
        self.signals  = SignalsDefines()
        self.stop_flag = False # semaphore used to stop the thread
        self.connected = False
        self.camera = camera # will get called on a connection event

        if self.use_mock:
            ebus.useMock()

    def stop(self):
        """ call this from the gui thread in order to stop the processing in the worker thread """
        self.stop_flag = True

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
        ebus.connectToDevice(device_unique_id)
        ebus.openDeviceSerialPort()
        if self.camera:
            self.camera.on_connected(ebus.writeSerialPort, ebus.readSerialPort)
        # ebus.openStream(device_unique_id)
        # self._createBuffers()
        # ebus.startAcquisition()
        # self.stop_flag = True
        self.connected = True

    def disconnect(self):
        ebus.stopAcquisition()
        ebus.closeStream()
        ebus.releaseBuffers()
        ebus.closeDeviceSerialPort()
        ebus.closeDevice()
        self.connected = False

    def _createBuffers(self):
        (buffer_size, buffer_count) = ebus.getBufferRequirements()
        # allocate "buffer_count" buffers of size "buffer_size"!
        self.buffers = []
        for k in range(buffer_count):
            self.buffers.append(bytearray(buffer_size))
            ebus.addBuffer(self.buffers[-1])

    @QtCore.pyqtSlot()
    def run(self):
        timeoutMS = 1000

        print("ebus reader thread id: ", threading.get_native_id())
        while not self.stop_flag and self.connected:
            # (img_buffer, img_info) = ebus.getImage(timeoutMS)
            # img_np = np.frombuffer(img_buffer, np.uint16)
            # img_copy = img_np.copy() # make a copy so that we can release the ebus buffer for the driver to re-use, while still doing operations on it
            # ebus.releaseImage()

            # if self.stop_flag:
            #     break
            # info = ebus.expand_img_info_tuple(img_info)
            # img_copy = img_copy.reshape(info['Height'], info['Width'])
            # self.signals.newImage.emit(img_copy)
            time.sleep(1)

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
#         stop_flag = False
#         while not stop_flag:
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
#                 stop_flag = True

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
