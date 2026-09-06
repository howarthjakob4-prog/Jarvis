import unittest
import numpy as np
from jarvis.brain.design_renderer import raster_triangle


class DesignRendererTests(unittest.TestCase):
    def test_crossing_surfaces_resolve_per_pixel_independent_of_order(self):
        flat = np.array([[1,1,0],[17,1,0],[1,18,0]],dtype=float)
        tilted = np.array([[1,1,-1],[17,1,1],[1,18,-1]],dtype=float)
        def draw(order):
            pixels = np.zeros((20,20,4),dtype=np.uint8); depth = np.full((20,20),-np.inf)
            for tri,color in order: raster_triangle(pixels,depth,tri,color)
            return pixels
        red,blue = [255,0,0,255],[0,0,255,255]
        a = draw([(flat,red),(tilted,blue)]); b = draw([(tilted,blue),(flat,red)])
        np.testing.assert_array_equal(a,b); self.assertEqual(a[2,2].tolist(),red); self.assertEqual(a[2,13].tolist(),blue)

    def test_degenerate_and_offscreen_triangles_leave_image_empty(self):
        image = np.zeros((10,10,4),dtype=np.uint8); depth = np.full((10,10),-np.inf)
        for tri in ([[0,0,0],[1,1,0],[2,2,0]], [[20,20,0],[25,20,0],[20,25,0]]):
            raster_triangle(image,depth,np.array(tri,dtype=float),[255,0,0,255])
        self.assertFalse(image.any())


if __name__ == "__main__": unittest.main()
