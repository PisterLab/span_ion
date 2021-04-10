# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_fd_cmfb(Module):
    """Module for library span_ion cell comparator_fd_cmfb.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_fd_cmfb.yaml'))


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
            lch_dict = 'Dictionary of channel lengths',
            wch_dict = 'Dictionary of channel widths',
            th_dict = 'Dictionary of device flavors',
            seg_dict = 'Dictionary of device segments',
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

        if in_type == 'n':
            lib_name = 'BAG_prim'
            p_name = 'pmos4_standard'
            n_name = 'nmos4_standard'
            n_vb = 'VSS'
            p_vb = 'VDD'
            inst_conn_dict = dict(XINNA=dict(D='VOUTP', G='VINNA', S='VTAIL', B=n_vb),
                                  XINNB=dict(D='VOUTP', G='VINNB', S='VTAIL', B=n_vb),
                                  XOUTP=dict(D='VOUTP', G='VOUTP', S=p_vb, B=p_vb),
                                  XINPA=dict(D='VOUTN', G='VINPA', S='VTAIL', B=n_vb),
                                  XINPB=dict(D='VOUTN', G='VINPB', S='VTAIL', B=n_vb),
                                  XOUTN=dict(D='VOUTN', G='VOUTN', S=p_vb, B=p_vb),
                                  XTAIL=dict(D='VTAIL', G='VGTAIL', S=n_vb, B=n_vb))
            inst_type_dict = dict(XINNA=n_name,
                                  XINNB=n_name,
                                  XINPA=n_name,
                                  XINPB=n_name,
                                  XOUTP=p_name,
                                  XOUTN=p_name,
                                  XTAIL=n_name)

            # Changing the input pair type
            for inst, ch_type in inst_type_dict.items():
                self.replace_instance_master(inst_name=inst,
                                             lib_name=lib_name,
                                             cell_name=ch_type)
                
                for pin, net in inst_conn_dict[inst].items():
                    self.reconnect_instance_terminal(inst, pin, net)

        # Design instances
        key_map = dict(XTAIL='tail',
                       XINPA='in',
                       XINPB='in',
                       XINNA='in',
                       XINNB='in',
                       XOUTN='out',
                       XOUTP='out')

        for name,dict_key in key_map.items():
            inst_params = dict(l=lch_dict[dict_key],
                               w=wch_dict[dict_key],
                               nf=seg_dict[dict_key],
                               intent=th_dict[dict_key])
            self.instances[name].design(**inst_params)