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
            load_reg = 'Maximum fractional change in output voltage given change in output current',
            ibias = 'Maximum bias current of amp and biasing, in amperes.',
            zload = 'TransferFunctions of the load impedance at nominal point (sans decap)',
            psrr = 'Minimum power supply rejection (linear, not dB)',
            amp_dsn_params = "Amplifier design parameters that aren't either calculated or handled above",
            optional_params = 'Optional parameters. voutcm=output bias voltage.'
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
        zload = params['zload']

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

        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        ser_type = params['series_type']
        vdd = params['vdd']
        vout = params['vout']
        load_reg = params['load_reg']
        ibias = params['ibias']
        zload = params['zload']
        psrr = params['psrr']

        vth_ser = estimate_vth(db=db_dict['ser'],
                               is_nch=ser_type=='n',
                               lch=l_dict['ser'],
                               vgs=vdd-vout if ser_type=='n' else vout-vdd,
                               vbs=0-vout if ser_type=='n' else vdd-vdd)
        
        # Spec out amplifier
        amp_specfile_dict = dict()
        amp_th_dict = dict()
        amp_l_dict = dict()

        for k in (): # TODO
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

        # Spec out biasing


        viable_op_list = []
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

            # TODO Design biasing
            try:
                disable_print()
                bias_dsn_list = bias_dsn_mod.meet_spec(**bias_dsn_params)
            except ValueError:
                continue
            finally:
                enable_print()


        return viable_op_list

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):

    def get_sch_params(self, op):
