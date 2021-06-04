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
import histogram_plot_widget

class CameraProcessor(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        """  """
        super().__init__()
        self.path_to_watch = args[0]

        print("CameraProcessor main thread id: ", threading.get_native_id())

        self.frame_timestamps = np.zeros(1000)
        self.cpu_timestamps = np.zeros(1000)
        self.ind_stamp = 0
        with open("frame_timestamps.bin", "wb") as f:
            pass
        with open("cpu_timestamps.bin", "wb") as f:
            pass
        print('Cleared timestamps file')

        self.imgProc = image_processor.ImageProcessor()
        self.imgProcPlugin = image_processor_plugin.ImageProcessor()
        self.camera = sui_camera.SUICamera()

        self.ebusReader = ebus_reader.EbusReader(use_mock=False, camera=self.camera)

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

        for w in [self.editPixelPitch, self.editTargetDistance, self.editResolution, self.editFocalLength]:
            w.editingFinished.connect(self.updateFOV)

        # start polling timer for the serial reads:
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.pollSerial)
        self.timer_period_ms = 100
        self.timer.start(self.timer_period_ms)

        # start the image reader thread:
        # it will actually sit idle until we actually connect and open a stream:
        self.startImageReadoutThread()

    def updateFOV(self):
        try:
            PixelPitch = 1e-6*float(eval(self.editPixelPitch.text()))
            TargetDistance = float(eval(self.editTargetDistance.text()))
            FocalLength = float(eval(self.editFocalLength.text()))
            ResolutionX = float(eval(self.editResolution.text().split('x')[0]))
            ResolutionY = float(eval(self.editResolution.text().split('x')[1]))

            FOVradiansX = np.arctan(ResolutionX * PixelPitch / FocalLength)
            FOVradiansY = np.arctan(ResolutionY * PixelPitch / FocalLength)
            FOVmetersX = TargetDistance*np.sin(FOVradiansX)
            FOVmetersY = TargetDistance*np.sin(FOVradiansY)
            self.lblFOVradians.setText("%.2fx%.2f" % (1e3*FOVradiansX, 1e3*FOVradiansY))
            self.lblFOVmeters.setText("%.1fx%.1f" % (FOVmetersX, FOVmetersY))
        except:
            pass

    def pollSerial(self):
        if not self.ebusReader.connected:
            return
        N_TO_READ = 1000 # this must be less than pyebus_main.cpp:RX_BUFFER_SIZE (TODO: add this as a module constant)
        reply = ebus_reader.ebus.readSerialPort(N_TO_READ, 1)
        if reply == '':
            return

        print(repr(reply))
        self.serialWidget.editConsole.appendPlainText(repr(reply))
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
        self.w.move(444, 22)
        self.w.resize(640, 512)
        self.w.setWindowTitle('IR Camera Image')
        self.w.show()

        self.serialWidget = serial_widget.SerialWidget()
        self.serialWidget.editPrompt.returnPressed.connect(self.sendSerial)
        self.serialWidget.move(1229, 20)
        self.serialWidget.show()

        self.scrollingPlot = scrolling_plot.ScrollingPlot()
        self.editFramesInScrolling_editingFinished()
        self.scrollingPlot.resize(760, 305)
        self.scrollingPlot.move(444, 661)
        self.scrollingPlot.show()

        # self.histogram = histogram_plot_widget.HistogramPlotWidget()
        # self.histogram.resize(500, 150)
        # self.histogram.move(0, 100)
        # self.histogram.show()

        hbox = self.centralWidget().layout()
        # hbox.addWidget(self.w)

        self.editN_editingFinished()
        self.chkSubtract_stateChanged()
        self.updateConnectionState()
        self.updateFOV()

        connections_list = qt_helpers.connect_signals_to_slots(self)
        self.setWindowTitle('eBUS Camera Processor')
        self.move(37, 22)

    def sendSerial(self):
        text = self.serialWidget.editPrompt.text() + '\r'
        ebus_reader.ebus.writeSerialPort(text)

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
        id_list = self.ebusReader.list_devices()
        if len(id_list) > 1:
            print("TODO: implement device selection instead of connecting to the first one available")
        if len(id_list) == 0:
            print("Error: could not find a camera device to connect to. Will use the mock device")
            ebus_reader.ebus.useMock()
            id_list = self.ebusReader.list_devices()
        self.ebusReader.connect(id_list[0])

        self.updateConnectionState()

    def startImageReadoutThread(self):
        self.ebusReader.signals.newImage.connect(self.newImage)

        threadpool = QtCore.QThreadPool.globalInstance()
        threadpool.start(self.ebusReader)

    def btnOpenStream_clicked(self):
        # try:
        if 1:
            Width = int(round(float(eval(self.editResolution.text().split('x')[0]))))
            Height = int(round(float(eval(self.editResolution.text().split('x')[1]))))
            X1 = int(round(float(eval(self.editXYoffset.text().split(',')[0]))))
            Y1 = int(round(float(eval(self.editXYoffset.text().split(',')[0]))))
            X2 = X1 + Width  - 1
            Y2 = Y1 + Height - 1
            result = self.camera.setupWindowing(X1, Y1, X2, Y2)
            if result is None:
                # values were too far off to correct, just ignore
                return
            (resolution_dict, X1, Y1, X2, Y2) = result
            self.editXYoffset.setText('%d, %d' % (X1, Y1))
            self.editResolution.setText('%dx%d' % (X2-X1+1, Y2-Y1+1))

            self.ebusReader.openStream(resolution_dict)
            self.updateConnectionState()
            self.last_frame_stamp = None
            self.dropped_frames = 0

        # except:
        else:
            pass

    def btnCloseStream_clicked(self):
        self.ebusReader.closeStream()
        self.updateConnectionState()

    def btnDisconnect_clicked(self):
        self.ebusReader.disconnect()
        self.updateConnectionState()

    def updateConnectionState(self):
        """ Enables/disables GUI elements to prevent trying to change states in an unsupported way
        by either the camera/framegrabber, or our GUI """
        if not self.ebusReader.connected:
            self.btnConnect.setEnabled(True)
            self.btnDisconnect.setEnabled(False)
            for w in [self.btnOpenStream, self.btnCloseStream]:
                w.setEnabled(False)

            for w in [self.editResolution, self.editXYoffset]:
                w.setEnabled(True)
        else:
            self.btnConnect.setEnabled(False)
            self.btnDisconnect.setEnabled(True)
            if self.ebusReader.streamOpened:
                self.btnOpenStream.setEnabled(False)
                self.btnCloseStream.setEnabled(True)
                for w in [self.editResolution, self.editXYoffset]:
                    w.setEnabled(False)
            else:
                self.btnOpenStream.setEnabled(True)
                self.btnCloseStream.setEnabled(False)
            for w in [self.editResolution, self.editXYoffset]:
                w.setEnabled(True)

    def btnAutoscale_clicked(self):
        self.editADCblack.setText(self.lblMinADC.text().strip('%'))
        self.editADCwhite.setText(self.lblMaxADC.text().strip('%'))
        self.updateMinMax()

    def editADCblack_editingFinished(self):
        self.updateMinMax()

    def editADCwhite_editingFinished(self):
        self.updateMinMax()

    def updateMinMax(self):
        conv_func = lambda x: int(x/100 * (2**self.camera.BPP_DATASTREAM-1))
        self.imgProc.min_val = conv_func(float(eval(self.editADCblack.text())))
        self.imgProc.max_val = conv_func(float(eval(self.editADCwhite.text())))
        try:
            self.updateDisplayedImage()
        except TypeError:
            pass

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

    def logTimestamps(self, frame_timestamp):
        self.frame_timestamps[self.ind_stamp] = frame_timestamp
        self.cpu_timestamps[self.ind_stamp] = time.perf_counter()
        self.ind_stamp += 1

        if self.ind_stamp >= len(self.frame_timestamps):
            self.ind_stamp = 0
            with open("frame_timestamps.bin", "ab") as f:
                f.write(self.frame_timestamps.tobytes())
            with open("cpu_timestamps.bin", "ab") as f:
                f.write(self.cpu_timestamps.tobytes())
            print('Saved 1000 timestamps')

    def checkDroppedFrames(self, frame_timestamp):
        if self.last_frame_stamp == None:
            self.last_frame_stamp = frame_timestamp
            self.dropped_frames = 0
            self.lblDroppedFrames.setText('0')
            return

        frames_increments = (int(frame_timestamp) - int(self.last_frame_stamp)) % 2**self.camera.BPP_DATASTREAM
        self.last_frame_stamp = frame_timestamp
        if frames_increments != 1:
            self.dropped_frames += frames_increments-1
            self.lblDroppedFrames.setText('%d' % self.dropped_frames)

    @QtCore.pyqtSlot(object, object, object)
    def newImage(self, img, frame_timestamp, cpu_img_send_timestamp):
        """ Receives a raw image from the ebus reader, sends it through the processing pipeline,
        and updates the various displays from the processed result. """
        # self.histogram.updateData(img) # too slow! need something else (in C++? or just live with min/max?)
        # self.logTimestamps(frame_timestamp)
        self.checkDroppedFrames(frame_timestamp)
        conv_func = lambda x : 100./(2.0**self.camera.BPP_DATASTREAM-1) * x
        self.lblMinADC.setText('%.1f%%' % (conv_func(np.min(img))))
        self.lblMaxADC.setText('%.1f%%' % (conv_func(np.max(img))))

        processedImage = self.imgProc.newImage(self.imgProcPlugin.run(img))
        self.lblProcessingLatency.setText('%.1f ms' % (1e3*(time.perf_counter()-cpu_img_send_timestamp)))

        if self.imgProc.N_progress <= self.status_bar_fields["pb"].maximum():
            self.status_bar_fields["pb"].setValue(self.imgProc.N_progress)

        if processedImage is not None:
            self.processedImage = processedImage
            if not hasattr(self.imgProc, 'annotations'):
                self.btnCommitAnnotations_clicked() # parse the annotations at the first image
            self.imgProc.addAnnotations(self.processedImage)
            self.updateDisplayedImage(self.processedImage)
            self.scrollingPlot.newPoint(self.camera.convertADCcountsToWatts(np.sum(self.imgProc.I_subtracted)))

    def updateDisplayedImage(self, img=None):
        if img is None:
            img = self.imgProc.getDisplayImg()
        self.w.update_image(img)
        self.w.update()

    def closeEvent(self, event):
        print("closeEvent")
        self.ebusReader.quitThread()
        self.ebusReader.disconnect()
        self.timer.stop()
        self.serialWidget.close()
        self.w.close()
        self.scrollingPlot.close()
        # self.histogram.close()
        event.accept()

    def btnCommitAnnotations_clicked(self):
        text = self.editAnnotations.toPlainText()
        self.imgProc.parseAnnotationsCommands(text, self.processedImage.shape[0:2]) # image is MxNx3 due to RGB

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

