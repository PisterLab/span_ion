# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__peak_detector_basic1(Module):
    """Module for library span_ion cell peak_detector_basic1.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'peak_detector_basic1.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            amp_params_list = 'List of parameters for the amplifiers',
            cap_params = 'Capacitor parameters',
            rst_params_dict = 'Parameters for the reset switches'
        )

    def design(self, **params):
        amp_params_list = params['amp_params_list']
        cap_params = params['cap_params']
        rst_params_dict = params['rst_params_dict']

        # Design instances
        self.instances['XCAP'].parameters = cap_params

        print('*** WARNING *** Check passive values in generated schematic.')

        self.instances['XAMP0'].design(**(amp_params_list[0]))
        self.instances['XAMP1'].design(**(amp_params_list[1]))
        # self.instances['XCONSTGM<0>'].design(res_side=amp_params_list[0]['in_type'], **(constgm_params_list[0]))
        # self.instances['XCONSTGM<1>'].design(res_side=amp_params_list[1]['in_type'], **(constgm_params_list[1]))
        self.instances['XRST_IN1'].design(mos_type='n', **(rst_params_dict['in1']))
        self.instances['XRST_OUT'].design(mos_type='n', **(rst_params_dict['out']))

        # Switching up current source/sink as necessary
        num_n = 0
        num_p = 0
        for i in range(2):
            amp_type = amp_params_list[i]['in_type']
            if amp_type == 'p':
                num_p = num_p + 1
            else:
                num_n = num_n + 1

        if num_n == 0 or num_p == 0:
            pin_remove = 'IBN' if num_n == 0 else 'IBP'
            pin_rename = 'IBP' if num_n == 0 else 'IBN'
            self.remove_pin(pin_remove)
            self.rename_pin(pin_rename, f'{pin_rename}<1:0>')
            self.reconnect_instance_terminal('XAMP0', pin_rename, f'{pin_rename}<0>')
            self.reconnect_instance_terminal('XAMP1', pin_rename, f'{pin_rename}<1>')