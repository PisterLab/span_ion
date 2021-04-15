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
            num_bits = 'Number of bits for offset gain control',
            main_params = 'primary amplifier parameters',
            offset_params = 'offset cancellation parameters',
            constgm_params = 'constant gm biasing parameters'
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
        constgm_params = params['constgm_params']

        # Design instances
        self.instances['XMAIN'].design(in_type=in_type, **main_params)
        self.instances['XOFFSET'].design(num_bits=num_bits, in_type=in_type, **offset_params)
        self.instances['XCONSTGM'].design(res_side=in_type, **constgm_params)

        # Reconnect constant gm
        reconn_pin = 'VP' if in_type=='p' else 'VN'
        self.reconnect_instance_terminal('XCONSTGM', reconn_pin, 'VGTAIL')

        # Rename control pin and rewire if necessary
        ctrl_base = 'Bb' if in_type == 'p' else 'B'
        ctrl_suffix = f'<{num_bits-1}:0>' if num_bits > 1 else ''
        if num_bits > 1 or in_type != 'n':
            net_ctrl = f'{ctrl_base}{ctrl_suffix}'
            self.rename_pin('B', net_ctrl)
            self.reconnect_instance_terminal('XOFFSET', net_ctrl, net_ctrl)