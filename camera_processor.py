import os
import time
from collections import OrderedDict

import win32file
import win32con

from PyQt5 import QtCore, QtGui, QtWidgets, uic
import time
import sys

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import cv2

from display_image_widget import DisplayImageWidget
from check_for_changes import DirectoryWatcherWorker


class CameraProcessor(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        """  """
        super().__init__()
        self.setupWorkerThread(*args, **kwargs)
        self.path_to_watch = args[0]

        self.I_accum        = None
        self.N_accum        = 0
        self.N_accum_target = 10
        self.max_val        = 2**16
        self.min_val        = 0

        self.setupUI()



    def setupUI(self):
        self.createStatusBar()

        self.w = DisplayImageWidget()
        self.w.resize(600, 600)

        # self.hbox = QtWidgets.QHBoxLayout()
        # self.hbox.addWidget(self.w)

        # self.setLayout(self.hbox)
        self.setCentralWidget(self.w)
        self.resize(600, 600)

    def createStatusBar(self):
        self.status_bar_fields = OrderedDict()
        self.status_bar_fields["filename"] = QtWidgets.QLabel('')
        self.status_bar_fields["pb"] = QtWidgets.QProgressBar()
        self.status_bar_fields["pb"].setMaximum(self.N_accum_target)
        self.status_bar_fields["pb"].setFormat('%%v/%d' % self.N_accum_target)

        # self.statusBar = QtWidgets.QStatusBar()
        for k, w in self.status_bar_fields.items():
            if k == "spacer":
                stretch = 1
            else:
                stretch = 0
            self.statusBar().addPermanentWidget(w, stretch)

    def setupWorkerThread(self, *args, **kwargs):
        self.worker = DirectoryWatcherWorker(*args, **kwargs)
        self.worker.signals.newFile.connect(self.newFile)
        # from https://stackoverflow.com/a/60977476
        threadpool = QtCore.QThreadPool.globalInstance()
        print("Multithreading with maximum %d threads" % threadpool.maxThreadCount())
        threadpool.start(self.worker)

    def accum(self, I_uint16):
        if self.I_accum is None or self.N_accum == 0:
            self.accumInit(I_uint16)

        self.I_accum += I_uint16
        self.N_accum += 1

        self.status_bar_fields["pb"].setValue(self.N_accum)

        if self.N_accum == self.N_accum_target:
            self.showAccum()
            self.accumInit(I_uint16)

    def accumInit(self, I_uint16):
        self.I_accum = np.zeros(I_uint16.shape[0:2], dtype=np.int64)
        self.N_accum = 0

    def showAccum(self):
        if self.N_accum == 0:
            return

        bits_out = 8
        self.I_avg = self.I_accum/self.N_accum
        I = (self.I_avg - self.min_val) * (2**bits_out-1)/(self.max_val-self.min_val)

        np.clip(I, 0, 2**bits_out-1, out=I)
        I_uint8 = I.astype(np.uint8)
        I_rgb = cv2.cvtColor(I_uint8, cv2.COLOR_GRAY2RGB)
        self.w.update_image(I_rgb)
        self.w.update()

    @QtCore.pyqtSlot(object)
    def newFile(self, filename):
        print("new file: %s" % filename)
        try:
            I = plt.imread(filename)
            self.status_bar_fields["filename"].setText(os.path.basename(filename))
        except FileNotFoundError:
            return
        self.accum(I)
        # self.showAccum()

        # print(I.shape)
        # print(I.dtype)
        # print(cv2.COLOR_GRAY2RGB)
        # I = (I/2**(16-8)).astype(np.uint8)
        # I_rgb = cv2.cvtColor(I, cv2.COLOR_GRAY2RGB)
        # self.w.update_image(I_rgb)
        # self.w.update()


        os.remove(filename)
        # try:
        #     I = plt.imread(filename)
        #     self.w.update_image(I)
        #     # self.w.load_image_from_file(filename, use_opencv=True)
        #     self.w.update()
        #     os.remove(filename)
        # except Exception as e:
        #     print(e)

    def closeEvent(self, event):
        # print("closeEvent")
        if self.worker is not None:
            self.worker.stop()
        stop_file = os.path.join(self.path_to_watch, "stop.txt")
        if os.path.exists(stop_file):
            os.remove(stop_file)
        with open(stop_file, "w"):
            pass
        os.remove(stop_file)
        event.accept()


    def startTestMode(self):
        # this generates fake data based on a timer, for testing purposes:
        self.testIteration = 0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.testModeUpdate)
        self.timer_period_ms = 100
        self.timer.start(self.timer_period_ms)
        self.testModeUpdate()

    def testModeUpdate(self):
        # generate a new image, save to disk
        filename = os.path.join(self.path_to_watch, 'test%d.tiff' % self.testIteration)
        
        data = np.zeros((600, 600), dtype=np.uint16)
        N_pixels = 10
        self.testIteration += N_pixels
        data[0:N_pixels, self.testIteration:(self.testIteration+N_pixels)] = 2**15
        im = Image.fromarray(data)
        im.save(filename)


def main():

    path_to_watch = "d:\\repo\\CameraProcess\\images"
    target_size = 720122

    app = QtWidgets.QApplication(sys.argv)
    gui = CameraProcessor(path_to_watch, target_size)
    gui.show()
    gui.startTestMode()
    app.exec_()

if __name__ == '__main__':
    main()

    # python D:\Repo\CameraProcess\camera_processor.py

