"""This source file contains some code from Selim's DESILS KSZ notebooks."""

import os
import time
import yaml
import shutil
import functools
import numpy as np

from . import io_utils
from . import utils

from .Catalog import Catalog
from .Cosmology import Cosmology
from .KszPSE import KszPSE

from scipy.signal import savgol_filter
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import interp1d


def subtract_zbin_means(w, z, nz=15):
    r"""Given per-galaxy weights 'w', and galaxy redshifts 'z', compute and subtract the mean weight in redshift bins.
    
    Function arguments:
      - ``w`` (array): per-galaxy weights
      - ``z`` (array): galaxy redshifts

    Return value:
      - A copy of ``w``, after subtracting the mean weight in redshift bins.

    (Source: Selim's ``pipeline_getsurrogates_selim.ipynb``, Nov 2024.)
    """

    w = np.asarray(w)
    z = np.asarray(z)
    assert w.shape == z.shape
    
    zmin = np.min(z) - 1.0e-10
    zmax = np.max(z) + 1.0e-10
    zbins = np.linspace(zmin, zmax, nz)
    
    locatez = np.digitize(z, zbins)
    zbin_means = np.zeros(nz)
    
    for iz in range(nz):
        wbin = w[locatez==iz]
        if len(wbin) > 0:
            zbin_means[iz] = np.mean(wbin)
    
    return w - zbin_means[locatez]


class PhotozDistribution:
    def __init__(self, zobs_arr, zerr_arr, zmin=0.0, zmax=1.5, zerr_min=0.02, zerr_max=0.5, nzbins=100, nzerrbins=49, niter=100, sigma=2):
        r"""Selim's model for the joint (ztrue, zobs, zerr) distribution in DESILS-LRG.

        Obtained by Richardson-Lucy deconvolution on the observed (zobs, zerr) distribution.
        (Source: Selim's ``pipeline_getsurrogates_selim.ipynb``, Nov 2024.)

        Constructor args:

          - ``zobs_arr``: 1-d array of observed redshifts.
          - ``zerr_arr``: 1-d array of observed redshift errors.
          - ``zmin, zmax, nzbins``: used internally when doing Richardson-Lucy deconvolution. 
            The defaults (0, 1.5, 100) are appropriate for DESILS-LRG.
          - ``zerr_min, zerr_max, nzerrbins``: used internally to split up the data before doing Richardson-Lucy deconvolution.
            The defaults (0.02, 0.5, 49) are approriate for DESILS-LRG.
          - ``niter``: number of Richardson-Lucy iterations.
          - ``sigma``: adjust for different smoothing levels.
        """
        
        zobs_arr = np.asarray(zobs_arr)
        zerr_arr = np.asarray(zerr_arr)
        
        # Argument checking.
        assert zobs_arr.shape == zerr_arr.shape
        assert zobs_arr.ndim == 1
        assert 0 <= zmin < zmax
        assert 0 <= zerr_min < zerr_max
        assert nzbins > 0
        assert nzerrbins > 0
        assert niter > 0
        assert sigma > 0.0

        self.nzbins = nzbins
        self.nzerrbins = nzerrbins
        self.z = np.linspace(zmin, zmax, nzbins)
        self.pzebins = np.linspace(zerr_min, zerr_max, nzerrbins+1)
        self.meanphotz = np.zeros(nzerrbins+2)
        self.umat = np.zeros((nzerrbins+2, nzbins))
        
        locatepze = np.digitize(zerr_arr, self.pzebins)

        for iz in range(nzerrbins+2):
            ix_bin = (locatepze == iz)
            zobs_bin = zobs_arr[ix_bin]
            zerr_bin = zerr_arr[ix_bin]
    
            if len(zerr_bin) < 5:
                continue
    
            self.meanphotz[iz] = np.mean(zerr_bin)
            counts_obs, bin_edges = np.histogram(zobs_bin, density=False, bins=nzbins, range=(zmin,zmax))
    
            zs_obs = (bin_edges[1:]+bin_edges[:-1])/2

            counts_obs = gaussian_filter1d(counts_obs, sigma=sigma)*1.
            counts_obs /= np.sum(counts_obs)
    
            counts_obs_int = interp1d(zs_obs, counts_obs, fill_value=0, bounds_error=False)
            observed_dist = counts_obs_int(self.z)

            Pij = np.array([[np.exp(-0.5*((zi-zj)/self.meanphotz[iz])**2) for zi in self.z] for zj in self.z])
            for j in range(len(self.z)):
                Pij[:,j] /= np.sum(Pij[:,j])

            di = observed_dist
            uguess = np.ones(nzbins)
    
            for iteration in range(niter):
                ci = np.dot(Pij, uguess)
                uguess *= np.dot(di / (ci+1.0e-10), Pij)

            self.umat[iz,:] = uguess / np.sum(uguess)

    
    def sample_z(self, zerr, zmin=0.4, zmax=1.0):
        r"""Randomly sample (ztrue, zobs) pairs, conditioned on a specified array of 'zerr' values.

        Function arguments:

          - ``zerr`` (array): 1-d array of zerr values.
          - ``(zmin, zmax)``: the returned zobs values will be constrained to satisfy 
            $z_{\rm min} < z_{\rm obs} < z_{\rm max}$. The defaults (0.4, 1.0) are appropriate
            for DESILS-LRG.

        Return values:

          - ``ztrue``: 1-d array (same length as ``zerr`` argument).
          - ``zobs``: 1-d array (same length as ``zerr`` argument).

        Each returned $(z_{\rm true}, z_{\rm obs})$ pair is consistent with the corresponding
        caller-specified $z_{\rm err}$.
        """
        
        zerr = np.asarray(zerr)
        assert zerr.ndim == 1

        locatepze = np.digitize(zerr, self.pzebins)
        ztrue = np.zeros_like(zerr)
        zobs = np.zeros_like(zerr)

        for iz in range(self.nzerrbins + 2):
            ix_bin = (locatepze == iz)
            lentruez = np.sum(ix_bin)
            
            buffer = 4
            lenpze = lentruez * buffer
    
            # Define some oversampled z-bins.
            # KMS: changed number of bins from lenpze to (10 * self.nzbins)
            # (speeds things up and gives similar results)
            
            zbin_edges = np.linspace(self.z[0], self.z[-1], 10*self.nzbins + 1)
            dz = zbin_edges[1] - zbin_edges[0]

            interp = interp1d(self.z, self.umat[iz,:])
            zvecs = (zbin_edges[1:] + zbin_edges[:-1]) / 2.  # bin centers
            zintrp = np.maximum(interp(zvecs), 0)

            # We perturb true_z within its bin [-dz/2,dz/2]
            # (Otherwise, all true_z's are at bin centers, and the histogram looks weird)
            
            true_z_sample = np.random.choice(zvecs, size=lenpze, p = (zintrp / np.sum(zintrp)))
            true_z_sample += np.random.uniform(-dz/2, dz/2, size=lenpze)
            photoz_err = np.random.normal(scale = self.meanphotz[iz], size = lenpze)
            observed_z_sample = true_z_sample + photoz_err 

            selectz_ = (observed_z_sample > zmin) * (observed_z_sample < zmax)
            ztrue[ix_bin] = (true_z_sample[selectz_])[:lentruez]
            zobs[ix_bin] = (observed_z_sample[selectz_])[:lentruez]

        return ztrue, zobs


####################################################################################################


class Kpipe:
    def __init__(self, input_dir, output_dir, nsurr=400):
        """FIXME write comment explaining inputs/outputs."""
        
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.nsurr = nsurr
        
        # Create output_dir and 'tmp' subdir
        os.makedirs(f'{output_dir}/tmp', exist_ok=True)

        with open(f'{input_dir}/params.yml', 'r') as f:
            params = yaml.safe_load(f)

            self.surr_bg = params['surr_bg']
            self.nkbins = params['nkbins']
            self.kmax = params['kmax']
            self.kbin_edges = np.linspace(0, self.kmax, self.nkbins+1)
            self.kbin_centers = (self.kbin_edges[1:] + self.kbin_edges[:-1]) / 2.

        self.box = io_utils.read_pickle(f'{input_dir}/bounding_box.pkl')
        self.cosmo = Cosmology('planck18+bao')
        self.gcat = Catalog.from_h5(f'{input_dir}/galaxies.h5')        
        self.rcat = Catalog.from_h5(f'{input_dir}/randoms.h5')

        # FIXME needs comment
        self.surr_ngal_mean = self.gcat.size
        self.surr_ngal_rms = 4 * np.sqrt(self.gcat.size)  # 4x Poisson

        self.pk_data_filename = f'{output_dir}/pk_data.npy'
        self.pk_surr_filename = f'{output_dir}/pk_surrogates.npy'
        self.pk_single_surr_filenames = [ f'{output_dir}/tmp/pk_surr_{i}.npy' for i in range(nsurr) ]

        
    @functools.cached_property
    def pse(self):
        print('Initializing KszPSE: this will take a few minutes')

        pse = KszPSE(
            box = self.box, 
            cosmo = self.cosmo, 
            randcat = self.rcat, 
            kbin_edges = self.kbin_edges,
            surr_ngal_mean = self.surr_ngal_mean,
            surr_ngal_rms = self.surr_ngal_rms,
            surr_bg = self.surr_bg,
            rweights = self.rcat.weight_zerr,
            nksz = 2,
            # ksz_rweights = None,
            ksz_bv = [ self.rcat.bv_90, self.rcat.bv_150 ],
            ksz_tcmb_realization = [ self.rcat.tcmb_90, self.rcat.tcmb_150 ],
            ztrue_col = 'ztrue',
            zobs_col = 'zobs'
        )
        
        print('KszPSE initialization done')
        return pse

    
    def get_pk_data(self, run=False):
        print(f'get_pk_data(), time={time.time()}\n', end='')
        if os.path.exists(self.pk_data_filename):
            return io_utils.read_npy(self.pk_data_filename)
        
        if not run:
            raise RuntimeError(f'Kpipe.get_pk_data(): run=False was specified, and file {self.pk_data_filename} not found')

        t90 = subtract_zbin_means(self.gcat.tcmb_90, self.gcat.z, nz=25)
        t150 = subtract_zbin_means(self.gcat.tcmb_150, self.gcat.z, nz=25)

        pk_data = self.pse.eval_pk(
            gcat = self.gcat,
            gweights = self.gcat.weight_zerr,
            # ksz_gweights = None, 
            ksz_bv = [ self.gcat.bv_90, self.gcat.bv_150 ], 
            ksz_tcmb = [ t90, t150 ],
            zobs_col = 'z'
        )

        io_utils.write_npy(self.pk_data_filename, pk_data)
        return pk_data


    def get_pk_surrogate(self, isurr, run=False):
        print(f'get_pk_surrogate(), time={time.time()}\n', end='')
        fname = self.pk_single_surr_filenames[isurr]
        
        if os.path.exists(fname):
            return io_utils.read_npy(fname)

        if not run:
            raise RuntimeError(f'Kpipe.get_pk_surrogate(): run=False was specified, and file {fname} not found')

        print(f'Running {fname}, time={time.time()}\n', end='')
        self.pse.simulate_surrogate()
        
        for sv in [ self.pse.Sv_noise, self.pse.Sv_signal ]:
            assert sv.shape ==  (2, self.rcat.size)
            for j in range(2):
                sv[j,:] = subtract_zbin_means(sv[j,:], self.rcat.zobs, nz=25)
    
        pk = self.pse.eval_pk_surrogate()

        io_utils.write_npy(fname, pk)
        return pk


    def get_pk_surrogates(self):
        if os.path.exists(self.pk_surr_filename):
            return io_utils.read_npy(self.pk_surr_filename)

        if not all(os.path.exists(f) for f in self.pk_single_surr_filenames):
            raise RuntimeError(f'Kpipe.read_pk_surrogates(): necessary files do not exist; you need to call Kpipe.run()')

        pk = np.array([ io_utils.read_npy(f) for f in self.pk_single_surr_filenames ])
        
        io_utils.write_npy(self.pk_surr_filename, pk)
        return pk


    def run(self, processes=2):
        # Copy yaml file from input to output dir.
        if not os.path.exists(f'{self.output_dir}/params.yml'):
            shutil.copyfile(f'{self.input_dir}/params.yml', f'{self.output_dir}/params.yml')
                
        have_data = os.path.exists(self.pk_data_filename)
        have_surr = os.path.exists(self.pk_surr_filename)
        missing_surrs = [ ] if have_surr else [ i for (i,f) in enumerate(self.pk_single_surr_filenames) if not os.path.exists(f) ]

        if (not have_surr) and (len(missing_surrs) == 0):
            self.get_pk_surrogates()   # creates "top-level" file
            have_surr = True
            
        if have_data and have_surr:
            print(f'Kpipe.run(): pipeline has already been run, exiting early')
            return
        
        # Initialize KszPSE before creating multiprocessing Pool.
        self.pse

        # FIXME change number of workers
        with utils.Pool(processes) as pool:
            l = [ ]
                
            if not have_data:
                l += [ pool.apply_async(self.get_pk_data, (True,)) ]
            for i in missing_surrs:
                l += [ pool.apply_async(self.get_pk_surrogate, (i,True)) ]

            for x in l:
                x.get()

        if not have_surr:
            # Consolidates all surrogates into one file
            self.get_pk_surrogates()
