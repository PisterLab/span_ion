# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__watchdog(Module):
    """Module for library span_ion cell watchdog.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'watchdog.yaml'))


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
            inv_params = 'Inverter for CFD branch output',
            nand_params = 'NAND for CFDb and LED',
            oneshot_led_params = 'One-shot pulse generator for the LED output',
            oneshot_stuck_params = 'One-shot pulse generator for the reset pulse'
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
        inv_params = params['inv_params']
        nand_params = params['nand_params']
        oneshot_led_params = params['oneshot_led_params']
        oneshot_stuck_params = params['oneshot_stuck_params']

        num_led_bits = oneshot_led_params['num_bits']
        num_stuck_bits = oneshot_stuck_params['num_bits']

        ### Design blocks
        self.instances['XINV<2:0>'].design(stack_n=1, stack_p=1, **inv_params)
        for i in range(3):
            self.instances[f'XNAND<{i}>'].design(num_in=2, **nand_params)
        self.instances['XONESHOT_LED'].design(has_rst=False, **oneshot_led_params)
        self.instances['XONESHOT_STUCK'].design(has_rst=False, **oneshot_stuck_params)

        ### Wiring up control pins
        if num_led_bits > 1:
            suffix_led = f'<{num_led_bits-1}:0>'
            self.rename_pin('CTRLb_LED', f'CTRLb_LED{suffix_led}')
            self.reconnect_instance_terminal('XONESHOT_LED',
                                             f'CTRLb{suffix_led}',
                                             f'CTRLb_LED{suffix_led}')
        elif num_led_bits < 1:
            self.remove_pin('CTRLb_LED')

        if num_stuck_bits > 1:
            suffix_stuck = f'<{num_stuck_bits-1}:0>'
            self.rename_pin('CTRLb_STUCK', f'CTRLb_STUCK{suffix_stuck}')
            self.reconnect_instance_terminal('XONESHOT_STUCK',
                                             f'CTRLb{suffix_stuck}',
                                             f'CTRLb_STUCK{suffix_stuck}')
        elif num_stuck_bits < 1:
            self.remove_pin('CTRLb_STUCK')

        ### Additional wiring
        for i in range(3):
            self.reconnect_instance_terminal(f'XNAND<{i}>', 'in<1:0>', f'CFDb<{i}>,LED_1shot<{i}>')