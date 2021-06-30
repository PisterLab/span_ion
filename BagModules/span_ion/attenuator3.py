# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module

# noinspection PyPep8Naming
class span_ion__attenuator3(Module):
    """Module for library span_ion cell attenuator3.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'attenuator3.yaml'))


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
            num_bits='Number of bits in the mux',
            mux_params='mux_bin parameters',
            rladder_params='rladder_core parameters'
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
        rladder_params = params['rladder_params']
        num_bits = params['num_bits']
        mux_params = params['mux_params']

        num_res = 1 << num_bits

        # Design instances
        rladder_params['num_out'] = num_res
        self.instances['XMUX'].design(num_bits=num_bits, **mux_params)
        self.instances['XLADDER'].design(**rladder_params)

        # Rewire mux
        suffix_mux = f'<{num_res - 1}:0>'
        mid_mux_net = f'VSIGNAL,mid<{num_res-1}:1>'
        self.reconnect_instance_terminal('XMUX', f'VIN{suffix_mux}', mid_mux_net)

        if num_bits > 1:
            sel_pin_net = f'S<{num_bits - 1}:0>'
            self.reconnect_instance_terminal('XMUX', sel_pin_net, sel_pin_net)
            self.rename_pin('S', sel_pin_net)

        # Rewire resistive ladder
        suffix_mid_res = f'<{num_res - 1}:0>'
        mid_net = f'mid{suffix_mid_res}'
        self.reconnect_instance_terminal('XLADDER', f'out{suffix_mid_res}', mid_net)