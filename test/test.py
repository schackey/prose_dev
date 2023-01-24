import inspect
import sys
import unittest
from prose import example_image, Sequence, Block, blocks
import numpy as np


def classes(module, sublcasses):
    class_members = inspect.getmembers(sys.modules[module], inspect.isclass)

    def mask(n, c):
        return issubclass(c, sublcasses) and n[0] != "_"

    return [c for n, c in class_members if mask(n, c)]


class TestBlocks(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        self.blocks = []

    def load(self, module, subclasses):
        self.blocks = classes(module, subclasses)

    def test_all(self):
        for block in self.blocks:
            with self.subTest(block=block.__name__):
                block().run(self.image)


class TestBlocksDetection(TestBlocks):
    def __init__(self, *args, **kwargs):
        TestBlocks.__init__(self, *args, **kwargs)
        from prose.blocks.detection import _SourceDetection

        self.load("prose.blocks.detection", _SourceDetection)
        self.image = example_image()


class TestBlocksGeometry(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        from prose.blocks.detection import PointSourceDetection

        self.image = example_image()
        PointSourceDetection().run(self.image)

    def test_Trim(self):
        from prose.blocks.geometry import Trim

        im = Trim(30)(self.image)

    def test_Cutouts(self):
        from prose.blocks.geometry import Cutouts

        im = Cutouts()(self.image.copy())

        assert len(im._sources) == len(im.cutouts)

    def test_ComputeTransform(self):
        from prose.blocks.geometry import ComputeTransform

        im = ComputeTransform(self.image.copy())(self.image.copy())
        assert np.allclose(im.transform, np.eye(3))


class TestBlocksCentroids(TestBlocks):
    def __init__(self, *args, **kwargs):
        TestBlocks.__init__(self, *args, **kwargs)
        from prose.blocks.detection import PointSourceDetection
        from prose.blocks.centroids import _PhotutilsCentroid

        self.load("prose.blocks.centroids", _PhotutilsCentroid)
        self.image = example_image()
        self.image = PointSourceDetection()(self.image)

    def test_Balletentroid(self):
        from prose.blocks.centroids import CentroidBallet

        CentroidBallet()(self.image)


class TestBlocksPSF(TestBlocks):
    def __init__(self, *args, **kwargs):
        TestBlocks.__init__(self, *args, **kwargs)
        from prose.blocks.psf import _PSFModelBase

        self.load("prose.blocks.psf", _PSFModelBase)

        self.image = example_image()
        Sequence(
            [blocks.PointSourceDetection(), blocks.Cutouts(), blocks.MedianEPSF()]
        ).run(self.image)

    def test_MedianPSF(self):
        from prose.blocks.psf import MedianEPSF
        from prose.blocks.geometry import Cutouts

        im = Cutouts()(self.image)
        im = MedianEPSF()(im)
        

class TestAlignment(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        from prose.blocks.detection import PointSourceDetection

        self.image = example_image()
        PointSourceDetection().run(self.image)

    def test_AlignReferenceSources(self):
        from prose.blocks.alignment import AlignReferenceSources

        im = AlignReferenceSources(self.image.copy())(self.image.copy())