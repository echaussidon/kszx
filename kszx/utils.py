import numpy as np
import scipy.integrate
import scipy.interpolate


def quad(f, xmin, xmax, epsabs=0.0, epsrel=1.0e-4, points=None):
    """Wrapper for scipy.integrate.quad()."""
    
    assert xmin < xmax

    if points is not None:
        # Remove points outside range (not sure if scipy does this automatically)
        points = [ x for x in points if (xmin < x < xmax) ]                                       
    
    return scipy.integrate.quad(f, xmin, xmax, epsabs=epsabs, epsrel=epsrel)[0]


def dblquad(f, xmin, xmax, ymin, ymax, *, epsabs=0.0, epsrel=1.0e-4):
    """
    Wrapper for scipy.integrate.dblquad().
      - The 'f' argument is f(x,y) [not f(y,x) as in scipy.integrate.dblquad]
      - The 'ymin' and 'ymax' arguments can either be floats or functions of x
    """

    ff = lambda x,y: f(y,x)  # swap
    return scipy.integrate.dblquad(f, xmin, xmax, ymin, ymax, epsabs=epsabs, epsrel=epsrel)[0]


def spline1d(xvec, yvec):
    """Wrapper for scipy.interpolate.InterpolatedUnivariateSpline()."""
    
    assert xvec.shape == yvec.shape
    assert xvec.ndim == yvec.ndim == 1
    return scipy.interpolate.InterpolatedUnivariateSpline(xvec, yvec)


def spline2d(xvec, yvec, zmat):
    """
    Wrapper for scipy.interpolate.RectBivariateSpline().
    
    Note that RectBivariateSpline.__call__(x,y) takes a 'grid' argument:

       grid=False  means "broadcast x,y to get a set of points"
       grid=True   means "take the Cartesian product of x,y to get a grid"

    Warning: grid=True is the default! (I usually want grid=False).
    """

    assert xvec.ndim == yvec.ndim == 1
    assert zmat.shape == (len(xvec), len(yvec))
    return scipy.interpolate.RectBivariateSpline(xvec, yvec, zmat)



def logspace(xmin, xmax, n=None, dlog=None):
    """
    Returns a 1-d array of values, uniformly log-spaced over the range (xmin, xmax).
    
    The spacing can be controlled by setting either the 'n' argument (number of points)
    or 'dlog' (largest allowed spacing in log(x)).
    """

    assert 0 < xmin < xmax
    assert (n is None) or (n >= 2)

    if (n is None) and (dlog is not None):
        n = int((np.log(xmax) - np.log(xmin)) / dlog) + 2
    elif (n is None) or (dlog is not None):
        raise RuntimeError("logspace: exactly one of 'n', 'dlog' should be None")

    ret = np.exp(np.linspace(np.log(xmin), np.log(xmax), n))
    ret[0] = xmin   # get rid of roundoff error
    ret[-1] = xmax  # get rid of roundoff error
    
    return ret


def log_uniform(xmin, xmax, size=None):
    assert 0 < xmin < xmax
    return np.exp(np.random.uniform(np.log(xmin), np.log(xmax), size=size))


def covscale(m):
    m = np.array(m)
    assert m.ndim == 2
    assert m.shape[0] == m.shape[1]
    assert np.all(m.diagonal() > 0.0)

    n = m.shape[0]
    ret = np.zeros((n,n))

    for i in xrange(n):
        for j in xrange(n):
            ret[i,j] = m[i,j] / (m[i,i]*m[j,j])**0.5

    return ret


def is_sorted(x):
    assert x.ndim == 1
    assert len(x) >= 2
    return np.all(x[:-1] < x[1:])
    

def trapezoid_weights(xmin, xmax, n):
    """Returns xvec, wvec."""

    assert xmin < xmax
    assert n >= 2
    
    xvec = np.linspace(xmin, xmax, n)
    wvec = np.full(n, (xmax-xmin)/(n-1))
    wvec[0] *= 0.5
    wvec[-1] *= 0.5

    return xvec, wvec


def range_checked_index_operator(source_array, index_array, default_value=None, error_message=None):
    """Returns source_array[index_array], but substitutes 'default_value' if index is out of range."""
    
    assert source_array.ndim == 1
    assert len(source_array) > 0

    n = len(source_array)
    valid = np.logical_and(index_array >= 0, index_array < n)

    if default_value is not None:
        index_array = np.where(valid, index_array, 0)
        return np.where(valid, source_array[index_array], default_value)
    
    if np.all(valid):
        return source_array[index_array]

    if error_message is None:
        error_message = 'index out of range, and no default_value specfied'

    raise RuntimeError(error_message)

    
def compare_arrays(arr1, arr2):
    assert arr1.shape == arr2.shape
    assert arr1.dtype == arr2.dtype

    t = arr1-arr2
    num = np.vdot(t,t)
    den = np.vdot(arr1,arr1) + np.vdot(arr2,arr2)
    
    return np.sqrt(num/den) if (den > 0.0) else 0.0


def random_shape(ndim=None, rng=np.random.default_rng()):
    if ndim is None:
        ndim = rng.integers(1,4)
    
    nmax = int(10000 ** (1./ndim))
    ret = np.zeros(ndim, dtype=int)
    
    for d in range(ndim):
        if rng.uniform() < 0.1:
            ret[d] = 1
        elif rng.uniform() < 0.1:
            ret[d] = 2
        else:
            ret[d] = rng.integers(3,nmax+1)

    return ret


def randomize_array(arr, *, lo=-1.0, hi=1.0, rng=np.random.default_rng()):
    if arr.dtype == float:
        arr[:] = rng.uniform(lo, hi, arr.shape)
    elif arr.dtype == complex:
        arr.real = rng.uniform(lo, hi, arr.shape)
        arr.imag = rng.uniform(lo, hi, arr.shape)
    else:
        raise RuntimeError('dtype must be real or complex')

    
def random_array(dtype, *, shape=None, lo=-1.0, hi=1.0, pad=True, rng=np.random.default_rng()):
    if shape is None:
        shape = random_shape(rng=rng)
            
    if not pad:
        ret = np.empty(shape, dtype=dtype)
    else:
        # FIXME should sometimes make last axis non-contiguous
        shape = np.asarray(shape, dtype=int)
        new_shape = shape + rng.integers(0, 3, size=len(shape))
        ret = np.empty(new_shape, dtype=dtype)

        for d in range(len(shape)):
            if shape[d] < ret.shape[d]:
                ret = np.take(ret, np.arange(shape[d]), axis=d)
                
    assert np.all(np.asarray(shape) == np.asarray(ret.shape))
    randomize_array(ret, lo=lo, hi=hi, rng=rng)
    
    return ret


def contains_duplicates(l):
    return len(l) != len(set(l))


def boxcar_sum(a, m, normalize=False):
    """
    Given a 1-d array 'a' of length n, return a length-n array containing boxcar-summed values of a.
    Each boxcar consists of (2*m+1) array elements, or fewer near the edges of the array.

    E.g. if m=2, then

      ret[0] = a[0] + a[1] + a[2]
      ret[1] = a[0] + a[1] + a[2] + a[3]
      ret[2] = a[0] + a[1] + a[2] + a[3] + a[4]
      ret[3] = a[1] + a[2] + a[3] + a[4] + a[5]
        ...
      ret[n-4] = a[n-6] + a[n-5] + a[n-4] + a[n-3] + a[n-2]
      ret[n-3] = a[n-5] + a[n-4] + a[n-3] + a[n-2] + a[n-1]
      ret[n-2] = a[n-4] + a[n-3] + a[n-2] + a[n-1]
      ret[n-1] = a[n-3] + a[n-2] + a[n-1]
    
    If 'normalize' is True, then "boxcar means" are computed instead of "boxcar sums".
    """
    
    a = np.asarray(a)
    assert a.ndim == 1
    assert m >= 0

    if m == 0:
        return np.copy(a)
    
    n = len(a)
    assert n > 0
        
    if n <= m+1:
        t = np.mean(a) if normalize else np.sum(a)
        return np.full((n,), t, dtype=a.dtype)

    c = np.cumsum(a)
    ret = np.zeros(n, dtype=a.dtype)
    ret[:-m] = c[m:]
    ret[-m:] = c[-1]
    ret[(m+1):] -= c[:(-m-1)]
    
    if normalize:
        den = np.full((n,), 2*m+1)
        den[:m] -= np.arange(m,0,-1)
        den[-m:] -= np.arange(1,m+1)
        ret = ret / den

    return ret
