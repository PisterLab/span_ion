# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources
import warnings

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__preamp(Module):
    """Module for library span_ion cell preamp.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'preamp.yaml'))


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
            amp_params = 'Amplifier schematic generator parameters',
            bias_params = 'Bias circuit schematic generator parameters',
            res_params = 'Feedback resistor parameters. Empty dictionary if not necessary.',
            res_bulk = 'Bulk connection for the resistor',
            cap_params = 'Feedback capacitor parameters. Empty dictionary if not necessary.',
            sw_params = 'Reset switch parameters. Empty dictionary if not necessary.'
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
        amp_params = params['amp_params']
        bias_params = params['bias_params']
        res_params = params['res_params']
        res_bulk = params['res_bulk']
        cap_params = params['cap_params']
        sw_params = params['sw_params']

        has_sw = len(sw_params.keys()) > 0
        has_res = len(res_params.keys()) > 0
        has_cap = len(cap_params.keys()) > 0

        ### Checking for common cases and possible user error
        if has_sw and has_res:
            warnings.warn('Feedback resistor and switch both present')

        if has_cap and not (has_res or has_sw):
            warnings.warn('Feedbcak has no DC path')

        ### Design elements
        # Feedback switch
        if not has_sw:
            self.delete_instance('XSW')
            self.remove_pin('RSTb')
            self.remove_pin('RST')
        else:
            self.instances['XSW'].design(**sw_params)
            # Delete unnecessary pins
            if sw_params['mos_type'] == 'n':
                self.remove_pin('RSTb')
            elif sw_params['mos_type'] == 'p':
                self.remove_pin('RST')

        # Feedback resistor
        if not has_res:
            self.delete_instance('XR')
        else:
            self.instances['XR'].design(**res_params)
            self.reconnect_instance_terminal('XR', 'BULK', res_bulk)

        # Feedback cap
        if not has_cap:
            self.delete_instance['XC']
        else:
            warnings.warn('Confirm cap value in generated schematic')
            self.instances['XC'].parameters = cap_params

        # Amp
        self.instances['XAMP'].design(**amp_params)

        # Biasing
        # self.instances['XBIAS'].design(**bias_params)