import numpy as np
from .. import Block, Image
from jax.config import config

config.update("jax_enable_x64", True)
import jax
import jax.numpy as jnp
from jaxopt import ScipyMinimize
from astropy.stats import gaussian_sigma_to_fwhm
from scipy.optimize import minimize

__all__ = ["MedianEPSF", "JAXGaussian2D", "JAXMoffat2D", "Gaussian2D", "Moffat2D"]


def moments(data):
    """Returns (height, x, y, width_x, width_y)
    the gaussian parameters of a 2D distribution by calculating its
    moments"""
    height = data.max()
    background = data.min()
    data = data - np.min(data)
    total = data.sum()
    x, y = np.indices(data.shape)
    x = (x * data).sum() / total
    y = (y * data).sum() / total
    col = data[:, int(y)]
    width_x = np.sqrt(abs((np.arange(col.size) - y) ** 2 * col).sum() / col.sum())
    row = data[int(x), :]
    width_y = np.sqrt(abs((np.arange(row.size) - x) ** 2 * row).sum() / row.sum())
    width_x /= gaussian_sigma_to_fwhm
    width_y /= gaussian_sigma_to_fwhm
    return {
        "amplitude": height,
        "x": x,
        "y": y,
        "sigma_x": width_x,
        "sigma_y": width_y,
        "background": background,
        "theta": 0.0,
        "beta": 3.0,
    }


class MedianEPSF(Block):
    def __init__(self, max_sources=1, name=None, normalize=True):
        """Stack cutouts into a median effective PSF

        |read| Image.source

        [write] Image.epsf

        Parameters
        ----------
        max_sources : int, optional
            max number of sources cutout to be stacked should have, by default 1, meaning only cutouts with a single source are used
        name : _type_, optional
            _description_, by default None
        normalize : bool, optional
            wether to normalize cutouts to form a normalized EPSF, by default True
        """
        super().__init__(name=name)
        self.max_sources = max_sources
        self.normalize = normalize

    def run(self, image):
        good_cutouts = np.array(
            [c.data for c in image.cutouts if len(c.sources) <= self.max_sources]
        )
        if self.normalize:
            good_cutouts = good_cutouts / np.nanmax(good_cutouts, (1, 2))[:, None, None]
        epsf = np.nanmedian(good_cutouts, 0)
        image.epsf = Image(epsf)
        image.set("epsf_n_sources", len(good_cutouts))


class _PSFModelBase(Block):
    def __init__(self, reference_image=None, name=None, verbose=False):
        super().__init__(name, verbose)
        self._init = reference_image.epsf_params if reference_image else None
        self.shape = (0, 0)  # reference_image.epsf.shape if reference_image else None
        self.x, self.y = None, None
        self._last_init = None

    def run(self, image: Image):
        if np.all(image.epsf.shape != self.shape):
            self.shape = image.epsf.shape
            self.x, self.y = np.indices(self.shape)
            self.model = self.model_function()

        if self._last_init is None:
            init = moments(image.epsf.data)
            self._last_init = init

        params = self.optimize(image.epsf.data)
        image.epsf.params = params
        image.epsf.model = self.model
        self._last_init = params


class _JAXPSFModel(_PSFModelBase):
    def __init__(self, reference_image=None, name=None, verbose=False):
        super().__init__(reference_image, name, verbose)

    def optimize(self, data):
        @jax.jit
        def nll(params):
            ll = jnp.sum(jnp.power((self.model(params) - data), 2))
            return ll

        opt = ScipyMinimize(fun=nll)
        params = opt.run(self._last_init).params
        return params


class JAXGaussian2D(_JAXPSFModel):
    def __init__(self, reference_image=None, name=None, verbose=False):
        super().__init__(reference_image, name, verbose)

    def model_function(self):
        @jax.jit
        def model(params):
            dx = self.x - params["x"]
            dy = self.y - params["y"]
            sx2 = jnp.square(params["sigma_x"])
            sy2 = jnp.square(params["sigma_y"])
            theta = params["theta"]

            a = (jnp.cos(theta) ** 2) / (2 * sx2) + (jnp.sin(theta) ** 2) / (2 * sy2)
            b = -(jnp.sin(2 * theta)) / (4 * sx2) + (jnp.sin(2 * theta)) / (4 * sy2)
            c = (jnp.sin(theta) ** 2) / (2 * sx2) + (jnp.cos(theta) ** 2) / (2 * sy2)
            psf = params["amplitude"] * jnp.exp(
                -(a * jnp.square(dx) + 2 * b * dx * dy + c * jnp.square(dy))
            )
            return psf + params["background"]

        return model


class JAXMoffat2D(_JAXPSFModel):
    def __init__(self, reference_image=None, name=None, verbose=False):
        super().__init__(reference_image, name, verbose)

    def model_function(self):
        @jax.jit
        def model(params):
            # https://pixinsight.com/doc/tools/DynamicPSF/DynamicPSF.html
            dx_ = self.x - params["x"]
            dy_ = self.y - params["y"]
            sx = params["sigma_x"]
            sy = params["sigma_y"]
            theta = params["theta"]
            dx = dx_ * jnp.cos(theta) + dy_ * jnp.sin(theta)
            dy = -dx_ * jnp.sin(theta) + dy_ * jnp.cos(theta)

            return params["background"] + params["amplitude"] / jnp.power(
                1 + jnp.square(dx / sx) + jnp.square(dy / sy), params["beta"]
            )

        return model


class Gaussian2D(_PSFModelBase):
    def __init__(self, reference_image=None, name=None, verbose=False):
        super().__init__(reference_image, name, verbose)

    def optimize(self, data):
        def nll(params):
            ll = np.sum(np.power((self.model(*params) - data), 2))
            return ll

        keys = ["amplitude", "x", "y", "sigma_x", "sigma_y", "theta", "background"]
        p0 = [self._last_init[k] for k in keys]
        w = np.max(data.shape)
        bounds = [
            (0, 1.5),
            (0, w),
            (0, w),
            (0.5, w),
            (0.5, w),
            (-np.pi, np.pi),
            (0, np.mean(data)),
        ]

        opt = minimize(nll, p0, bounds=bounds).x
        return dict(zip(keys, opt))

    def model_function(self):
        def model(height, xo, yo, sx, sy, theta, m):
            dx = self.x - xo
            dy = self.y - yo
            a = (np.cos(theta) ** 2) / (2 * sx**2) + (np.sin(theta) ** 2) / (
                2 * sy**2
            )
            b = -(np.sin(2 * theta)) / (4 * sx**2) + (np.sin(2 * theta)) / (
                4 * sy**2
            )
            c = (np.sin(theta) ** 2) / (2 * sx**2) + (np.cos(theta) ** 2) / (
                2 * sy**2
            )
            psf = height * np.exp(-(a * dx**2 + 2 * b * dx * dy + c * dy**2))
            return psf + m

        return model


class Moffat2D(_PSFModelBase):
    def __init__(self, reference_image=None, name=None, verbose=False):
        super().__init__(reference_image, name, verbose)

    def optimize(self, data):
        def nll(params):
            ll = np.sum(np.power((self.model(*params) - data), 2))
            return ll

        keys = ["amplitude", "x", "y", "sigma_x", "sigma_y", "theta", "background"]
        p0 = [self._last_init[k] for k in keys]
        w = np.max(data.shape)
        bounds = [
            (0, 1.5),
            (0, w),
            (0, w),
            (0.5, w),
            (0.5, w),
            (-np.pi, np.pi),
            (0, np.mean(data)),
        ]

        opt = minimize(nll, p0, bounds=bounds).x
        return dict(zip(keys, opt))

    def model_function(self):
        def model(height, xo, yo, sx, sy, theta, m):
            dx = self.x - xo
            dy = self.y - yo
            a = (np.cos(theta) ** 2) / (2 * sx**2) + (np.sin(theta) ** 2) / (
                2 * sy**2
            )
            b = -(np.sin(2 * theta)) / (4 * sx**2) + (np.sin(2 * theta)) / (
                4 * sy**2
            )
            c = (np.sin(theta) ** 2) / (2 * sx**2) + (np.cos(theta) ** 2) / (
                2 * sy**2
            )
            psf = height * np.exp(-(a * dx**2 + 2 * b * dx * dy + c * dy**2))
            return psf + m

        return model
