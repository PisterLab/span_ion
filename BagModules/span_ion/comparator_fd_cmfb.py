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
        lch_dict = params['lch_dict']
        wch_dict = params['wch_dict']
        th_dict = params['th_dict']
        seg_dict = params['seg_dict']

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