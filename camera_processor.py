import os
import time
from collections import OrderedDict
from importlib import reload
import threading

from PyQt5 import QtCore, QtGui, QtWidgets, uic
import time
import sys

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import cv2

from display_image_widget import DisplayImageWidget
import qt_helpers
import image_processor
import sui_camera_constants as camera
import ebus_reader
import serial_widget
import scrolling_plot

class CameraProcessor(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        """  """
        super().__init__()
        self.path_to_watch = args[0]

        print("CameraProcessor main thread id: ", threading.get_native_id())

        self.I_accum        = None
        self.N_accum        = 0
        self.N_accum_target = 10
        self.max_val        = 2**16
        self.min_val        = 0
        self.I_subtract     = None
        self.I_avg          = None
        self.file_count     = 0
        
        self.taper_shape_last = None
        self.radius_last      = None
        self.taper_last       = None
        self.window           = None

        self.imgProc = image_processor.ImageProcessor()

        self.ebusReader = ebus_reader.EbusReader(use_mock=True)

        self.reply_buffer = ''

        self.fileWatcher = QtCore.QFileSystemWatcher(["image_processor.py"])
        self.fileWatcher.fileChanged.connect(self.fileWatcher_fileChanged)

        self.setupUI()

        self.registers = {k: None for k in ['EXP', 'FRAME:PERIOD']}

        # start polling timer for the serial reads:
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.pollSerial)
        self.timer_period_ms = 100
        self.timer.start(self.timer_period_ms)

    def pollSerial(self):
        if not self.ebusReader.connected:
            return
        N_TO_READ = 1000 # this must be less than pyebus_main.cpp:RX_BUFFER_SIZE (TODO: add this as a module constant)
        reply = ebus_reader.ebus.readSerialPort(N_TO_READ, 1)
        if reply != '':
            print(repr(reply))
            self.serialWidget.editConsole.appendPlainText(reply)
            self.reply_buffer += reply
            self.splitSerialTextInLines()

    def splitSerialTextInLines(self):
        pos = self.reply_buffer.find('\r')
        while pos != -1:
            full_line = self.reply_buffer[:pos+1]
            self.parseSerialOutput(full_line)
            self.reply_buffer = self.reply_buffer[pos+1:]
            
            pos = self.reply_buffer.find('\r')

    def parseSerialOutput(self, line):
        """ Called whenever the device replies one full line on its serial port.
        Will parse out relevant info and display them in the GUI """
        for reg_name in self.registers.keys():
            header = reg_name + ' '
            if line.startswith(header):
                value = int(line[len(header):])
                self.registers[reg_name] = value
                self.registersUpdated()

    def editExposureCount_editingFinished(self):
        try:
            user_val = int(round(float(eval(self.editExposureCount.text()))))
        except:
            return

        EXP_register = user_val - camera.EXP_OFFSET
        ebus_reader.ebus.writeSerialPort('EXP %d\r' % EXP_register)

    def registersUpdated(self):
        """ Called when the serial communication shows a new value of a register.
        Updates our internal values and GUI """
        try:
            user_val = int(round(float(eval(self.editExposureCount.text()))))
        except:
            user_val = 0

        self.lblExposureMSRequested.setText('%.3f ms' % (1e3*camera.countsToSeconds(user_val)))
        self.lblExposureMSActual.setText(   '%.3f ms' % (1e3*camera.countsToSeconds(self.registers['EXP'] + camera.EXP_OFFSET)))
        self.lblExposureCounts.setText(                                         str(self.registers['EXP'] + camera.EXP_OFFSET))

    def fileWatcher_fileChanged(self, path):
        print("fileWatcher_fileChanged: %s" % path)
        old_obj = self.imgProc
        reload(image_processor)
        new_obj = image_processor.ImageProcessor()
        # copy all attributes of the old object to the new one, except builtins or callables of course
        for attr_name in dir(old_obj):
            attr = getattr(old_obj, attr_name)
            if not attr_name.startswith('__') and not callable(attr):
                print("copying attribute '%s'" % attr_name)
                setattr(new_obj, attr_name, attr)
        self.imgProc = new_obj

    def setupUI(self):
        uic.loadUi("main.ui", self)
        self.createStatusBar()

        self.w = DisplayImageWidget()
        self.w.resize(600, 600)
        self.w.setWindowTitle('IR Camera Image')
        self.w.show()

        self.serialWidget = serial_widget.SerialWidget()
        self.serialWidget.move(50, 200)
        self.serialWidget.show()

        self.scrollingPlot = scrolling_plot.ScrollingPlot()
        self.editFramesInScrolling_editingFinished()
        self.scrollingPlot.show()

        hbox = self.centralWidget().layout()
        # hbox.addWidget(self.w)

        self.editN_editingFinished()

        connections_list = qt_helpers.connect_signals_to_slots(self)
        self.setWindowTitle('eBUS Camera Processor')
        self.resize(600, 600)

    def editFramesInScrolling_editingFinished(self):
        try:
            N = int(round(float(eval(self.editFramesInScrolling.text()))))
            self.scrollingPlot.updateXspan(N)
        except:
            pass

    def createStatusBar(self):
        self.status_bar_fields = OrderedDict()
        self.status_bar_fields["filename"] = QtWidgets.QLabel('')
        self.status_bar_fields["pb"] = QtWidgets.QProgressBar()

        # self.statusBar = QtWidgets.QStatusBar()
        for k, w in self.status_bar_fields.items():
            if k == "spacer":
                stretch = 1
            else:
                stretch = 0
            self.statusBar().addPermanentWidget(w, stretch)

    # def setupWorkerThreads(self, *args, **kwargs):
    #     self.workers = list()
    #     self.workers.append(DirectoryWatcherWorker(*args, **kwargs))
    #     self.workers[-1].signals.newFile.connect(self.newFile)
    #     # from https://stackoverflow.com/a/60977476
    #     threadpool = QtCore.QThreadPool.globalInstance()
    #     threadpool.start(self.workers[-1])

    def btnConnect_clicked(self):
        # from https://stackoverflow.com/a/60977476
        id_list = self.ebusReader.list_devices()
        if len(id_list) > 1:
            print("TODO: implement device selection instead of connecting to the first one available")
        self.ebusReader.connect(id_list[0])
        self.ebusReader.signals.newImage.connect(self.newImage)

        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self.ebusReader)

    def btnDisconnect_clicked(self):
        self.ebusReader.stop()

    def editMin_editingFinished(self):
        self.updateMinMax()

    def editMax_editingFinished(self):
        self.updateMinMax()

    def chkAvg_clicked(self):
        self.editN_editingFinished()

    def editN_editingFinished(self):
        if self.chkAvg.isChecked():
            N = int(float(eval(self.editN.text())))
        else:
            N = 1
        if N > 0:
            self.N_accum_target = N
            self.status_bar_fields["pb"].setMaximum(self.N_accum_target)
            self.status_bar_fields["pb"].setFormat('%%v/%d' % self.N_accum_target)

    def btnBck_clicked(self):
        self.I_subtract = self.I_avg
        self.showAvg()

    def updateMinMax(self):
        self.min_val = int(float(eval(self.editMin.text())))
        self.max_val = int(float(eval(self.editMax.text())))
        self.showAvg()

    def computeWindowFunction(self, img_shape, radius, taper):
        # only recompute window if it has changed:
        if self.taper_shape_last == img_shape and self.radius_last == self.radius and self.taper_last == self.taper:
            return

        N = img_shape[0]
        y_dist, x_dist = np.meshgrid(np.arange(N)+0.5-N/2, np.arange(N)+0.5-N/2)
        distance_to_center = np.sqrt(x_dist*x_dist + y_dist*y_dist)
        in_center_logical = (distance_to_center < self.radius)
        in_taper_logical = np.logical_and(self.radius <= distance_to_center, distance_to_center <= self.radius+self.taper)
        self.window = 1.0*in_center_logical
        if self.taper != 0:
            self.window += in_taper_logical * 0.5 * (1.0 + np.cos(np.pi * ((distance_to_center-self.radius)/self.taper)))

        self.taper_shape_last = img_shape
        self.radius_last      = self.radius
        self.taper_last       = self.taper

    def newImage(self, img):
        if self.chkROI.isChecked():
            try:
                xy_str = self.editROIcenter.text().split(',')
                if len(xy_str) == 2:
                    xcenter = int(xy_str[0])
                    ycenter = int(xy_str[1])
                    radius  = int(self.editROIradius.text())//2
                    taper   = int(self.editROItaper.text())//2
                    d_half = int((radius + taper))
                    # apply ROI by croppping
                    img = img[ycenter-d_half:ycenter+d_half, xcenter-d_half:xcenter+d_half]
                    # apply tapered window/weighting function:
                    self.computeWindowFunction(img.shape, radius, taper) # recompute if needed
                    img = img * self.window
            except:
                # we simply don't apply the ROI if it's wrong
                pass
        img = self.imgProc.run(img)
        if img is not None:
            self.accum(img)

    def accum(self, I_uint16):
        if self.I_accum is None or self.N_accum == 0:
            self.accumInit(I_uint16)

        if I_uint16.dtype != np.uint16 and self.I_accum.dtype == np.int64:
            self.I_accum.dtype = np.float64
        self.I_accum += I_uint16
        self.N_accum += 1

        if self.N_accum <= self.status_bar_fields["pb"].maximum():
            self.status_bar_fields["pb"].setValue(self.N_accum)

        if self.N_accum >= self.N_accum_target:
            self.I_avg = self.I_accum/self.N_accum
            self.showAvg()
            self.accumInit(I_uint16)

    def accumInit(self, I_uint16):
        self.I_accum = np.zeros(I_uint16.shape[0:2], dtype=np.int64)
        self.N_accum = 0

    def showAvg(self):
        bits_out_display = 8

        if self.chkSubtract.isChecked() and self.I_subtract is not None:
            I_subtracted = self.I_avg - self.I_subtract
        else:
            I_subtracted = self.I_avg

        I = (I_subtracted - self.min_val) * (2**bits_out_display-1)/(self.max_val-self.min_val)

        np.clip(I, 0, 2**bits_out_display-1, out=I)
        I_uint8 = I.astype(np.uint8)
        I_rgb = cv2.cvtColor(I_uint8, cv2.COLOR_GRAY2RGB)
        self.w.update_image(I_rgb)
        self.w.update()

        self.scrollingPlot.newPoint(np.sum(self.I_avg))

    def saveAvgImg(self):
        bits_out_save = 16
        I_save = np.clip(self.I_avg, 0, (2**bits_out_save-1))
        I_save = I_save.astype(np.uint16)
        self.file_count += 1
        out_filename = 'images\\avg_%08d.tiff' % self.file_count
        plt.imsave(out_filename, I_save)

    def closeEvent(self, event):
        print("closeEvent")
        self.ebusReader.stop()
        self.timer.stop()
        self.serialWidget.close()
        self.w.close()
        self.scrollingPlot.close()
        event.accept()


    # def startTestMode(self):
    #     # this generates fake data based on a timer, for testing purposes:
    #     self.testIteration = 0
    #     self.timer = QtCore.QTimer()
    #     self.timer.timeout.connect(self.testModeUpdate)
    #     self.timer_period_ms = 100
    #     self.timer.start(self.timer_period_ms)
    #     self.testModeUpdate()

    # def testModeUpdate(self):
    #     # generate a new image, save to disk
    #     filename = os.path.join(self.path_to_watch, 'test%d.tiff' % self.testIteration)
        
    #     data = np.zeros((600, 600), dtype=np.uint16)
    #     N_pixels = 10
    #     self.testIteration += N_pixels
    #     if self.testIteration+N_pixels > data.shape[1]:
    #         self.testIteration = 0
    #     data[0:N_pixels, self.testIteration:(self.testIteration+N_pixels)] = 2**15
    #     im = Image.fromarray(data)
    #     im.save(filename)


def main():

    path_to_watch = "d:\\"
    target_size = 655534

    app = QtWidgets.QApplication(sys.argv)
    gui = CameraProcessor(path_to_watch, target_size)
    gui.show()
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        gui.startTestMode()
    app.exec_()

if __name__ == '__main__':
    main()

    # python D:\Repo\CameraProcess\camera_processor.py test

