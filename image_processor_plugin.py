# This file is monitored by the GUI code, and will be reloaded automatically on any change,
# a new instance of the ImageProcessor class will be created, and all members from the old
# object will be copied to the new one seamlessly
import numpy as np

class ImageProcessor():
    def run(self, img):
        """ Receives an image to process, must also return an image,
        or None if there is nothing new to display """

        new_img = img # passthrough

        # # example: subtract last frame:
        # if not hasattr(self, 'old_img') or self.old_img.shape != img.shape:
        #     self.old_img = img

        # new_img = img.astype(np.float64) - self.old_img
        # self.old_img = img

        return new_img
