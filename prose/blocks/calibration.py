import numpy as np
from ..core import Block, Image
from .. import utils, viz
import matplotlib.pyplot as plt
from astropy.nddata import Cutout2D
from ..console_utils import info
from time import sleep
from ..utils import register_args
import matplotlib.patches as patches

np.seterr(divide="ignore")


def easy_median(images):
    # To avoid memory errors, we split the median computation in 50
    images = np.array(images)
    shape_divisors = utils.divisors(images.shape[1])
    n = shape_divisors[np.argmin(np.abs(50 - shape_divisors))]
    return np.concatenate([np.median(im, axis=0) for im in np.split(images, n, axis=1)])


class Calibration(Block):
    """
    Flat, Bias and Dark calibration

    Parameters
    ----------
    darks : list
        list of dark files paths
    flats : list
        list of flat files paths
    bias : list
        list of bias files paths
    """

    @register_args
    def __init__(self, darks=None, flats=None, bias=None, loader=Image, **kwargs):

        super().__init__(**kwargs)
        if darks is None:
            darks = []
        if flats is None:
            flats = []
        if bias is None:
            bias = []
        self.images = {
            "dark": darks,
            "flat": flats,
            "bias": bias
        }

        self.master_dark = None
        self.master_flat = None
        self.master_bias = None

        self.loader = loader

        if self.master_bias is None:
            self._produce_master("bias")
        if self.master_dark is None:
            self._produce_master("dark")
        if self.master_flat is None:
            self._produce_master("flat")

    def calibration(self, image, exp_time):
        return (image - (self.master_dark * exp_time + self.master_bias)) / self.master_flat

    def _produce_master(self, image_type):
        _master = []
        images = self.images[image_type]

        if len(images) == 0:
            info(f"No {image_type} images set")
            if image_type == "dark":
                self.master_dark = 0
            elif image_type == "bias":
                self.master_bias = 0
            elif image_type == "flat":
                self.master_flat = 1

        for image_path in images:
            image = self.loader(image_path)
            if image_type == "dark":
                _dark = (image.data - self.master_bias) / image.exposure
                _master.append(_dark)
            elif image_type == "bias":
                _master.append(image.data)
            elif image_type == "flat":
                _flat = image.data - self.master_bias - self.master_dark*image.exposure
                _flat /= np.mean(_flat)
                _master.append(_flat)
                del image

        if len(_master) > 0:
            med = easy_median(_master)
            if image_type == "dark":
                self.master_dark = med.copy()
            elif image_type == "bias":
                self.master_bias = med.copy()
            elif image_type == "flat":
                self.master_flat = med.copy()
            del _master

    def plot_masters(self):
        plt.figure(figsize=(40, 10))
        plt.subplot(131)
        plt.title("Master bias")
        im = plt.imshow(utils.z_scale(self.master_bias), cmap="Greys_r")
        viz.add_colorbar(im)
        plt.subplot(132)
        plt.title("Master dark")
        im = plt.imshow(utils.z_scale(self.master_dark), cmap="Greys_r")
        viz.add_colorbar(im)
        plt.subplot(133)
        plt.title("Master flat")
        im = plt.imshow(utils.z_scale(self.master_flat), cmap="Greys_r")
        viz.add_colorbar(im)

    def run(self, image, **kwargs):
        data = image.data
        calibrated_image = self.calibration(data, image.exposure)
        calibrated_image[calibrated_image < 0] = 0.
        calibrated_image[~np.isfinite(calibrated_image)] = -1

        image.data = calibrated_image

    def citations(self):
        return "astropy", "numpy"


class Trim(Block):
    """Image trimming. If trim is not specified, triming is taken from the telescope characteristics

    |write| ``Image.header``
    
    |modify|

    Parameters
    ----------
    skip_wcs : bool, optional
        whether to skip applying trim to WCS, by default False
    trim : tuple, int or flot, optional
        (x, y) trim values, by default None which uses the ``trim`` value from the image telescope definition. If an int or a float is provided trim will be be applied to both axes.
    

    Example
    -------

    In what follows we generate an example image and apply a trimming on it

    .. jupyter-execute::

        from prose.tutorials import example_image
        from prose.blocks import Trim

        # our example image
        image = example_image()

        # Creating and applying the Trim block
        trim = Trim(trim=100)
        trimmed_image = trim(image)

    We can now see the resulting trimmed image against its original shape

    .. jupyter-execute::

        import matplotlib.pyplot as plt

        plt.figure(figsize=(12, 4))

        ax1 = plt.subplot(121)
        image.show(ax=ax1)
        trim.draw_cutout(image)
        plt.axis("off")
        _ = plt.title("original image (white = cutout)", loc="left")

        ax2 = plt.subplot(122)
        trimmed_image.show(ax=ax2)
        plt.axis("off")
        _ = plt.title("trimmed image", loc="left")

    """

    @register_args
    def __init__(self, skip_wcs=False, trim=None, **kwargs):

        super().__init__(**kwargs)
        self.skip_wcs = skip_wcs
        if isinstance(trim, (int, float)):
            trim = (trim, trim)
        self.trim = trim

    def run(self, image, **kwargs):
        shape = image.shape
        center = shape[::-1] / 2
        trim = self.trim if self.trim is not None else image.telescope.trimming[::-1]
        dimension = shape - 2 * np.array(trim)
        trim_image = Cutout2D(image.data, center, dimension, wcs=None if self.skip_wcs else image.wcs)
        image.data = trim_image.data
        if not self.skip_wcs:
            image.header.update(trim_image.wcs.to_header())

    def draw_cutout(self, image, ax=None, lw=1, c="w"):
        w, h = image.shape - 2*np.array(self.trim)
        rect = patches.Rectangle(2*np.array(self.trim)/2, w, h, linewidth=lw, edgecolor=c, facecolor='none')
        if ax is None:
            ax = plt.gca()
        ax.add_patch(rect)