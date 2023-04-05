# prose

<p align="center" style="margin-bottom:-50px">
    <img src="docs/_static/prose3.png" width="450">
</p>

<p align="center">
  A python package to build image processing pipelines. Built for Astronomy
  <br>
  <p align="center">
    <a href="https://github.com/lgrcia/prose">
      <img src="https://img.shields.io/badge/github-lgrcia/prose-03A487.svg?style=flat" alt="github"/>
    </a>
    <a href="">
      <img src="https://img.shields.io/badge/license-MIT-lightgray.svg?style=flat" alt="license"/>
    </a>
    <a href="https://arxiv.org/abs/2111.02814">
      <img src="https://img.shields.io/badge/paper-B166A9.svg?style=flat" alt="paper"/>
    </a>
    <a href="https://prose.readthedocs.io/en/3.0.0">
      <img src="https://img.shields.io/badge/documentation-black.svg?style=flat" alt="documentation"/>
    </a>
  </p>
</p>

 *prose* is a Python package to build image processing pipelines, built for Astronomy. Beyond featuring the blocks to build pipelines from scratch, it provides pre-implemented ones to perform common tasks such as automated calibration, reduction and photometry.

*powered by [astropy](https://www.astropy.org/) and [photutils](https://photutils.readthedocs.io)*!

## Example

Here is a quick example pipeline to characterize the point-spread-function (PSF) of an example image


```python
from prose import Sequence, blocks
from prose.tutorials import example_image
import matplotlib.pyplot as plt

# getting the example image
image = example_image()

sequence = Sequence([
    blocks.SegmentedPeaks(),  # stars detection
    blocks.Cutouts(size=21),  # cutouts extraction
    blocks.MedianEPSF(),       # PSF building
    blocks.Moffat2D(),    # PSF modeling
])

sequence.run(image)

# plotting
image.show()           # detected stars
image.plot_psf_model() # PSF model
```

While being run on a single image, a Sequence is designed to be run on list of images (paths) and provides the architecture to build powerful pipelines. For more details check [Quickstart](https://prose.readthedocs.io/en/latest/notebooks/quickstart.html) and [What is a pipeline?](https://prose.readthedocs.io/en/latest/rst/core.html)

## Installation

### latest

*prose* is written for python 3 and can be installed from [pypi](https://pypi.org/project/prose/) with:

```shell
pip install prose
```

To install it through conda (recommended, within a fresh environment):

```shell
conda env create -f {prose_repo}/environment.yml -n prose
```

## Contributions
See our [contributions guidelines](docs/CONTRIBUTING.md)

<p align="center">
    <img src="docs/_static/lookatit.png" width="150">
</p>
