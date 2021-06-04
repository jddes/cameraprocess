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
        
        self.window_params_last = None

    def updateROI(self, apply_ROI, xcenter=None, ycenter=None, radius=None, taper=None):
        self.apply_ROI = apply_ROI
        if apply_ROI:
            self.ROI = (xcenter, ycenter, radius, taper)

    def computeWindowFunction(self, ycenter, ymin, ymax, xcenter, xmin, xmax, radius, taper):
        """ Computes the window only if it has changed since last call """
        if self.window_params_last == (ymin, ymax, xmin, xmax, radius, taper):
            return

        y_dist, x_dist = np.meshgrid(np.arange(xmin, xmax)-xcenter, np.arange(ymin, ymax)-ycenter)

        distance_to_center = np.sqrt(x_dist*x_dist + y_dist*y_dist)
        in_center_logical = (distance_to_center < radius)
        in_taper_logical = np.logical_and(radius <= distance_to_center, distance_to_center <= radius+taper)
        self.window = 1.0*in_center_logical
        if taper != 0:
            self.window += in_taper_logical * 0.5 * (1.0 + np.cos(np.pi * ((distance_to_center-radius)/taper)))

        self.window_params_last = (ycenter, ymin, ymax, xcenter, xmin, xmax, radius, taper)

    def applyROIandWindowing(self, img):
        if not self.apply_ROI:
            return img
        else:
            if 1:#  try:
                (xcenter, ycenter, radius, taper) = self.ROI
                full_radius = int((radius + taper))
                ymin = int(max(0, ycenter-full_radius))
                ymax = int(min(ycenter+full_radius, img.shape[0]-1))
                xmin = int(max(0, xcenter-full_radius))
                xmax = int(min(xcenter+full_radius, img.shape[1]-1))
                # apply ROI by croppping
                cropped_img = img[ymin:ymax, xmin:xmax]
                if 0 in cropped_img.shape:
                    return img # invalid region, with one empty dimension
                # apply tapered window/weighting function:
                self.computeWindowFunction(ycenter, ymin, ymax, xcenter, xmin, xmax, radius, taper) # recomputes only if needed
                # cropped_img = cropped_img * self.window
                return cropped_img
            # except:
            #     # we simply don't apply the ROI if it's wrong
            #     return None

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
        # print('np.min(self.I_subtracted)=', np.min(self.I_subtracted))
        # print('self.min_val=', self.min_val)
        # print('np.max(self.I_subtracted)=', np.max(self.I_subtracted))
        # print('self.max_val=', self.max_val)
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

    def getColor(self, colorName):
        color_dict = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (0xff, 0xd7, 0x0),
        }
        return color_dict.get(colorName, color_dict['red'])

    def getLineIndices(self, img_shape, x1, y1, x2, y2):
        """ returns the x and y indices of a line from (x1, y1) to (x2, y2) """
        length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
        t = np.linspace(0, 1, int(round(2*length)))
        x = np.round(t * x1 + (1-t)*x2).astype(np.uint32)
        y = np.round(t * y1 + (1-t)*y2).astype(np.uint32)
        x = x[np.logical_and(x >= 0, x <= img_shape[0])]
        y = y[np.logical_and(y >= 0, y <= img_shape[1])]
        return (x, y)

    def getCircleIndices(self, img_shape, x1, y1, diameter):
        """ returns the x and y indices of a circle centered on (x1, y1) with the given diameter """
        length = diameter * np.pi
        t = np.linspace(0, 2*np.pi, int(round(2*length)))
        x = np.round(x1 + diameter/2*np.cos(t)).astype(np.uint32)
        y = np.round(y1 + diameter/2*np.sin(t)).astype(np.uint32)
        x = x[np.logical_and(x >= 0, x <= img_shape[0])]
        y = y[np.logical_and(y >= 0, y <= img_shape[1])]
        return (x, y)

    def parseAnnotationsCommands(self, text, img_shape):
        """ Adds annotations to an image, described via a simple domain-specific language.
        One command per line, # can be used to indicate comments, list of commands:
        crosshair x y [length]
        circle x y diameter
        line x1 y1 x2 y2 
        color color_name
        color r g b
        colorname can be 'black, white, red, green, blue, yellow'"""
        default_crosshair_size = max(10, np.min(img_shape) * 0.02)

        self.annotations = list()
        color = self.getColor('yellow')
        for line_with_comments in text.split('\n'):
            ind = line_with_comments.find('#')
            if ind != -1:
                line = line_with_comments[:ind-1].strip()
            else:
                line = line_with_comments

            if line.startswith('color'):
                print('color')
                _, *rest = line.split(' ')
                if len(rest) == 1:
                    color = self.getColor(rest[0]) # named color
                elif len(rest) == 3:
                    color = (int(float(s)) for s in rest) # rgb tuple

            if line.startswith('crosshair'):
                args = [float(s) for s in line.split(' ')[1:]]
                if len(args) == 2:
                    # no size specified, use default:
                    args += (default_crosshair_size, )
                self.annotations.append((self.getLineIndices(img_shape, args[0]-args[2]/2, args[1], args[0]+args[2]/2, args[1]), color))
                self.annotations.append((self.getLineIndices(img_shape, args[0], args[1]-args[2]/2, args[0], args[1]+args[2]/2), color))

            if line.startswith('line'):
                args = [float(s) for s in line.split(' ')[1:]]
                self.annotations.append((self.getLineIndices(img_shape, *args), color))


            if line.startswith('circle'):
                args = [float(s) for s in line.split(' ')[1:]]
                self.annotations.append((self.getCircleIndices(img_shape, *args), color))

        print(self.annotations)

    def addAnnotations(self, img):
        """ Adds annotations to an image, added via parseAnnotationsCommands() """
        for (indices, color) in self.annotations:
            try:
                for color_index, color_component in enumerate(color):
                    img[indices[1], indices[0], color_index] = color_component
            except IndexError: # we get this if the image size changed since the annotations were calculated, for example if the user activates software ROI
                pass
