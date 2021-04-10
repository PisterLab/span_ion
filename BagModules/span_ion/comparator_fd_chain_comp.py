# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources
import warnings

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_chain_comp(Module):
    """Module for library span_ion cell comparator_fd_chain_comp.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_chain_comp.yaml'))


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
            sw_params = 'Switch parameters',
            cap_params = 'Cap parameters'
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
        sw_params = params['sw_params']
        cap_params = params['cap_params']

        ### Design instances
        warnings.warn(f"(comparator_fd_chain_comp)) check generated capacitor values")

        self.instances['XCAP'].parameters = cap_params
        self.instances['XSWCAP'].design(**sw_params)

        ### Remove unnecessary pins
        has_n = sw_params['mos_type'] != 'p'
        has_p = sw_params['mos_type'] != 'n'
        
        if not has_n:
            self.remove_pin('VSS')
            self.remove_pin('PHI')

        if not has_p:
            self.remove_pin('VDD')
            self.remove_pin('PHIb')