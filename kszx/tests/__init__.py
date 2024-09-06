from . import test_box
from . import test_lss

def run_all_tests():
    test_box.test_k_component()
    test_box.test_r_component()
    test_box.test_smallest_r()
    test_lss.test_interpolation()
    test_lss.test_interpolation_gridding_consistency()
    test_lss.test_simulate_gaussian()
    test_lss.test_estimate_power_spectrum()

    #test_lss.monte_carlo_simulate_gaussian([4,6,1], 10.0)
    #test_lss.monte_carlo_simulate_gaussian([5,4,6], 10.0)
    #test_lss.monte_carlo_simulate_gaussian([6,7,4], 10.0)
    #test_lss.monte_carlo_simulate_gaussian([4,4,5], 10.0)
