# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__peak_detector_basic2(Module):
    """Module for library span_ion cell peak_detector_basic2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'peak_detector_basic2.yaml'))


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
            constgm_params_list = 'List of parameters for the constant gm',
            cap_params = 'Capacitor parameters',
            rst_params = 'Parameters for the reset switch'
        )

    def design(self, **params):
        amp_params_list = params['amp_params_list']
        constgm_params_list = params['constgm_params_list']
        cap_params = params['cap_params']
        rst_params = params['rst_params']

        # Design instances
        self.instances['XAMP<0>'].design(**(amp_params_list[0]))
        self.instances['XAMP<1>'].design(**(amp_params_list[1]))
        self.instances['XCONSTGM<0>'].design(**(constgm_params_list[0]))
        self.instances['XCONSTGM<1>'].design(**(constgm_params_list[1]))
        self.instances['XRST'].design(**rst_params)

        self.instances['XCAP'].parameters = cap_params

        # Switching up tail connection to constant gm as necessary
        for i in range(2):
            if amp_params_list[i]['in_type'] == 'p':
                self.reconnect_instance_terminal(f'XAMP<{i}>', 'VGTAIL', f'VP<{i}>')