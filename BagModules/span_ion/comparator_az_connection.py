# -*- coding: utf-8 -*-

from typing import Dict, Mapping

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__comparator_az_connection(Module):
    """Module for library span_ion cell comparator_az_connection.

    Fill in high level description here.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'comparator_az_connection.yaml'))


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
            in_params = 'Input switch parameters',
            sample_params = 'Sample switch parameters',
            fb_params = 'Feedback switch parameters',
            cap_params = 'Capacitor parameters'
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
        in_params = params['in_params']
        sample_params = params['sample_params']
        fb_params = params['fb_params']
        cap_params = params['cap_params']

        # Designing instances
        name_map = dict(XIN=in_params,
                        XSAMPLE=sample_params,
                        XFB=fb_params)

        for name, device_params in name_map.items():
            self.instances[f'{name}A'].design(**device_params)
            self.instances[f'{name}B'].design(**device_params)

        self.instances['XCAPA'].parameters = cap_params
        self.instances['XCAPB'].parameters = cap_params

        print('*** WARNING *** (comparator_az_connection) double check passive values in generated schematic')

        # Removing pins as necessary
        in_type = in_params['mos_type']
        sample_type = sample_params['mos_type']
        fb_type = fb_params['mos_type']
        pin_needs = dict(PHI=(in_type != 'p' or sample_type != 'n'),
                         PHIb=(in_type != 'n' or sample_type != 'p'),
                         PHI_EARLY=(fb_type != 'p'),
                         PHI_EARLYb=(fb_type != 'n'))

        for pin,needed in pin_needs.items():
            if not needed:
                self.remove_pin(pin)