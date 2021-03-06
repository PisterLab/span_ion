# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_stage_cmfb(Module):
    """Module for library span_ion cell comparator_fd_stage_cmfb.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_stage_cmfb.yaml'))


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
            in_type='n or p for PMOS or NMOS input pair',
            main_params='Main amplifier parameters',
            cmfb_idx='1 for switch-side input, 2 for same-side input, 3 for same-side, non-mirrored input',
            cmfb_params='Common mode feedback parameters',
            constgm_params='CMFB constant gm parameters'
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
        cmfb_idx = params['cmfb_idx']

        opp_type = 'n' if in_type == 'p' else 'p'
        cmfb_in_type = in_type if cmfb_idx in (2, 3) else opp_type

        main_params = params['main_params']
        cmfb_params = params['cmfb_params']

        constgm_params = params['constgm_params']

        self.instances['XMAIN'].design(in_type=in_type, **main_params)

        if cmfb_idx == 1:
            self.replace_instance_master(inst_name='XCMFB',
                                         lib_name='span_ion',
                                         cell_name='comparator_fd_cmfb')
        elif cmfb_idx == 3:
            self.replace_instance_master(inst_name='XCMFB',
                                         lib_name='span_ion',
                                         cell_name='comparator_fd_cmfb3')
            self.reconnect_instance_terminal('XCMFB', 'VOUT', 'VCMFB')

        self.instances['XCMFB'].design(in_type=cmfb_in_type, **cmfb_params)
        self.instances['XCONSTGM'].design(res_side=cmfb_in_type,
                                          **constgm_params)

        if cmfb_in_type == 'n':
            self.reconnect_instance_terminal('XCONSTGM', 'VN', 'VGTAIL_CMFB')
        elif cmfb_in_type == 'p':
            self.reconnect_instance_terminal('XCONSTGM', 'VP', 'VGTAIL_CMFB')
        else:
            raise ValueError(f"input type should be n or p, not {in_type}")

