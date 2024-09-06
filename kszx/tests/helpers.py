from .. import Box

import numpy as np

    
def compare_arrays(arr1, arr2):
    assert arr1.shape == arr2.shape
    assert arr1.dtype == arr2.dtype

    t = arr1-arr2
    num = np.vdot(t,t)
    den = np.vdot(arr1,arr1) + np.vdot(arr2,arr2)
    
    return np.sqrt(num/den) if (den > 0.0) else 0.0


def generate_indices(shape):
    if len(shape) == 1:
        for i in range(shape[0]):
            yield (i,)
    else:
        for t in generate_indices(shape[:-1]):
            for i in range(shape[-1]):
                yield t + (i,)


def random_shape(ndim=None, nmin=1):
    if ndim is None:
        ndim = np.random.randint(1,4)
    
    ret = np.zeros(ndim, dtype=int)
    nmax = int(10000 ** (1./ndim))
    assert nmax >= (nmin+1)
    
    for d in range(ndim):
        if np.random.uniform() < 0.1:
            ret[d] = nmin
        elif np.random.uniform() < 0.1:
            ret[d] = nmin+1
        else:
            ret[d] = np.random.randint(nmin, nmax+1)

    return ret


def random_box(ndim=None, nmin=2):
    npix = random_shape(ndim, nmin)
    pixsize = np.random.uniform(1.0, 10.0)
    
    t = np.random.uniform(0, pixsize)
    cpos = np.random.uniform(-t*npix, t*npix, size=len(npix))
    return Box(npix, pixsize, cpos)


def map_dot_product(box, arr1, arr2, normalize=True):
    """Returns dot product of two maps (maps can be either Fourier or real space).
    
    For two real-space arrays, the dot product is defined by:
        
       f.g = (pixel volume) sum_x f(x) g(x)       [ morally int d^nx f(x) g(x) ]

   For two Fourier-space arrays, the dot product is defined by:

       f.g = (box volume)^{-1} sum_k f(k) g(k)^*  [ morally int d^nk/(2pi)^n f(k) g(k)^* ]

    If dot products are defined with these normalizations, then:

       - kszx.lss.fft_c2r() and kszx.lss.fft_c2r() are adjoints (transposes)
       - kszx.lss.interpolate_points() and kszx.lss.grid_points() are ajdoints.

    These statements are the basis for unit tests in kszx.tests.test_lss.
    """
    
    # Case 1: real-space dot product.
    if box.is_real_space_map(arr1) and box.is_real_space_map(arr2):
        return box.pixel_volume * np.vdot(arr1, arr2)

    if (not box.is_fourier_space_map(arr1)) or (not box.is_fourier_space_map(arr2)):
        raise RuntimeError('wrong shapes/dtypes in map_dot_product()')
    
    # Case 2: Fourier-space dot product, last dimension is odd.
    if box.npix[-1] % 2:
        t = np.vdot(arr1[...,0], arr2[...,0])
        t += 2 * np.vdot(arr1[...,1:], arr2[...,1:])
        
    # Case 3: Fourier-space dot product, last dimension is even and > 2.
    elif box.npix[-1] > 2:
        t = np.vdot(arr1[...,0], arr2[...,0])
        t += np.vdot(arr1[...,-1], arr2[...,-1])
        t += 2 * np.vdot(arr1[...,1:-1], arr2[...,1:-1])
        
    # Case 4: Fourier-space dot product, last dimension == 2
    else:
        t = np.vdot(arr1, arr2)
    
    return t.real / box.box_volume
