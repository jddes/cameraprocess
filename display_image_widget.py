from PyQt5 import QtGui, QtCore, QtWidgets
import sys

import numpy as np
import cv2

# adapted to my needs starting from https://stackoverflow.com/a/57209821
class DisplayImageWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ROI = None
        self.qimg = None
        self.displayed_qimg = None

    def setTransform(self, painter):
        pass # just exists so that we can override this later in a subclass

    def getTargetRatio(self):
        """ Returns the target image ratio to fill the most-limiting widget dimension,
        without changing the aspect ratio of the image """
        width_ratio  = self.width()/self.displayed_qimg.width()
        height_ratio = self.height()/self.displayed_qimg.height()
        return min(width_ratio, height_ratio)

    def getTargetRect(self):
        """ Returns the target image size to fill the most-limiting widget dimension,
        without changing the aspect ratio of the image """
        scale_ratio = self.getTargetRatio()

        target_width  = scale_ratio*self.displayed_qimg.width()
        target_height = scale_ratio*self.displayed_qimg.height()

        close_enough = lambda x, y : abs(x-y) < 1e-6
        assert close_enough(target_width, self.width()) or close_enough(target_height, self.height()), "assertion failed: one of the target size must be equal to the full window size, otherwise there is a bug in the scaling logic above"

        return QtCore.QRectF(0., 0., target_width, target_height)

    def paintEvent(self, event):
        if self.displayed_qimg is None:
            return

        painter = QtGui.QPainter()
        painter.begin(self)
        self.setTransform(painter) # this will be re-implemented differently in a subclass

        painter.setRenderHint(QtGui.QPainter.Antialiasing, True) # everything looks a bit better with antialiasing
        source = QtCore.QRectF(self.displayed_qimg.rect())
        target = self.getTargetRect()
        painter.drawImage(target, self.displayed_qimg, source)
        painter.end()

    def load_image_from_file(self, filename, use_opencv=True):
        if use_opencv:
            img_mat = cv2.imread(filename)
            if img_mat is None:
                raise Exception("load_image_from_file() error: image file %s could not be loaded via opencv (does the file exist?)\n" % filename)
            self.update_image(img_mat)

        else:
            # load using Qt directly:
            qimg = QtGui.QImage(filename)
            if qimg.isNull():
                raise Exception("load_image_from_file() error: image file %s could not be loaded via Qt (does the file exist?)\n" % filename)
            self.update_image(qimg)

    def update_image(self, img):
        """ img must implement either the same interface as an opencv "cv::Mat" object, or a "PyQt5.QtGui.QImage" object """
        if isinstance(img, np.ndarray):
            # img could be an opencv::Mat: need to do additional conversions
            self.qimg = QtGui.QImage(img.data, img.shape[1], img.shape[0], QtGui.QImage.Format_RGB888).rgbSwapped()
        else:
            self.qimg = img # assume that this is a qimg (duck-typing)

        self.update_displayed_image()

    def setDisplayROI(self, left, bottom, width, height):
        self.ROI = (left, bottom, width, height)
        self.ROI = (int(x) for x in self.ROI)
        self.update_displayed_image()

    def update_displayed_image(self):
        """ Sets the displayed image from the full image,
        handling the optional region-of-interest feature """
        if self.ROI is None:
            # easy case, displayed image is simply the full image
            self.displayed_qimg = self.qimg
        else:
            # implement minimal ROI feature:
            (left, bottom, width, height) = self.ROI
            self.displayed_qimg = self.qimg.copy(left, bottom, width, height)

def setupTestImageWidget(w):
    w.load_image_from_file(filename='placeholder4.PNG', use_opencv=True)
    w.resize(600, 600)
    w.show()

def testDisplayImageWidget():
    w = DisplayImageWidget()
    # w.setDisplayROI(left=100, bottom=0, width=10, height=50)
    setupTestImageWidget(w)
    return w

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = testDisplayImageWidget()
    # w2 = testAnnotatedImageWidget()
    # w3 = testImageWithROIselectors()
    # w4 = testZoomedImageWidget()

    sys.exit(app.exec_())
