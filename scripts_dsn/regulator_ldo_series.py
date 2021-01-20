# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class bag2_analog__regulator_ldo_series_dsn(DesignModule):
    """Module for library bag2_analog cell regulator_ldo_series

    Fill in high level description here.
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
            specfile_dict = 'Transistor database spec file names for each device',
            series_type = 'n or p for type of series device',
            th_dict = 'Transistor flavor dictionary.',
            l_dict = 'Transistor channel length dictionary',
            sim_env = 'Simulation environment',
            vdd = 'Supply voltage in volts.',
            vout = 'Reference voltage to regulate the output to',
            loadreg = 'Maximum fractional change in output voltage given change in output current',
            ibias = 'Maximum bias current of amp and biasing, in amperes.',
            rload = '',
            cload = '',
            psrr = 'Minimum power supply rejection (linear, not dB)',
            amp_dsn_params = "Amplifier design parameters that aren't either calculated or handled above",
            bias_dsn_params = '',
            optional_params = 'Optional parameters. voutcm=output bias voltage.',
            tb_stb_params = '',
            tb_iload_params = ''
        ))
        return ans

    def dsn_fet(self, **params):
        specfile_dict = params['specfile_dict']
        series_type = params['series_type']
        th_dict = params['th_dict']
        sim_env = params['sim_env']

        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        vdd = params['vdd']
        vout = params['vout']
        vg = params['vg']

        vs = vout if series_type == 'n' else vdd
        vd = vdd if series_type == 'n' else vout
        vb = 0 if series_type == 'n' else vdd

        ser_op = db_dict['ser'].query(vgs=vg-vs, vds=vd-vs, vbs=vb-vs)
        idc = zload.num[-1]/zload.den[-1]
        nf = int(round(idc/ser_op['ibias']))
        return nf > 1, dict(nf=nf, op=ser_op)

    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        optional_params = params['optional_params']

        specfile_dict = params['specfile_dict']
        th_dict = params['th_dict']
        l_dict = params['l_dict']
        sim_env = params['sim_env']

        tb_iload_params = params['tb_iload_params']
        tb_stb_params = params['tb_stb_params']

        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        ser_type = params['series_type']
        vdd = params['vdd']
        vout = params['vout']
        loadreg = params['load_reg']
        ibias = params['ibias']
        psrr = params['psrr']
        rload = params['rload']
        cload = params['cload']

        vth_ser = estimate_vth(db=db_dict['ser'],
                               is_nch=ser_type=='n',
                               lch=l_dict['ser'],
                               vgs=vdd-vout if ser_type=='n' else vout-vdd,
                               vbs=0-vout if ser_type=='n' else vdd-vdd)
        
        # Spec out amplifier
        amp_specfile_dict = dict()
        amp_th_dict = dict()
        amp_l_dict = dict()

        for k in ('in', 'tail', 'load'): # TODO amp topology might change
            amp_specfile_dict = specfile_dict[f'amp_{k}']
            amp_th_dict = th_dict[f'amp_{k}']
            amp_l_dict = l_dict[f'amp_{k}']
        amp_dsn_params = dict(params['amp_dsn_params'])
        amp_dsn_params['vdd'] = vdd
        amp_dsn_params.update(dict(vincm=vout,
                                   specfile_dict=amp_specfile_dict,
                                   th_dict=amp_th_dict,
                                   l_dict=amp_l_dict,
                                   sim_env=sim_env))

        # TODO Spec out biasing
        bias_specfile_dict = dict()
        bias_th_dict = dict()
        bias_l_dict = dict()
        for k in ('n', 'p'):
            bias_specfile_dict[k] = specfile_dict[f'bias_{k}']
            bias_th_dict[k] = th_dict[f'bias_{k}']
            bias_l_dict[k] = l_dict[f'bias_{k}']
        bias_th_dict['res'] = th_dict[f'bias_res']
        bias_dsn_params = dict(params['bias_dsn_params'])
        bias_dsn_params['vdd'] = vdd
        bias_dsn_params.update(dict(specfile_dict=bias_specfile_dict,
                                       th_dict=bias_th_dict,
                                       l_dict=bias_l_dict,
                                       sim_env=sim_env))

        # Keep track of viable ops
        viable_op_list = []

        amp_dsn_mod = bag2_analog__amp_diff_mirr_dsn()
        constgm_dsn_mod = bag2_analog__constant_gm_dsn()

        # Sweep gate bias voltage of the series device
        vg_min = vout+vth_ser if ser_type=='n' else vout+vth_ser
        vg_max = vdd+vth_ser if ser_type=='n' else vdd+vth_ser
        vg_vec = np.arange(vg_min, vg_max, 10e-3)
        for vg in vg_vec:
            # Size the series device
            match_ser, ser_info = dsn_fet(**params)
            if not match_ser:
                continue

            # TODO Design amplifier s.t. output bias = gate voltage
            # This is to maintain accuracy in the computational design proces
            ser_op = ser_info['op']
            amp_cload = ser_op['cgg']
            amp_dsn_params.update(dict(cload=amp_cload,
                                       optional_params=dict(voutcm=vout)))
            try:
                disable_print()
                amp_dsn_list = amp_dsn_mod.meet_spec(**amp_dsn_params)
            except ValueError:
                continue
            finally:
                enable_print()

            # For each possibility, design the biasing
            for amp_dsn_info in amp_dsn_lst:
                if amp_dsn_params['in_type'] == 'n':
                    bias_dsn_params.update(dict(vref=dict(n=amp_dsn_info['vgtail']),
                                                res_side='n'))
                else:
                    bias_dsn_params.update(dict(vref=dict(p=amp_dsn_info['vgtail']),
                                                res_side='p'))

                print(f'Attempting to design biasing...')
                try:
                    disable_print()
                    _, bias_dsn_info = bias_dsn_mod.design(**bias_dsn_params)
                except ValueError:
                    continue
                finally:
                    enable_print()
                print(f"Constant gm: {constgm_dsn_info}")

                # TODO Check against transient load

                # TODO Check PSRR

                # TODO Check against stb 

        return viable_op_list

    def _get_stb_sim(self, **spec):
        return pm

    def _get_psrr_sim(self, **spec):
        return

    def _get_iload_bounce_sim(self, **spec):
        prj = spec['prj']
        tb_vars = spec['tb_vars']
        tb_lib = spec['tb_lib']
        tb_cell = spec['tb_cell']
        impl_lib = spec['impl_lib']
        impl_cell = spec['impl_cell']
        tb_gen_name = self._get_tb_gen_name(spec['tb_gen_name'], spec['num'])

        # Generate testbench schematic
        tb_dsn = prj.create_design_module(tb_lib, tb_cell)
        tb_dsn.design(**(spec['params']))
        tb_dsn.implement_design(impl_lib, top_cell_name=tb_gen_name)

        # Copy and load ADEXL state of generated testbench
        tb_obj = prj.configure_testbench(impl_lib, tb_gen_name)

        # Assign testbench design variables (the ones that show in ADE)
        for param_name, param_val in tb_vars.items():
            tb_obj.set_parameter(param_name, param_val)

        # Update testbench changes and run simulation
        tb_obj.update_testbench()
        print(f'Simulating testbench {tb_gen_name}')
        save_dir = tb_obj.run_simulation()

        # Load simulation results into Python
        print("Simulation done, loading results")
        results = load_sim_results(save_dir)

        vreg = results['tran_vreg']

        return min(vreg), max(vreg)


    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):

    def get_sch_params(self, op):
