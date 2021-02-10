# -*- coding: utf-8 -*-

from typing import Dict, Mapping, Any

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__delay_tt1_ord2(Module):
    """Module for library span_ion cell delay_tt1_ord2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'delay_tt1_ord2.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, Any]:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            cap_params_list = 'List of cap parameters. Ordering can be seen by the index in the schematic.',
            res_params_list = 'List of res parameters. Ordering can be seen by the index in the schematic.',
            amp_params_list = 'List of amplifier parameters.',
            constgm_params_list = 'List of constant gm parameters.'
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
        cap_params_list = params['cap_params_list']
        res_params_list = params['res_params_list']
        amp_params_list = params['amp_params_list']
        constgm_params_list = params['constgm_params_list']

        # Design instances
        for i, res_params in enumerate(res_params_list):
            if res_params['num_unit'] == 0:
                self.delete_instance(f'XR<{i}>')
            else:
                self.instances[f'XR<{i}>'].design(**res_params)

        for i, cap_params in enumerate(cap_params_list):
            self.instances[f'XC<{i}>'].parameters = cap_params

        print('*** WARNING *** (delay_tt1_ord2) Check passive component values in generated schematic.', flush=True)

        for idx_constgm, constgm_params in enumerate(constgm_params_list):
            self.instances[f'XCONSTGM<{idx_constgm}>'].design(**constgm_params)

        for idx_amp, amp_params in enumerate(amp_params_list):
            self.instances[f'XAMP<{idx_amp}>'].design(**amp_params)

            # Switching up tail connection to constant gm as necessary
            if amp_params_list[i]['in_type'] == 'n':
                self.reconnect_instance_terminal(f'XAMP<{i}>', 'VGTAIL', f'VN<{i}>')