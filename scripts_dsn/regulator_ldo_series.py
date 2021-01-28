# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any, List

import os
import pkg_resources
import numpy as np
import warnings
from pprint import pprint

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add, enable_print, disable_print
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

from .amp_diff_mirr import bag2_analog__amp_diff_mirr_dsn
from .constant_gm import bag2_analog__constant_gm_dsn

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
            rload = 'Load resistance from the output of the LDO to ground',
            cload = 'Load capacitance from the output of the LDO to ground',
            psrr = 'Minimum power supply rejection ratio (dB, 20*log10(dVdd/dVout))',
            pm = 'Minimum phase margin for the large feedback loop',
            amp_dsn_params = "Amplifier design parameters that aren't either calculated or handled above",
            bias_dsn_params = "Design parameters for the biasing that aren't calculated or handled above.",
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
        rload = params['rload']

        vs = vout if series_type == 'n' else vdd
        vd = vdd if series_type == 'n' else vout
        vb = 0 if series_type == 'n' else vdd

        ser_op = db_dict['ser'].query(vgs=vg-vs, vds=vd-vs, vbs=vb-vs)
        idc = vout/rload
        nf = int(round(idc/ser_op['ibias']))
        return nf > 1, dict(nf=nf, op=ser_op)


    def meet_spec(self, **params) -> List[Mapping[str,Any]]:
        specfile_dict = params['specfile_dict']
        th_dict = params['th_dict']
        l_dict = params['l_dict']
        sim_env = params['sim_env']

        # TODO simulating
        tb_iload_params = params['tb_iload_params']
        tb_stb_params = params['tb_stb_params']

        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        ser_type = params['series_type']
        vdd = params['vdd']
        vout = params['vout']
        loadreg = params['loadreg'] # TODO load regulation
        ibias_max = params['ibias']
        psrr_min = params['psrr']
        rload = params['rload']
        cload = params['cload']
        pm_min = params['pm']

        vth_ser = estimate_vth(db=db_dict['ser'],
                               is_nch=ser_type=='n',
                               lch=l_dict['ser'],
                               vgs=vdd-vout if ser_type=='n' else vout-vdd,
                               vbs=0-vout if ser_type=='n' else vdd-vdd)
        
        # Spec out amplifier
        amp_specfile_dict = dict()
        amp_th_dict = dict()
        amp_l_dict = dict()

        for k in ('in', 'tail', 'load'):
            amp_specfile_dict[k] = specfile_dict[f'amp_{k}']
            amp_th_dict[k] = th_dict[f'amp_{k}']
            amp_l_dict[k] = l_dict[f'amp_{k}']
        amp_dsn_params = dict(params['amp_dsn_params'])
        amp_dsn_params.update(dict(vincm=vout,
                                   specfile_dict=amp_specfile_dict,
                                   th_dict=amp_th_dict,
                                   l_dict=amp_l_dict,
                                   sim_env=sim_env,
                                   vdd=vdd))

        # Spec out biasing
        bias_specfile_dict = dict()
        bias_th_dict = dict()
        bias_l_dict = dict()
        for k in ('n', 'p'):
            bias_specfile_dict[k] = specfile_dict[f'bias_{k}']
            bias_th_dict[k] = th_dict[f'bias_{k}']
            bias_l_dict[k] = l_dict[f'bias_{k}']
        bias_dsn_params = dict(params['bias_dsn_params'])
        bias_dsn_params.update(dict(specfile_dict=bias_specfile_dict,
                                       th_dict=bias_th_dict,
                                       l_dict=bias_l_dict,
                                       sim_env=sim_env,
                                       vdd=vdd))

        # Keep track of viable ops
        viable_op_list = []

        amp_dsn_mod = bag2_analog__amp_diff_mirr_dsn()
        bias_dsn_mod = bag2_analog__constant_gm_dsn()

        # Sweep gate bias voltage of the series device
        vg_min = vout+vth_ser
        vg_max = min(vdd+vth_ser, vdd)
        vg_vec = np.arange(vg_min, vg_max, 10e-3)

        for vg in vg_vec:
            print('Designing the series device...')
            # Size the series device
            match_ser, ser_info = self.dsn_fet(vg=vg, **params)
            if not match_ser:
                continue
            print('Done')

            # Design amplifier s.t. output bias = gate voltage
            # This is to maintain accuracy in the computational design proces
            print('Designing the amplifier...')
            ser_op = ser_info['op']
            amp_cload = ser_op['cgg']
            amp_dsn_params.update(dict(cload=amp_cload,
                                       optional_params=dict(voutcm=vg),
                                       ibias=ibias_max))
            try:
                disable_print()
                amp_dsn_lst = amp_dsn_mod.meet_spec(**amp_dsn_params)
            except ValueError:
                continue
            finally:
                enable_print()
            print(f'{len(amp_dsn_lst)} viable amps')

            # For each possibility, design the biasing
            for amp_dsn_info in amp_dsn_lst:
                if amp_dsn_params['in_type'] == 'n':
                    bias_dsn_params.update(dict(vref=dict(n=amp_dsn_info['vgtail']),
                                                res_side='n'),
                                                ibias=ibias_max-amp_dsn_info['ibias'])
                else:
                    bias_dsn_params.update(dict(vref=dict(p=amp_dsn_info['vgtail']),
                                                res_side='p'),
                                                ibias=ibias_max-amp-dsn_info['ibias'])

                print(f'Attempting to design biasing...')
                try:
                    disable_print()
                    _, bias_dsn_info = bias_dsn_mod.design(**bias_dsn_params)
                except ValueError:
                    continue
                finally:
                    enable_print()
                print('Done')

                op_dict = {'in' : amp_dsn_info['op_in'],
                           'tail' : amp_dsn_info['op_tail'] ,
                           'load' : amp_dsn_info['op_load'],
                           'ser' : ser_info['op']}

                nf_dict = {'in' : amp_dsn_info['nf_in'],
                           'tail' : amp_dsn_info['nf_tail'],
                           'load' : amp_dsn_info['nf_load'],
                           'ser' : ser_info['nf']}

                # TODO Check against transient load - use Jackson's (likely need to modify)

                # Check PSRR
                psrr_lti = self._get_psrr_lti(op_dict=op_dict,
                                              nf_dict=nf_dict,
                                              series_type=ser_type,
                                              amp_in=amp_dsn_params['in_type'],
                                              rload=rload,
                                              cload=cload)

                if psrr_lti < psrr_min:
                    print(f'psrr {psrr_lti}')
                    continue

                # TODO Check STB against simulation
                pm_lti = self._get_stb_lti(op_dict=op_dict, 
                                       nf_dict=nf_dict, 
                                       series_type=ser_type,
                                       rload=rload,
                                       cload=cload)

                if np.isnan(pm_lti):
                    pm_lti = -1

                if pm_lti < pm_min:
                    print(f'pm {pm_lti}')
                    continue

                viable_op = dict(amp_params=amp_dsn_info,
                                 bias_params=bias_dsn_info,
                                 ser_params=ser_info, 
                                 pm=pm_lti,
                                 psrr=psrr_lti,
                                 vg=vg)

                pprint(viable_op)
                viable_op_list.append(viable_op)


        self.other_params = dict(l_dict=l_dict,
                                 w_dict={k:db.width_list[0] for k,db in db_dict.items()},
                                 rload=rload,
                                 cload=cload)

        return viable_op_list

    def _get_psrr_lti(self, op_dict, nf_dict, series_type, amp_in, rload, cload) -> float:
        
        n_ser = series_type == 'n'
        n_amp = amp_in == 'n'

        # Supply -> output gain
        ckt_sup = LTICircuit()
        ser_d = 'vdd' if n_ser else 'reg'
        ser_s = 'reg' if n_ser else 'vdd'
        inp_conn = 'gnd' if n_ser else 'reg'
        inn_conn = 'reg' if n_ser else 'gnd'
        tail_rail = 'gnd' if n_amp else 'vdd'
        load_rail = 'vdd' if n_amp else 'gnd'
        ckt_sup.add_transistor(op_dict['ser'], ser_d, 'out', ser_s, fg=nf_dict['ser'], neg_cap=False)
        ckt_sup.add_res(rload, 'reg', 'gnd')
        ckt_sup.add_cap(rload, 'reg', 'gnd')
        ckt_sup.add_transistor(op_dict['in'], 'outx', inp_conn, 'tail', fg=nf_dict['in'], neg_cap=False)
        ckt_sup.add_transistor(op_dict['in'], 'out', inn_conn, 'tail', fg=nf_dict['in'], neg_cap=False)
        ckt_sup.add_transistor(op_dict['tail'], 'tail', 'gnd', tail_rail, fg=nf_dict['tail'], neg_cap=False)
        ckt_sup.add_transistor(op_dict['load'], 'outx', 'outx', load_rail, fg=nf_dict['load'], neg_cap=False)
        ckt_sup.add_transistor(op_dict['load'], 'out', 'outx', load_rail, fg=nf_dict['load'], neg_cap=False)

        num_sup, den_sup = ckt_sup.get_num_den(in_name='vdd', out_name='reg', in_type='v')
        gain_sup = num_sup[-1]/den_sup[-1]

        # Reference -> output gain
        # ckt_norm = LTICircuit()
        # ser_d = 'gnd' if n_ser else 'reg'
        # ser_s = 'reg' if n_ser else 'gnd'
        # inp_conn = 'in' if n_ser else 'reg'
        # inn_conn = 'reg' if n_ser else 'in'
        # ckt_norm.add_transistor(op_dict['ser'], ser_d, 'out', ser_s, fg=nf_dict['ser'], neg_cap=False)
        # ckt_norm.add_res(rload, 'reg', 'gnd')
        # ckt_norm.add_cap(rload, 'reg', 'gnd')
        # ckt_norm.add_transistor(op_dict['in'], 'outx', inp_conn, 'tail', fg=nf_dict['in'], neg_cap=False)
        # ckt_norm.add_transistor(op_dict['in'], 'out', inn_conn, 'tail', fg=nf_dict['in'], neg_cap=False)
        # ckt_norm.add_transistor(op_dict['tail'], 'tail', 'gnd', 'gnd', fg=nf_dict['tail'], neg_cap=False)
        # ckt_norm.add_transistor(op_dict['load'], 'outx', 'outx', 'gnd', fg=nf_dict['load'], neg_cap=False)
        # ckt_norm.add_transistor(op_dict['load'], 'out', 'outx', 'gnd', fg=nf_dict['load'], neg_cap=False)

        # num_norm, den_norm = ckt_norm.get_num_den(in_name='in', out_name='reg', in_type='v')
        # gain_norm = num_norm[-1]/den_norm[-1]

        if gain_sup == 0:
            return float('inf')

        return 10*np.log10((1/gain_sup)**2)

    def _get_stb_lti(self, op_dict, nf_dict, series_type, rload, cload) -> float:
        '''
        Returns:
            pm: Phase margins (in degrees)
        '''
        ckt = LTICircuit()

        n_ser = series_type == 'n'
       
        # Series device
        ser_d = 'gnd' if n_ser else 'reg'
        ser_s = 'reg' if n_ser else 'gnd'
        ckt.add_transistor(op_dict['ser'], ser_d, 'out', ser_s, fg=nf_dict['ser'], neg_cap=False)

        # Load passives
        ckt.add_res(rload, 'reg', 'gnd')
        ckt.add_cap(rload, 'reg', 'gnd')
        # TODO include any compensation passives

        # Amplifier
        inp_conn = 'gnd' if n_ser else 'in'
        inn_conn = 'gnd' if not n_ser else 'in' 
        ckt.add_transistor(op_dict['in'], 'outx', inp_conn, 'tail', fg=nf_dict['in'], neg_cap=False)
        ckt.add_transistor(op_dict['in'], 'out', inn_conn, 'tail', fg=nf_dict['in'], neg_cap=False)
        ckt.add_transistor(op_dict['tail'], 'tail', 'gnd', 'gnd', fg=nf_dict['tail'], neg_cap=False)
        ckt.add_transistor(op_dict['load'], 'outx', 'outx', 'gnd', fg=nf_dict['load'], neg_cap=False)
        ckt.add_transistor(op_dict['load'], 'out', 'outx', 'gnd', fg=nf_dict['load'], neg_cap=False)

        # Calculating stability margins
        num, den = ckt.get_num_den(in_name='in', out_name='reg', in_type='v')
        pm, _ = get_stability_margins(np.convolve(num, [-1]), den)

        return pm

    def _get_stb_sim(self, **spec):
        pass
        # return pm

    def _get_psrr_sim(self, **spec):
        pass

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
        return op1 if op1['ibias'] < op2['ibias'] else op2

    def get_sch_params(self, op):
        return dict()