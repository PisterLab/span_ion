# -*- coding: utf-8 -*-

from typing import Mapping, Tuple, Any

import os
import pkg_resources
import numpy as np

from bag.design.module import Module
from . import DesignModule, get_mos_db, estimate_vth, parallel, verify_ratio, num_den_add
from bag.data.lti import LTICircuit, get_w_3db, get_stability_margins

# noinspection PyPep8Naming
class bag2_analog__bandgap_dsn(DesignModule):
    """Module for library bag2_analog cell bandgap.

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
            th_dict = 'Transistor flavor dictionary.',
            l_dict = 'Transistor channel length dictionary',
            sim_env = 'Simulation environment',
            diode_params = 'tempco=temperature coefficient of 1 device (+V/K), isat=300K saturation current, swing=V/decade of current',
            vdd = 'Supply voltage in volts.',
            diode_mult = 'Multiplier for diodes',
            amp_dsn_params = 'Amplifier parameters excepting physical device parameters and input/output biasing',
            constgm_dsn_params = 'Constant gm design parameters excepting physical device parameters, resistor side, and voltages'
        ))
        return ans

    def dsn_passives(self, **params) -> Mapping[str,Any]:
        """
        """
        vdd = params['vdd']
        diode_mult = params['diode_mult']

        # TODO ideally there would be some diode characterization, but we calculate things for now
        diode_params = params['diode_params']
        tempco_1x = diode_params['tempco']
        isat_1x = diode_params['isat']
        ion = diode_params['ion']
        swing = diode_params['swing']

        # Databases
        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        ### Calculate resistor values ###
        # Calculate room temperature voltages of the diodes
        vdio_1x = np.log10(ion/isat) * swing
        vdio_Nx = np.log10((ion/diode_mult)/isat) * swing
        tempco_diff = (vdio_1x-vdio_Nx)/300

        # Calculate the required resistor values to get 0 temperature coefficient on output voltage
        res_mult = tempco_1x / tempco_diff
        rval_diff = (vdio_1x - viode_Nx)/ion
        rval_fb = rval_diff * res_mult

        vbg = vdio_1x + res_mult*(vdio_1x-vdio_Nx)

        return dict(vbg=vbg,
                    amp_vincm=vdio_1x,
                    rval_diff=rval_diff,
                    rval_fb=rval_fb,
                    ibranch=ion)

    def verify_pmos(self, db:MOSDBDiscrete, vg:float, vbg:float, ibias:float):
        p_op = db.query(vgs=vg-vdd, vbg-vdd, vbs=0)
        match_p, nf_p = verify_ratio(ibias, p_op['ibias'], 1, 0.1)

        if not match_p:
            return False, 0

        else:
            return True, nf_p


    def meet_spec(self, **params) -> Tuple[Mapping[str,Any],Mapping[str,Any]]:
        """To be overridden by subclasses to design this module.

        Raises a ValueError if there is no solution.
        """
        ### Get DBs for each device
        specfile_dict = params['specfile_dict']
        l_dict = params['l_dict']
        th_dict = params['th_dict']
        sim_env = params['sim_env']
        
        # Databases
        db_dict = {k:get_mos_db(spec_file=specfile_dict[k],
                                intent=th_dict[k],
                                sim_env=sim_env) for k in specfile_dict.keys()}

        # TODO: vstar min not hardcoded
        vstar_min = 0.25

        # Get info regarding the passives outside the amplifier and constant gm
        passive_info = self.dsn_passives(vdd=vdd,
                                         diode_mult=diode_mult)
        
        # Spec out amplifier
        vbg = passive_info['vbg']
        idiode = passive_info['ibranch']
        vth_p = estimate_vth(is_nch=False, vgs=vbg-vdd, vds=vbg-vdd, vbs=0)
        vg_min = vbg + vth_p
        vg_max = vdd + vth_p - vstar_min
        vg_vec = np.arange(vg_min, vg_max, 10e-3)

        amp_specfile_dict = dict()
        amp_th_dict = dict()
        amp_l_dict = dict()

        for k in ('in', 'tail', 'load'):
            amp_specfile_dict[k] = specfile_dict[f'amp_{k}']
            amp_th_dict[k] = th_dict[f'amp_{k}']
            amp_l_dict[k] = l_dict[f'amp_{k}']
        amp_dsn_params = dict(params['amp_dsn_params'])
        amp_dsn_params.update(dict(vincm=loop_info['amp_vincm'],
                                   specfile_dict=amp_specfile_dict,
                                   th_dict=amp_th_dict,
                                   l_dict=amp_l_dict,
                                   sim_env=sim_env))

        # Spec out constant gm
        constgm_specfile_dict = dict()
        constgm_th_dict = dict()
        constgm_l_dict = dict()
        for k in ('n', 'p'):
            constgm_specfile_dict[k] = specfile_dict[f'constgm_{k}']
            constgm_th_dict[k] = th_dict[f'constgm_{k}']
            constgm_l_dict[k] = l_dict[f'constgm_{k}']
        constgm_dsn_params = dict(params['constgm_dsn_params'])
        constgm_dsn_params.update(dict(specfile_dict=constgm_specfile_dict,
                                       th_dict=constgm_th_dict,
                                       l_dict=constgm_l_dict,
                                       sim_env=sim_env))

        # Keep track of viable ops
        viable_op_list = []

        # Design active components
        for vg in vg_vec:
            # Match the PMOS size if possible
            match_p, nf_p = verify_pmos(db=db_dict['p'], vg=vg, vbg=vbg, ibias=idiode)
            if not match_p:
                continue

            # TODO: design amplifier
            amp_dsn_params.update(dict(optional_params=dict(voutcm=passive_info['amp_voutcm'])))

            try:
                amp_info = ()
            except ValueError:
                continue

            # Spec out constant gm
            if amp_dsn_params['in_type'] == 'n':
                constgm_dsn_params.update(dict(vref=dict(n=amp_info['vgtail']),
                                               res_side='n'))
            else:
                constgm_dsn_params.update(dict(vref=dict(p=amp_info['vgtail']),
                                               res_side='p'))

            # TODO: design constant gm
            constgm_info = ()

            # TODO: viable op
            viable_op_list.append(dict())

        if len(viable_op_list) < 1:
            raise ValueError("No solution")

        best_op = viable_op_list[0]
        for op in viable_op_list:
            best_op = self.op_compare(op, best_op)




        print(f"(RESULT) {sch_params}\n{best_op}")

        return sch_params, best_op

    def op_compare(self, op1:Mapping[str,Any], op2:Mapping[str,Any]):
        """Returns the best operating condition based on 
        minimizing bias current.
        """
        return op2 if op1['ibias'] > op2['ibias'] else op1