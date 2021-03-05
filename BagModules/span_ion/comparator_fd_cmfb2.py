# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_cmfb2(Module):
    """Module for library span_ion cell comparator_fd_cmfb2.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_cmfb2.yaml'))


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
            in_type = 'p or n for input pair type',
            lch_dict = 'Dictionary of channel lengths. in, load, out, tail',
            wch_dict = 'Dictionary of channel widths',
            th_dict = 'Dictionary of device flavors',
            seg_dict = 'Dictionary of device segments. Add load_copy to keys',
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
        lch_dict = params['lch_dict']
        wch_dict = params['wch_dict']
        th_dict = params['th_dict']
        seg_dict = params['seg_dict']

        assert in_type in ('n', 'p'), f'in_type {in_type} must be n or p'
        
        ### Make NMOS input if necessary
        if in_type == 'n':
            # Individual transistors
            lib_name = 'BAG_prim'
            n_name = 'nmos4_standard'
            n_vb = 'VSS'

            inst_conn_dict = dict(XINNA=dict(D='VOUT1P', S='VTAIL', G='VINNA', B=n_vb),
                                  XINNB=dict(D='VOUT1P', S='VTAIL', G='VINNB', B=n_vb),
                                  XINPA=dict(D='VOUT1N', S='VTAIL', G='VINPA', B=n_vb),
                                  XINPB=dict(D='VOUT1N', S='VTAIL', G='VINPB', B=n_vb),
                                  XTAIL=dict(D='VTAIL', S=n_vb, G='VGTAIL', B=n_vb),
                                  XOUTN=dict(D='VOUTN', S=n_vb, G='VOUTN', B=n_vb),
                                  XOUTP=dict(D='VOUTP', S=n_vb, G='VOUTP', B=n_vb))

            for inst, conn_dict in inst_conn_dict.items():
                self.replace_instance_master(inst_name=inst,
                                             lib_name=lib_name,
                                             cell_name=n_name)
                
                for pin, net in conn_dict.items():
                    self.reconnect_instance_terminal(inst, pin, net)

            # Mirrors
            for inst_type in ('P', 'N'):
                inst_name = f'XOUT1{inst_type}'
                other_type = 'P' if inst_type == 'N' else 'N'
                self.replace_instance_master(inst_name=inst_name,
                                             lib_name='bag2_analog',
                                             cell_name='mirror_p')
                self.reconnect_instance_terminal(inst_name, 'in', f'VOUT1{inst_type}')
                self.reconnect_instance_terminal(inst_name, 'out', f'VOUT{other_type}')
                self.reconnect_instance_terminal(inst_name, 'VDD', 'VDD')
                self.reconnect_instance_terminal(inst_name, 's_in', 'VDD')
                self.reconnect_instance_terminal(inst_name, 's_out', 'VDD')

        ### Design instances
        # Individual transistors
        key_map = dict(XINNA='in',
                       XINNB='in',
                       XINPA='in',
                       XINPB='in',
                       XTAIL='tail',
                       XOUTP='out',
                       XOUTN='out')

        for name, dict_key in key_map.items():
            inst_params = dict(l=lch_dict[dict_key],
                               w=wch_dict[dict_key],
                               nf=seg_dict[dict_key],
                               intent=th_dict[dict_key])
            self.instances[name].design(**inst_params)

        # Mirrors
        mirr_device_params = dict(w=wch_dict['load'],
                                  l=lch_dict['load'],
                                  intent=th_dict['load'])

        mirr_params = dict(device_params=mirr_device_params,
                           seg_in=seg_dict['load'],
                           seg_out_list=[seg_dict['load_copy']])
        self.instances['XOUT1P'].design(**mirr_params)
        self.instances['XOUT1N'].design(**mirr_params)