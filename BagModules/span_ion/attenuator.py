# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__attenuator(Module):
    """Module for library span_ion cell attenuator.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'attenuator.yaml'))


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
            num_bits = 'Number of tuning bits for the tunable resistor',
            res_tune_params = 'Tunable resistor parameters',
            res_static_params = 'Static resistor parameters',
            inv_params = 'Parameters for control bit buffers',
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
        num_bits = params['num_bits']
        res_tune_params = params['res_tune_params']
        res_static_params = params['res_static_params']

        inv_params = params['inv_params']

        # Design the static resistor
        self.instances['XRSTATIC'].design(**res_static_params)
        self.reconnect_instance_terminal('XRSTATIC', 'BULK', res_tune_params["bulk_conn"])
        self.remove_pin('BULK')

        # Design the tunable resistor
        self.instances['XRTUNE'].design(**res_tune_params, 
                                        res_groupings=[2**i for i in range(num_bits)])

        if num_bits > 0:
            sw_type = res_tune_params['sw_params']['mos_type']
            has_n = sw_type != 'p'
            has_p = sw_type != 'n'

            if not has_n:
                self.delete_instance('XINV_CTRL')
            
            if num_bits > 1:
                # Pin suffixes for attenuation control
                suffix = f'<{num_bits-1}:0>'
                if has_p:
                    self.rename_pin('CTRLb', f'CTRLb{suffix}')
                    self.reconnect_instance_terminal('XRTUNE', f'CTRL{suffix}', f'CTRLb{suffix}')
                
                if has_n:
                    self.reconnect_instance_terminal('XRTUNE', f'CTRLb{suffix}', f'CTRL{suffix}')

                    # Design inverters for control bits
                    self.array_instance('XINV_CTRL', [f'XINV_CTRL{suffix}'], [{'in' : f'CTRLb{suffix}',
                                                                            'out' : f'CTRL{suffix}'}])
                    self.instances['XINV_CTRL'][0].design(**inv_params)
            else:
                # Design control bit inverter
                if has_n:
                    self.instances['XINV_CTRL'].design(**inv_params)

        else:
            self.remove_instance('XINV_CTRL')
            self.remove_pin('CTRLb')