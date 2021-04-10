# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources
import warnings

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_az_fb(Module):
    """Module for library span_ion cell comparator_az_fb.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_az_fb.yaml'))


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
            mos_type = '"n", "p", or "both" to indicate NMOS, PMOS, or tgate, respectively',
            mos_params_dict = 'Dictionary of transistor parameters (keys n, p)',
            cap_params = 'Capacitor parameters',
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
        mos_type = params['mos_type']
        mos_params_dict = params['mos_params_dict']
        cap_params = params['cap_params']

        has_n = mos_type != 'p'
        has_p = mos_type != 'n'

        if not has_n:
            self.remove_pin('PHI')

        if not has_p:
            self.remove_pin('PHIb')

        self.instances['XCAPA'].parameters = cap_params
        self.instances['XCAPB'].parameters = cap_params

        warnings.warn("(comparator_az_fb) double check passive values in generated schematic")

        ### Designing instances
        self.instances['XFBA'].design(mos_type=mos_type, mos_params_dict=mos_params_dict)
        self.instances['XFBB'].design(mos_type=mos_type, mos_params_dict=mos_params_dict)