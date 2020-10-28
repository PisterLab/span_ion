# -*- coding: utf-8 -*-

from typing import Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__delay_sk_ord2(Module):
    """Module for library span_ion cell delay_sk_ord2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'delay_sk_ord2.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            res_params_list = 'List of resistor parameters. Ordering is indicated in the schematic by the index of the resistor.',
            cap_params_list = 'List of cap parameters. Ordering is indicated in schematic indices.',
            amp_params = 'Amplifier parameters',
            constgm_params = 'Constant gm parameters'
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
        amp_params = params['amp_params']
        constgm_params = params['constgm_params']
        res_params_list = params['res_params_list']
        cap_params_list = params['cap_params_list']

        # Design instances
        self.instances['XAMP'].design(**amp_params)
        self.instances['XCONSTGM'].design(**constgm_params)

        for i in range(6):
            self.instances[f'XR<{i}>'].parameters = res_params_list[i]

        for i in range(2):
            self.instances[f'XC<{i}>'].parameters = cap_params_list[i]
        
        print('*** WARNING *** (delay_sk_ord2) Check passive component values in generated schematic.', flush=True)

        # Rewire tail biasing if necessary
        if amp_params['in_type'].lower() == 'n':
            self.reconnect_instance_terminal('XAMP', 'VGTAIL', f'VN')
        elif amp_params['in_type'].lower() == 'p':
            self.reconnect_instance_terminal('XAMP', 'VGTAIL', f'VP')
        else:
             raise ValueError(f"in_type of amplifier {amp_params['in_type']} is invalid (should be p or n)")    