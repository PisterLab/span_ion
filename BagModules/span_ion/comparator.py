# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator(Module):
    """Module for library span_ion cell comparator.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator.yaml'))


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
            lch_dict = 'Dictionary of channel lengths.',
            wch_dict = 'Dictionary of channel widths.',
            seg_dict = 'Dictionary of number of fingers.',
            th_dict = 'Dictionary of device flavors.'
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
        seg_dict = params['seg_dict']
        th_dict = params['th_dict']

        diffpair_lch = {'in' : lch_dict['diff_in'],
                        'tail' : lch_dict['diff_tail']}
        diffpair_wch = {'in' : wch_dict['diff_in'],
                        'tail' : wch_dict['diff_tail']}
        diffpair_seg = {'in' : seg_dict['diff_in'],
                        'tail' : seg_dict['diff_tail']}
        diffpair_th = {'in' : th_dict['diff_in'],
                       'tail' : th_dict['diff_tail']}

        diffpair_params = {'lch_dict' : diffpair_lch,
                           'w_dict' : diffpair_wch,
                           'seg_dict' : diffpair_seg,
                           'th_dict' : diffpair_th}

        mirror_device_params = {'w' : wch_dict['mirror'],
                                'l' : lch_dict['mirror'],
                                'intent' : th_dict['mirror']}

        mirror_params = {'device_params' : mirror_device_params,
                         'seg_in' : seg_dict['mirror_in'],
                         'seg_out_list' : [seg_dict['mirror_out']]}

        src_params = {'l' : lch_dict['src'],
                      'w' : wch_dict['src'],
                      'nf' : seg_dict['src'],
                      'intent' : th_dict['src']}

        self.instances['XDIFFPAIR'].design(**diffpair_params)
        self.instances['XMIRR_A'].design(**mirror_params)
        self.instances['XMIRR_B'].design(**mirror_params)
        self.instances['XBIAS_A'].design(**src_params)
        self.instances['XBIAS_B'].design(**src_params)