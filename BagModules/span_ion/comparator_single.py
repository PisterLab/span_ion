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
            bits_inv_p = 'Number of PMOS control bits for the starved inverter',
            bits_inv_n = 'Number of NMOS control bits for the starved inverter',
            in_type = '"n" or "p" for the input pair type of the amplifier',
            amp_params = 'Parameters for the analog amplifier',
            constgm_params = 'Constant gm parameters',
            inv_params = 'Tunable resistor parameters',
            buf_params = 'Parameters for the tristate inverter chain'
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
        inv_params = params['inv_params']
        buf_params = params['buf_params']
        bits_inv_p = params['bits_inv_p']
        bits_inv_n = params['bits_inv_n']

        diff_out = buf_params['dual_output']
        num_inv = len(buf_params['inv_param_list'])

        assert bits_inv_p > 0, f'Number of PMOS bits {bits_inv_p} should be > 0'
        assert bits_inv_n > 0, f'Number of NMOS bits {bits_inv_n} should be > 0'
        assert in_type.lower() in ['p', 'n'], f'in_type must be p or n, not {in_type}'

        # Design components
        self.instances['XAMP'].design(in_type=in_type, **amp_params)
        self.instances['XCONSTGM'].design(**constgm_params)
        self.instances['XBUF'].design(**buf_params)

        ctrl_groups_p = [1] + [1<<i for i in range(bits_inv_p)]
        ctrl_groups_n = [1] + [1<<i for i in range(bits_inv_n)]
        self.instances['XINV'].design(ctrl_groups_p=ctrl_groups_p,
                                      ctrl_groups_n=ctrl_groups_n,
                                      **inv_params)

        # Adjust wiring
        if in_type.lower() == 'p':
            self.reconnect_instance_terminal('XAMP', 'VGTAIL', 'VGP')

        inv_bpb = f'bpb<{bits_inv_p}:0>'
        inv_bn = f'bn<{bits_inv_n}:0>'
        pin_bpb = f'bpb<{bits_inv_p-1}:0>'
        pin_bn = f'bn<{bits_inv_n-1}:0>'
        net_bpb = f'{pin_bpb},VSS'
        net_bn = f'{pin_bn},VDD'
        self.reconnect_instance_terminal('XINV', inv_bpb, net_bpb),
        self.reconnect_instance_terminal('XINV', inv_bn, net_bn)
        self.rename_pin('bpb', pin_bpb)
        self.rename_pin('bn', pin_bn)

        if not diff_out:
            pin_unused = 'out' if num_inv%2==0 else 'outb'
            self.remove_pin(pin_unused)