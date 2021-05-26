import os
import time
from collections import OrderedDict
from importlib import reload
import threading

from PyQt5 import QtCore, QtGui, QtWidgets, uic
import time
import sys

import numpy as np

from display_image_widget import DisplayImageWidget
import qt_helpers
import image_processor
import image_processor_plugin
import sui_camera
import ebus_reader
import serial_widget
import scrolling_plot

class CameraProcessor(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        """  """
        super().__init__()
        self.path_to_watch = args[0]

        print("CameraProcessor main thread id: ", threading.get_native_id())

        self.imgProc = image_processor.ImageProcessor()
        self.imgProcPlugin = image_processor_plugin.ImageProcessor()
        self.camera = sui_camera.SUICamera()

        self.ebusReader = ebus_reader.EbusReader(use_mock=True, camera=self.camera)

        self.fileWatcher = QtCore.QFileSystemWatcher(["image_processor_plugin.py"])
        self.fileWatcher.fileChanged.connect(self.fileWatcher_fileChanged)

        self.setupUI()

        self.widgets_exposure = {
            'requestedCounts': self.editExposureCount,
            'requestedMS':     self.lblExposureMSRequested,
            'actualMS':        self.lblExposureMSActual,
            'actualCounts':    self.lblExposureCounts,
        }
        self.widgets_frameperiod = {
            'requestedCounts': self.editFrameCount,
            'requestedMS':     self.lblFrameMSRequested,
            'actualMS':        self.lblFrameMSActual,
            'actualCounts':    self.lblFrameCounts,
        }

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
        if reply == '':
            return

        print(repr(reply))
        self.serialWidget.editConsole.appendPlainText(reply)
        if self.camera.newSerialData(reply):
            self.registersUpdated()

    def editExposureCount_editingFinished(self):
        user_val = int(round(float(eval(self.editExposureCount.text()))))
        self.camera.setExposure(user_val)
        try:
            user_val = int(round(float(eval(self.editExposureCount.text()))))
            self.camera.setExposure(user_val)
        except:
            return

    def editFrameCount_editingFinished(self):
        try:
            user_val = int(round(float(eval(self.editFrameCount.text()))))
            self.camera.setFramePeriod(user_val)
        except:
            return

    def registersUpdated(self):
        """ Updates the GUI with the new register values. """
        self.updateLinkedRegistersWidgets(self.widgets_exposure, *self.camera.getExposure())
        self.updateLinkedRegistersWidgets(self.widgets_frameperiod, *self.camera.getFramePeriod())

    def updateLinkedRegistersWidgets(self, widgets, val_counts, val_secs):
        try:
            user_val = int(round(float(eval(widgets['requestedCounts'].text()))))
        except:
            user_val = 0

        widgets['requestedMS'].setText('%.3f ms' % (1e3*self.camera.countsToSeconds(user_val)))
        widgets['actualMS'].setText('%.3f ms' % (1e3*val_secs))
        widgets['actualCounts'].setText(str(val_counts))

    def fileWatcher_fileChanged(self, path):
        print("fileWatcher_fileChanged: %s" % path)
        old_obj = self.imgProcPlugin
        reload(image_processor_plugin)
        new_obj = image_processor_plugin.ImageProcessor()
        # copy all attributes of the old object to the new one, except builtins or callables of course
        for attr_name in dir(old_obj):
            attr = getattr(old_obj, attr_name)
            if not attr_name.startswith('__') and not callable(attr):
                print("copying attribute '%s'" % attr_name)
                setattr(new_obj, attr_name, attr)
        self.imgProcPlugin = new_obj

    def setupUI(self):
        uic.loadUi("main.ui", self)
        self.createStatusBar()

        self.chkROI.stateChanged.connect(self.updateROIparameters)
        for w in [self.editROIcenter, self.editROIradius, self.editROItaper]:
            w.editingFinished.connect(self.updateROIparameters)

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
        self.chkSubtract_stateChanged()

        connections_list = qt_helpers.connect_signals_to_slots(self)
        self.setWindowTitle('eBUS Camera Processor')
        # self.resize(600, 600)

    def chkSubtract_stateChanged(self):
        self.imgProc.background_subtraction = self.chkSubtract.isChecked()

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

    def updateMinMax(self):
        self.imgProc.min_val = int(float(eval(self.editMin.text())))
        self.imgProc.max_val = int(float(eval(self.editMax.text())))
        self.updateDisplayedImage()

    def chkAvg_clicked(self):
        self.editN_editingFinished()

    def editN_editingFinished(self):
        if self.chkAvg.isChecked():
            N = int(float(eval(self.editN.text())))
        else:
            N = 1
        if N > 0:
            self.imgProc.N_accum_target = N
            self.status_bar_fields["pb"].setMaximum(self.imgProc.N_accum_target)
            self.status_bar_fields["pb"].setFormat('%%v/%d' % self.imgProc.N_accum_target)

    def btnBck_clicked(self):
        """ Update the background image that gets subtracted """
        self.imgProc.I_subtract = self.imgProc.I_avg
        self.updateDisplayedImage()

    def updateROIparameters(self):
        if self.chkROI.isChecked():
            try:
                xy_str = self.editROIcenter.text().split(',')
                if len(xy_str) == 2:
                    xcenter = int(xy_str[0])
                    ycenter = int(xy_str[1])
                    radius  = int(self.editROIradius.text())//2
                    taper   = int(self.editROItaper.text())//2
                    self.imgProc.updateROI(True, xcenter, ycenter, radius, taper)
            except:
                pass
        else:
            self.imgProc.updateROI(False)

    @QtCore.pyqtSlot(object)
    def newImage(self, img):
        """ Receives a raw image from the ebus reader, sends it through the processing pipeline,
        and updates the various displays from the processed result. """
        processedImage = self.imgProc.newImage(img)

        if self.imgProc.N_progress <= self.status_bar_fields["pb"].maximum():
            self.status_bar_fields["pb"].setValue(self.imgProc.N_progress)

        if processedImage is not None:
            self.updateDisplayedImage(processedImage)
            self.scrollingPlot.newPoint(np.sum(self.imgProc.I_subtracted))

    def updateDisplayedImage(self, img=None):
        if img is None:
            img = self.imgProc.getDisplayImg()
        self.w.update_image(img)
        self.w.update()

    def closeEvent(self, event):
        print("closeEvent")
        self.ebusReader.stop()
        self.timer.stop()
        self.serialWidget.close()
        self.w.close()
        self.scrollingPlot.close()
        event.accept()

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

