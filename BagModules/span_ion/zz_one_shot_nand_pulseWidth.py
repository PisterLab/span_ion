# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__zz_one_shot_nand_pulseWidth(Module):
    """Module for library span_ion cell zz_one_shot_nand_pulseWidth.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'zz_one_shot_nand_pulseWidth.yaml'))


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
            num_bits = 'Number of tuning bits for the resistor',
            inv_in_params = 'Input inverter parameters',
            nand_params = 'NAND parameters',
            nor_params = 'reset NOR parameters',
            rst_params = 'reset switch parameters',
            inv_chain_params = 'Inverter chain parameters',
            res_params = 'RC resistor parameters',
            cap_params = 'RC cap parameters'
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
        self.instances['XONESHOT'].design(**params)

        num_bits = params['num_bits']

        assert num_bits < 3, f'Currently only supports up to 2 control bits ({num_bits} > 2)'

        suffix_pin = f'<{num_bits-1}:0>' if num_bits > 1 else ''
        suffix_net = suffix_pin if num_bits > 1 else '<0>'
        self.reconnect_instance_terminal('XONESHOT', f'CTRLb{suffix_pin}', f'CTRLb{suffix_net}')