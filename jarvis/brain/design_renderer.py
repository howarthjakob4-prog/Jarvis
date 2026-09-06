"""Small orthographic depth-buffer renderer for layered concept geometry.

Uses NumPy, already a Jarvis dependency. No GPU context or network is required.
"""
import numpy as np


def render_meshes(meshes, width, height, scale):
    """Render (camera-space vertices, faces, RGB) tuples into an RGBA image."""
    pixels = np.zeros((height,width,4),dtype=np.uint8)
    depth = np.full((height,width),-np.inf,dtype=np.float32)
    light = np.array([.3,.8,.5])
    light /= np.linalg.norm(light)
    for vertices,faces,color in meshes:
        vertices = np.asarray(vertices,dtype=np.float64)
        projected = vertices.copy()
        projected[:,0] = width/2+vertices[:,0]*scale
        projected[:,1] = height/2-vertices[:,1]*scale
        for face in faces:
            a,b,c = vertices[list(face[:3])]
            normal = np.cross(b-a,c-a)
            length = np.linalg.norm(normal)
            if length < 1e-12:
                continue
            shade = .65+.35*abs(np.dot(normal/length,light))
            rgba = np.array([*[min(255,int(channel*shade)) for channel in color],255],dtype=np.uint8)
            for i in range(1,len(face)-1):
                tri = projected[[face[0],face[i],face[i+1]]]
                raster_triangle(pixels,depth,tri,rgba)
    return pixels


def raster_triangle(pixels,depth,tri,color):
    """Interpolate depth per pixel; centroid sorting cannot resolve overlaps."""
    height,width = depth.shape
    x0,y0,z0 = tri[0]
    x1,y1,z1 = tri[1]
    x2,y2,z2 = tri[2]
    denominator = (y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
    if abs(denominator) < 1e-10:
        return
    left = max(0,int(np.floor(min(x0,x1,x2))))
    right = min(width-1,int(np.ceil(max(x0,x1,x2))))
    top = max(0,int(np.floor(min(y0,y1,y2))))
    bottom = min(height-1,int(np.ceil(max(y0,y1,y2))))
    if right < left or bottom < top:
        return
    yy,xx = np.ogrid[top:bottom+1,left:right+1]
    xx,yy = xx+.5,yy+.5
    w0 = ((y1-y2)*(xx-x2)+(x2-x1)*(yy-y2))/denominator
    w1 = ((y2-y0)*(xx-x2)+(x0-x2)*(yy-y2))/denominator
    w2 = 1-w0-w1
    z = w0*z0+w1*z1+w2*z2
    region = depth[top:bottom+1,left:right+1]
    visible = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9) & (z > region)
    region[visible] = z[visible]
    pixels[top:bottom+1,left:right+1][visible] = color
