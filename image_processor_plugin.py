# This file is monitored by the GUI code, and will be reloaded automatically on any change,
# a new instance of the ImageProcessor class will be created, and all members from the old
# object will be copied to the new one seamlessly
import numpy as np

class ImageProcessor():
    def run(self, img):
        """ Receives an image to process, must also return an image,
        or None if there is nothing new to display """
        new_img = img # passthrough

        # # autoscale min/max
        # new_img = (new_img-np.min(new_img)).astype(np.float64)
        # new_img = new_img*2**16/np.max(new_img)

        # print("min=", np.min(new_img), "max=", np.max(new_img), "dtype=", new_img.dtype)

        # # example: subtract last frame:
        # if not hasattr(self, 'old_img') or self.old_img.shape != img.shape:
        #     self.old_img = img

        # new_img = img.astype(np.float64) - self.old_img
        # self.old_img = img

        return new_img
