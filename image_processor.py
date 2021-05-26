import numpy as np
import cv2

class ImageProcessor():

    def __init__(self):
        self.background_subtraction = False
        self.apply_ROI = False

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

    def updateROI(self, apply_ROI, xcenter=None, ycenter=None, radius=None, taper=None):
        self.apply_ROI = apply_ROI
        if apply_ROI:
            self.ROI = (xcenter, ycenter, radius, taper)

    def computeWindowFunction(self, img_shape, radius, taper):
        # only recompute window if it has changed:
        if self.taper_shape_last == img_shape and self.radius_last == radius and self.taper_last == taper:
            return

        N = img_shape[0]
        y_dist, x_dist = np.meshgrid(np.arange(N)+0.5-N/2, np.arange(N)+0.5-N/2)
        distance_to_center = np.sqrt(x_dist*x_dist + y_dist*y_dist)
        in_center_logical = (distance_to_center < radius)
        in_taper_logical = np.logical_and(radius <= distance_to_center, distance_to_center <= radius+taper)
        self.window = 1.0*in_center_logical
        if taper != 0:
            self.window += in_taper_logical * 0.5 * (1.0 + np.cos(np.pi * ((distance_to_center-radius)/taper)))

        self.taper_shape_last = img_shape
        self.radius_last      = radius
        self.taper_last       = taper

    def applyROIandWindowing(self, img):
        if not self.apply_ROI:
            return img
        else:
            try:
                (xcenter, ycenter, radius, taper) = self.ROI
                # apply ROI by croppping
                img = img[ycenter-d_half:ycenter+d_half, xcenter-d_half:xcenter+d_half]
                # apply tapered window/weighting function:
                self.computeWindowFunction(img.shape, radius, taper) # recompute if needed
                img = img * self.window
                return img
            except:
                # we simply don't apply the ROI if it's wrong
                return None

    def newImage(self, img):
        img = self.applyROIandWindowing(img)
        
        if self.accum(img):
            return self.getDisplayImg()
        else:
            return None

    def accum(self, I_uint16):
        """ Accumulates the received image in our buffer.
        Returns True if the averaged image was updated. """
        if self.I_accum is None or self.N_accum == 0 or self.I_accum.shape != I_uint16.shape:
            self.accumInit(I_uint16)

        if I_uint16.dtype != np.uint16 and self.I_accum.dtype == np.int64:
            # fallback to accumulating in floats if the images have been transformed already
            self.I_accum.dtype = np.float64

        self.I_accum += I_uint16
        self.N_accum += 1
        self.N_progress = self.N_accum

        if self.N_accum >= self.N_accum_target:
            self.I_avg = self.I_accum/self.N_accum
            self.applySubtraction()
            self.accumInit(I_uint16)
            return True
        else:
            return False

    def accumInit(self, I_uint16):
        """ Reset our image accumulator """
        self.I_accum = np.zeros(I_uint16.shape[0:2], dtype=np.int64)
        self.N_accum = 0

    def applySubtraction(self):
        """ Computes the optionally-subtracted image """
        if self.background_subtraction and self.I_subtract is not None:
            self.I_subtracted = self.I_avg - self.I_subtract
        else:
            self.I_subtracted = self.I_avg

    def getDisplayImg(self):
        """ Returns our averaged image, scaled to the correct format for plotting (RGB888) """
        bits_out_display = 8

        self.applySubtraction()
        I = (self.I_subtracted - self.min_val) * (2**bits_out_display-1)/(self.max_val-self.min_val)

        np.clip(I, 0, 2**bits_out_display-1, out=I)
        I_uint8 = I.astype(np.uint8)
        I_rgb = cv2.cvtColor(I_uint8, cv2.COLOR_GRAY2RGB)
        return I_rgb

    def saveAvgImg(self):
        bits_out_save = 16
        I_save = np.clip(self.I_avg, 0, (2**bits_out_save-1))
        I_save = I_save.astype(np.uint16)
        self.file_count += 1
        out_filename = 'images\\avg_%08d.tiff' % self.file_count
        plt.imsave(out_filename, I_save)
