# -*- coding: utf-8 -*-

from typing import Mapping

import os
import pkg_resources
import warnings

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__one_shot_nand(Module):
    """Module for library span_ion cell one_shot_nand.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'one_shot_nand.yaml'))


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
        inv_in_params = params['inv_in_params']
        nand_params = params['nand_params']
        inv_chain_params = params['inv_chain_params']
        res_params = params['res_params']
        cap_params = params['cap_params']
        nor_params = params['nor_params']
        rst_params = params['rst_params']

        inv_chain_length = len(inv_chain_params['inv_param_list'])

        assert inv_chain_length >= 2, f'Length of inverter chain {inv_chain_length} must be >= 2'

        # Design instances
        self.instances['XINV_IN'].design(**inv_in_params)
        self.instances['XNAND'].design(num_in=2, **nand_params)
        self.instances['XINV_OUT'].design(dual_output=True, **inv_chain_params)
        self.instances['XNOR'].design(num_in=3, **nor_params)
        self.instances['XRST'].design(mos_type='n', **rst_params)

        self.instances['XR'].design(**res_params)

        warnings.warn('(one_shot_nand) check cap values generated correctly')
        self.instances['XC'].parameters = cap_params

        self.reconnect_instance_terminal('XNAND', 'in<1:0>', 'inb,outb')
        self.reconnect_instance_terminal('XNOR', 'in<2:0>', 'in,in_gate,out')