# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module

from bag2_analog.regulator_ldo_series import bag2_analog__regulator_ldo_series

# noinspection PyPep8Naming
class span_ion__zz_regulator_ldo_series_tranLoad(Module):
    """Module for library span_ion cell zz_regulator_ldo_series_tranLoad.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'zz_regulator_ldo_series_tranLoad.yaml'))


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
            series_params = 'Parameters "type" (n/p), and the various device parameters (assumes MOSFET)',
            amp_params = 'amp_folded_cascode parameters',
            biasing_params = 'TODO',
            cap_conn_list = 'List of dictionaries of device connections',
            cap_param_list = 'List of dictionaries containing device parameters',
            res_conn_list = 'List of dictionaries of device connections',
            res_param_list = 'List of dictionaries containing device parameters',
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
        self.instances['XREG'].design(**params)

