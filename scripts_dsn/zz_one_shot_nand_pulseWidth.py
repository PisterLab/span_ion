# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
import warnings
from pprint import pprint
import csv

from bag.design.module import Module
from bag.core import BagProject
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add, enable_print, disable_print
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins, get_w_crossings
from bag.io import load_sim_results, save_sim_results, load_sim_file

# noinspection PyPep8Naming
class span_ion__zz_one_shot_nand_pulseWidth_dsn(DesignModule):
    """Module for library span_ion cell zz_one_shot_nand_pulseWidth
    that's intended for measurement rather than actual design. Structure, what is it!

    This is intended to run Monte Carlo simulations to get the
    generated pulse width of the block.
    """

    @classmethod
    def get_params_info(cls) -> Mapping[str,str]:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        ans = super().get_params_info()
        # TODO: add resistors to specfile_dict and th_dict 
        ans.update(dict(
            impl_lib = '',
            impl_cell = '',
            dut_params = '',
            vdd = '',
            cload = '',
            td_power = '',
            tstop = '',
            num_sims = 'Number of Monte Carlo sims for a single run',
            output_fname = 'CSV file without suffix for pulse widths',
            seed_offset = 'Offset from 1 for the seed for Monte Carlo simulations. Increment by 1 per simulation.'
        ))
        return ans

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.
        Returns collection of all possible solutions.
        Raises a ValueError if there is no solution.
        """
        dut_params = params['dut_params']
        num_bits = dut_params['num_bits']
        num_sims = params['num_sims']
        output_fname = params['output_fname']
        seed_offset = params['seed_offset']

        assert num_bits < 3, f'Currently only supports up to 2 bits (not {num_bits})'

        ### Setting up the testbench
        tb_lib = 'span_ion'
        tb_cell = 'zz_one_shot_nand_pulseWidth'
        impl_lib = params['impl_lib']
        impl_cell = params['impl_cell']

        # Testbench parameters
        vdd = params['vdd']
        cload = params['cload']
        td_power = params['td_power']
        tstop = params['tstop']

        tb_vars = dict(VDD=vdd,
                       CL=cload,
                       TD_POWER=td_power,
                       TSTOP=tstop)

        # Generate testbench schematic
        prj = BagProject()
        tb = prj.create_design_module(tb_lib, tb_cell)
        tb.design(**dut_params)
        tb.implement_design(impl_lib, top_cell_name=impl_cell)

        # Copy and load ADEXL state of generated testbench
        tb_obj = prj.configure_testbench(impl_lib, impl_cell)

        # Iterate across digital codes
        num_codes = int(round(2**num_bits))
        for code in range(num_codes):
            # Specifying the code associated with the file
            output_fname_full = f'{output_fname}_{code}.csv'

            # Assign testbench design variables (the ones that show in ADE)
            var_b0 = code % 2
            var_b1 = code // 2
            cap_val = dut_params['cap_params']['cap_val'] # Sometimes cap doesn't set correctly

            tb_vars.update(dict(b0=var_b0,
                                b1=var_b1,
                                CAP_VAL=cap_val))

            for param_name, param_val in tb_vars.items():
                tb_obj.set_parameter(param_name, param_val)

            # Update testbench changes and run simulation
            tb_obj.update_testbench()
            print(f'Simulating code {code}...')
            for i in range(num_sims):
                print(f'\t {i+1}/{num_sims}')
                idx_run = i + 1 + seed_offset
                save_dir = tb_obj.run_simulation(sim_type='mc', sim_info=dict(idx_run=idx_run))
                # Load simulation results into Python
                results = load_sim_results(save_dir)
                t_vec = results['time']
                v_vec = results['tran_vout']
                data_dict = {t_vec[i]:v_vec[i] for i in range(len(t_vec))}

                # Get pulse width data
                pulse_widths = self._get_pulse_widths(data_dict, vdd/2)

                # Write to a row in a CSV file
                with open(output_fname_full, 'a', newline='') as csvfile:
                    spamwriter = csv.writer(csvfile, delimiter=',')
                    spamwriter.writerow(pulse_widths)
        
        return []


    def _get_pulse_widths(self, data_dict, sig_threshold, posedge=True):
        '''
        Inputs:
            data_dict:      Key:value is time:signal value.
            sig_threshold:  Threshold for determining an edge crossing. Used for linear interpolation.
            posedge:        Boolean. True to indicate that a rising edge is the start of a pulse.
                            False indicates a pulse is active low.
        Outputs:
            Returns a list of pulse widths in the order in which they appear.
        '''
        t_vec = list(data_dict.keys())
        t_vec.sort()
        sig_vec = [data_dict[t] for t in t_vec]
        result = []

        # Finding zero crossings of down-shifted signal vector
        sig_vec_shifted = [sig_val-sig_threshold for sig_val in sig_vec]
        zcross_start_idx = np.where(np.diff(np.signbit(sig_vec_shifted)))[0]

        # Linear interpolation of times
        for zcross_idx in zcross_start_idx:
            val_start = sig_vec_shifted[zcross_idx]
            val_stop = sig_vec_shifted[zcross_idx + 1]

            frac = val_start / (val_start - val_stop)

            tedge_start = t_vec[zcross_idx]
            tedge_stop = t_vec[zcross_idx + 1]

            t_cross = tedge_start + frac * (tedge_stop - tedge_start)

            if val_start > val_stop:
                t_negedge = t_cross
                if posedge:
                    result = result + [t_negedge - t_posedge]
                    t_negedge = np.inf
                    t_posedge = -np.inf
            elif val_start < val_stop:
                t_posedge = t_cross
                if not posedge:
                    result = result + [t_posedge - t_negedge]
                    t_negedge = -np.inf
                    t_posedge = np.inf
            else:
                raise ValueError("(get_pulse_widths) Edge detection isn't actually an edge!")

        return result

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        pass

    def get_sch_params(self, op):
        pass