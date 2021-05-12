import os
import time

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

ACTIONS = {
    1 : "Created",
    2 : "Deleted",
    3 : "Updated",
    4 : "Renamed to something",
    5 : "Renamed from something"
}
# Thanks to Claudio Grondi for the correct set of numbers
FILE_LIST_DIRECTORY = 0x0001

# see https://www.learnpyqt.com/tutorials/multithreading-pyqt-applications-qthreadpool/
# for the particular style of coding up the multithreading using PyQt5:
class SignalsDefines(QtCore.QObject):
    """ this is needed since PyQt requires an object to be a subclass of QObject
    in order to define signals, but QRunnable is not. """
    newFile = QtCore.pyqtSignal(object)

class DirectoryWatcherWorker(QtCore.QRunnable):
    """
    Worker thread
    """
    def __init__(self, path_to_watch, target_size):
        super().__init__()
        self.signals     = SignalsDefines()

        # semaphore used to stop the thread
        self.stop_flag = False

        self.path_to_watch = path_to_watch
        self.target_size = target_size
        
        self.files_to_watch = {}

        self.hDir = win32file.CreateFile (
            self.path_to_watch,
            FILE_LIST_DIRECTORY,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_FLAG_BACKUP_SEMANTICS,
            None
        )

    def stop(self):
        """ call this from the gui thread in order to stop the processing in the worker thread """
        self.stop_flag = True

    @QtCore.pyqtSlot()
    def run(self):
        print("DirectoryWatcherWorker: run()")
        while True:
            if self.stop_flag:
                print("DirectoryWatcherWorker: Received stop flag, thread will close.")
                break
            #
            # ReadDirectoryChangesW takes a previously-created
            # handle to a directory, a buffer size for results,
            # a flag to indicate whether to watch subtrees and
            # a filter of what changes to notify.
            #
            # NB Tim Juchcinski reports that he needed to up
            # the buffer size to be sure of picking up all
            # events when a large number of files were
            # deleted at once.
            #
            results = win32file.ReadDirectoryChangesW (
                self.hDir,
                int(1e6),
                True,
                win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                # win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                # win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                win32con.FILE_NOTIFY_CHANGE_SIZE,
                # win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
                # win32con.FILE_NOTIFY_CHANGE_SECURITY,
                None,
                None
            )
            # print(results)

            for action, file in results:
                if ACTIONS[action] == 'Updated':
                    full_filename = os.path.join(self.path_to_watch, file)
                    self.files_to_watch[full_filename] = 1

            for file in self.files_to_watch:
                try:
                    size = os.path.getsize(file)
                    if size == self.target_size:
                        # print("%s: %d (correct)" % (file, size))
                        self.signals.newFile.emit(file)
                    else:
                        print("%s: %d (incorrect)" % (file, size))

                except OSError as e:
                    if e.errno == 2: # OSError: 2, The system cannot find the file specified
                        continue
                    print("%s: OSError: %d, %s" % (file, e.errno, e.strerror))

        print("DirectoryWatcherWorker: closing down.")


class TestWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        """  """
        super().__init__()
        self.setupWorkerThread(*args, **kwargs)
        self.path_to_watch = args[0]

        self.resize(600, 600)

        self.startTestMode()

    def setupWorkerThread(self, *args, **kwargs):
        self.worker = DirectoryWatcherWorker(*args, **kwargs)
        self.worker.signals.newFile.connect(self.newFile)
        # from https://stackoverflow.com/a/60977476
        threadpool = QtCore.QThreadPool.globalInstance()
        print("Multithreading with maximum %d threads" % threadpool.maxThreadCount())
        threadpool.start(self.worker)

    @QtCore.pyqtSlot(object)
    def newFile(self, filename):
        print("new file: %s" % filename)
        if not os.path.exists(filename):
            return
        # TODO: do something with the file before deleting it
        os.remove(filename)

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
    gui = TestWidget(path_to_watch, target_size)
    gui.show()
    app.exec_()

if __name__ == '__main__':
    main()

    # python D:\Repo\CameraProcess\check_for_changes.py
