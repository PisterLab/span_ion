# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_single(Module):
    """Module for library span_ion cell comparator_single.

    Comparator is a differential-in single-out amplifier 
    followed by a string of inverters for digitization.
    This does not use any kind of positive feedback, since
    for this project there is no clock for a reset phase and
    hysteresis is exceptionally bad in this case.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_single.yaml'))


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
            in_type = '"n" or "p" for the input pair type of the amplifier',
            amp_params = 'Parameters for the analog amplifier',
            constgm_params = 'Constant gm parameters',
            buf_params = 'Parameters for the inverter chain'
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
        in_type = params['in_type']
        amp_params = params['amp_params']
        constgm_params = params['constgm_params']
        buf_params = params['buf_params']

        diff_out = buf_params['dual_output']
        num_inv = len(buf_params['inv_param_list'])

        assert in_type.lower() in ['p', 'n'], f'in_type must be p or n, not {in_type}'

        # Design components
        self.instances['XAMP'].design(in_type=in_type, **amp_params)
        self.instances['XCONSTGM'].design(**constgm_params)
        self.instances['XBUF'].design(**buf_params)

        # Adjust wiring
        if in_type.lower() == 'p':
            self.reconnect_instance_terminal('XAMP', 'VGTAIL', 'VP')

        if not diff_out:
            pin_unused = 'out' if num_inv%2==1 else 'outb'
            self.remove_pin(pin_unused)