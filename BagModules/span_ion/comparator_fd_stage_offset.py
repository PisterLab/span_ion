# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_stage_offset(Module):
    """Module for library span_ion cell comparator_fd_stage_offset.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_stage_offset.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str,str]:
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            in_type = 'n or p for NMOS or PMOS input pair',
            num_bits = 'Thermometer; number of bits for offset gain control',
            main_params = 'primary amplifier parameters',
            offset_params = 'offset cancellation parameters for offset removal',
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
        in_type = params['in_type']
        num_bits = params['num_bits']
        main_params = params['main_params']
        offset_params = params['offset_params']

        ### Design instances
        self.instances['XMAIN'].design(in_type=in_type, **main_params)
        self.instances['XOFFSET'].design(in_type=in_type, **offset_params)

        ### DAC control
        if num_bits > 1:
            suffix_dac = f'<{num_bits-1}:0>'
            # Array and wire up offset cancellation amp
            self.array_instance('XOFFSET', [f'XOFFSET{suffix_dac}'], [dict(VDD='VDD',
                                                                           VSS='VSS',
                                                                           VOUTP='VOUTP',
                                                                           VOUTN='VOUTN',
                                                                           IBP='IBP_OS',
                                                                           IBN='IBN_OS',
                                                                           VINP='VOSP',
                                                                           VINN='VOSN',
                                                                           B=f'B{suffix_dac}',
                                                                           Bb=f'Bb{suffix_dac}')])
            # Rename control pin
            rm_ctrl = 'Bb' if in_type == 'n' else 'B'
            kp_ctrl = 'B' if in_type == 'n' else 'Bb'
            self.remove_pin(rm_ctrl)
            self.rename_pin(kp_ctrl, f'{kp_ctrl}{suffix_dac}')

        ### Wiring up biasing for main amp and removing unnecessary biasing pins
        if in_type == 'p':
            self.remove_pin('IBN_MAIN')
            self.remove_pin('IBN_OS')
            self.reconnect_instance_terminal('XMAIN', 'IBP', 'IBP_MAIN')
        else:
            self.remove_pin('IBP_MAIN')
            self.remove_pin('IBP_OS')