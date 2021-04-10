# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_main2(Module):
    """Module for library span_ion cell comparator_fd_main2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_main2.yaml'))


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
            in_type = '"p" or "n" for NMOS or PMOS input pair',
            l_dict = 'Channel and resistor lengths',
            w_dict = 'Channel and resistor widths',
            th_dict = 'Device and resistor flavors',
            seg_dict = 'Device and resistor number of devices',
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
        l_dict = params['l_dict']
        w_dict = params['w_dict']
        th_dict = params['th_dict']
        seg_dict = params['seg_dict']

        # Design instances
        if in_type == 'p':
            self.replace_instance_master(inst_name='XDIFFPAIR',
                                         lib_name='bag2_analog',
                                         cell_name='diffpair_p')
            self.replace_instance_master(inst_name='XLOADP',
                                         lib_name='BAG_prim',
                                         cell_name=f'nmos4_{th_dict["load"]}')
            self.replace_instance_master(inst_name='XLOADN',
                                         lib_name='BAG_prim',
                                         cell_name=f'nmos4_{th_dict["load"]}')

            # Reconnect replaced devices
            diffpair_conn = dict(VDD='VDD',
                                 VINP='VINP',
                                 VINN='VINN',
                                 VOUTP='VOUTP',
                                 VOUTN='VOUTN',
                                 VGTAIL='VGTAIL')

            for pin, net in diffpair_conn.items():
                self.reconnect_instance_terminal('XDIFFPAIR', pin, net)

            for side in ('N', 'P'):
                self.reconnect_instance_terminal(f'XLOAD{side}', 'S', 'VSS')
                self.reconnect_instance_terminal(f'XLOAD{side}', 'D', f'VOUT{side}')
                self.reconnect_instance_terminal(f'XLOAD{side}', 'B', 'VSS')
                self.reconnect_instance_terminal(f'XLOAD{side}', 'G', 'VCMFB')

        self.instances['XDIFFPAIR'].design(lch_dict=l_dict,
                                           w_dict=w_dict,
                                           seg_dict=seg_dict,
                                           th_dict=th_dict)

        self.instances['XLOADN'].design(w=w_dict['load'],
                                        l=l_dict['load'],
                                        intent=th_dict['load'],
                                        nf=seg_dict['load'])

        self.instances['XLOADP'].design(w=w_dict['load'],
                                        l=l_dict['load'],
                                        intent=th_dict['load'],
                                        nf=seg_dict['load'])