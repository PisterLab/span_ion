# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources
import numpy as np

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__dac_offset(Module):
    """Module for library span_ion cell dac_offset.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'dac_offset.yaml'))


    def __init__(self, database, parent=None, prj=None, **kwargs):
        Module.__init__(self, database, self.yaml_file, parent=parent, prj=prj, **kwargs)

    @classmethod
    def get_params_info(cls):
        # type: () -> Dict[str, str]
        """Returns a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Optional[Dict[str, str]]
            dictionary from parameter names to descriptions.
        """
        return dict(
            in_type = "n or p. NMOS or PMOS devices.",
            mirr_params = "mirr_n or mirr_p parameters.",
            diffpair_params = "diffpair_n or diffpair_p parameters.",
            en_params = "Enable/disable switch parameters"
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
        mirr_params = params['mirr_params']
        diffpair_params = params['diffpair_params']
        en_params = params['en_params']

        dac_groups_list = mirr_params['seg_out_list']
        num_bits = len(mirr_params['seg_out_list'])
        suffix_bits = '' if num_bits <= 1 else f'<{num_bits-1}:0>'


        if in_type.lower() == 'p':
            # Replace masters for mirror, enable, and diffpair
            self.replace_instance_master(inst_name='XDIFFPAIR',
                                         lib_name='bag2_analog',
                                         cell_name='diffpair_p')

            self.replace_instance_master(inst_name='XEN',
                                         lib_name='BAG_prim',
                                         cell_name='pmos4_standard')

            self.replace_instance_master(inst_name='XMIRR',
                                         lib_name='bag2_analog',
                                         cell_name='mirror_p')

            # Connect them as necessary
            diffpair_conn = dict(VINP='PULLAb',
                                 VINN='PULLBb',
                                 VOUTP='VOUTB',
                                 VOUTN='VOUTA',
                                 VTAIL='VTAIL',
                                 VDD='VDD')

            en_conn = dict(S=f'VDAC',
                           D='VTAIL',
                           G=f'Bb',
                           B='VDD')

            mirr_conn = {'in' : 'IREF',
                         'out' : f'VDAC{suffix_bits}',
                         's_in' : 'VDD',
                         's_out' : 'VDD',
                         'VDD' : 'VDD'}

            for pin, net in diffpair_conn.items():
                self.reconnect_instance_terminal('XDIFFPAIR', pin, net)

            for pin, net in en_conn.items():
                self.reconnect_instance_terminal('XEN', pin, net)

            for pin, net in mirr_conn.items():
                self.reconnect_instance_terminal('XMIRR', pin, net)

            # Rename pins as necessary
            self.rename_pin('B', f'Bb{suffix_bits}')
            self.rename_pin('PULLA', 'PULLAb')
            self.rename_pin('PULLB', 'PULLBb')
            self.remove_pin('VSS')
        else:
            en_conn = dict(D='VTAIL',
                           G=f'B{suffix_bits}',
                           B='VSS')
            self.remove_pin('VDD')
            if num_bits > 1:
                self.rename_pin('B', f'B{suffix_bits}')

        if num_bits > 1:
            g_base = 'Bb' if in_type=='p' else 'B'
            self.array_instance('XEN', [f'XEN<{i}>' for i in range(num_bits)], [dict(S=f'VDAC<{i}>',
                                                                                     D='VTAIL',
                                                                                     G=f'{g_base}<{i}>',
                                                                                     B='VSS') for i in range(num_bits)])
            for i in range(num_bits):
                en_params_cut = dict(en_params)
                en_params_cut['nf'] = en_params_cut['nf']*dac_groups_list[i]
                self.instances['XEN'][i].design(**en_params_cut)
            self.reconnect_instance_terminal('XMIRR', f's_out{suffix_bits}', 'VDD' if in_type.lower() == 'p' else 'VSS')
            self.reconnect_instance_terminal('XMIRR', f'out{suffix_bits}', f'VDAC{suffix_bits}')
        else:
            self.instances['XEN'].design(**en_params)

        # Design instances
        self.instances['XDIFFPAIR'].design(**diffpair_params)
        self.instances['XMIRR'].design(**mirr_params)