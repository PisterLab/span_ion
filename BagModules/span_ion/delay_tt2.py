# -*- coding: utf-8 -*-

from typing import Mapping, Any

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__delay_tt2(Module):
    """Module for library span_ion cell delay_tt2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'delay_tt2.yaml'))


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
            unit_params_list = 'List of delay_tt2_ord2 parameters.'
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
        unit_params_list = params['unit_params_list']
        num_units = len(unit_params_list)

        assert num_units > 0, f'Number of units {num_units} should be > 0'

        # Wire up and design chain of instances
        if num_units > 1:
            inst_list = []
            conn_list = []
            for i in range(num_units):
                inst_list.append(f'XDELAY<{i}>')

                vin_conn = 'VIN' if i == 0 else f'm<{i-1}>'
                vout_conn = 'VOUT' if i == num_units-1 else f'm<{i}>'
                conn_list.append(dict(VDD='VDD',
                                      VSS='VSS',
                                      VIN=vin_conn,
                                      VOUT=vout_conn))

            self.array_instance('XDELAY', inst_list, conn_list)

            for i in range(num_units):
                self.instances['XDELAY'][i].design(**(unit_params_list[i]))
        else:
            self.instances['XDELAY'].design(**(unit_params_list[0]))