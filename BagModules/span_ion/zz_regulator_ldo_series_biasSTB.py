# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__zz_regulator_ldo_series_biasSTB(Module):
    """Module for library span_ion cell zz_regulator_ldo_series_biasSTB.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'zz_regulator_ldo_series_biasSTB.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            series_params = 'Parameters "type" (n/p), and the various device parameters (assumes MOSFET)',
            amp_params = 'amp_folded_cascode parameters',
            biasing_params = 'TODO',
            cap_conn_list = 'List of dictionaries of device connections',
            cap_param_list = 'List of dictionaries containing device parameters',
            res_conn_list = 'List of dictionaries of device connections',
            res_param_list = 'List of dictionaries containing device parameters',
        )

    def design(self, **params):
        """To be overridden by subclasses to design this module.

        This method should fill in values for all parameters in
        self.parameters.  To design instances of this module, you can
        call their design() method or any other ways you coded.

        To modify schematic structure, call:

        rename_pin()
        delete_instance()
        replace_instance_master()
        reconnect_instance_terminal()
        restore_instance()
        array_instance()
        """
        ### Instantiating the parts of the regulator
        series_params = params['series_params']
        cap_conn_list = params['cap_conn_list']
        cap_param_list = params['cap_param_list']
        res_conn_list = params['res_conn_list']
        res_param_list = params['res_param_list']
        amp_params = params['amp_params']
        biasing_params = params['biasing_params']

        # Design the series device and reconnect as necessary
        series_type = series_params['type']
        if series_type != 'n':
            self.replace_instance_master(inst_name='XSERIES',
                                         lib_name='BAG_prim',
                                         cell_name=f'{series_type}mos4_standard')

            series_conn = dict(G='VG',
                               S='VDD',
                               D='VREG',
                               B='VDD')
            for pin, net in series_conn.items():
                self.reconnect_instance_terminal('XSERIES', pin, net)

        self.instances['XSERIES'].design(l=series_params['l'],
                                         w=series_params['w'],
                                         intent=series_params['intent'],
                                         nf=series_params['nf'])

        # Design and connect the capacitors
        num_caps = len(cap_conn_list)
        if num_caps < 1:
            self.delete_instance('XCAP')
        else:
            self.array_instance('XCAP', 
                                [f'XCAP<{i}>' for i in range(num_caps)],
                                cap_conn_list)
            for i, cap_params in enumerate(cap_param_list):
                self.instances['XCAP'][i].parameters = cap_params

            print("*** WARNING *** Double-check capacitor parameters in generated schematic")

        # Design and connect resistors
        num_res = len(res_conn_list)
        if num_res < 1:
            self.delete_instance('XRES')
        else:
            self.array_instance('XRES',
                                [f'XRES<{i}>' for i in range(num_res)],
                                res_conn_list)
            for i, res_params in enumerate(res_param_list):
                self.instances['XRES'][i].design(**res_params)

        # Design amplifier
        self.instances['XAMP'].design(**amp_params)

        # Reconnect amp inputs if inversion is necessary
        if series_type == 'p':
            self.reconnect_instance_terminal('XAMP', 'VINP', 'VREGX')
            self.reconnect_instance_terminal('XAMP', 'VINN', 'VREF')

        # TODO Design biasing, this biasing willlikely change
        res_side = 'n' if amp_params['in_type']=='n' else 'p'
        self.instances['XBIAS'].design(res_side=res_side, **biasing_params)

        if amp_params['in_type'] == 'n':
            self.reconnect_instance_terminal('XBIAS', 'VN', 'VGTAIL')
        elif amp_params['in_type'] == 'p':
            self.reconnect_instance_terminal('XBIAS', 'VP', 'VGTAIL')