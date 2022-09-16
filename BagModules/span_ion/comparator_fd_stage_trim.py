# -*- coding: utf-8 -*-

from typing import Dict

import os, warnings
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_stage_trim(Module):
    """Module for library span_ion cell comparator_fd_stage_trim.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_stage_trim.yaml'))


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
            amp_params = 'comparator_fd_stage parameters',
            trim_n_params = 'Empty if unused. N side current DAC parameters (dac_offset).',
            trim_p_params = 'Empty if unused. P side current DAC parameters (dac_offset).'
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
        trim_n_params = params['trim_n_params']
        trim_p_params = params['trim_p_params']

        pin_del_lst = []

        ### Amplifier
        self.instances['XAMP'].design(**amp_params)

        # Change pins as necessary
        if amp_params['in_type'] == 'p':
            self.rename_pin('IBN_AMP', 'IBP_AMP')
            self.reconnect_instance_terminal('XAMP', 'IBP', 'IBP_AMP')

        ### N-side trim
        if trim_n_params:
            self.instances['XTRIMN'].design(**trim_n_params, in_type='n')
            num_bits_n = len(trim_n_params['mirr_params']['seg_out_list'])
            if num_bits_n > 1:
                suffix_down = f'<{num_bits_n-1}:0>'
                pin_b_down = f'B_DOWN{suffix_down}'
                self.reconnect_instance_terminal('XTRIMN', f'B{suffix_down}', pin_b_down)
                self.rename_pin('B_DOWN', pin_b_down)
        else:
            self.delete_instance('XTRIMN')
            pin_del_lst = pin_del_lst + ['PULLDOWN_P', 'PULLDOWN_N', 'IBN_TRIM', 'B_DOWN']

        ### P-side trim
        if trim_p_params:
            self.instances['XTRIMP'].design(**trim_p_params, in_type='p')
            num_bits_p = len(trim_p_params['mirr_params']['seg_out_list'])
            self.reconnect_instance_terminal('XTRIMP', 'PULLAb', 'PULLUPb_P')
            self.reconnect_instance_terminal('XTRIMP', 'PULLBb', 'PULLUPb_N')
            if num_bits_p > 1:
                suffix_up = f'<{num_bits_p - 1}:0>'
                pin_bb_up = f'Bb_UP{suffix_up}'
                self.reconnect_instance_terminal('XTRIMP', f'Bb{suffix_up}', pin_bb_up)
                self.rename_pin('Bb_UP', pin_bb_up)
        else:
            self.delete_instance('XTRIMP')
            pin_del_lst = pin_del_lst + ['PULLUPb_P', 'PULLUPb_N', 'IBP_TRIM', 'Bb_UP']

        ### Delete unnecessary pins
        for p in pin_del_lst:
            self.remove_pin(p)