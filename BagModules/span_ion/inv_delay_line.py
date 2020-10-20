# -*- coding: utf-8 -*-

from typing import Dict

import os
import pkg_resources

from bag.design.module import Module


# noinspection PyPep8Naming
class span_ion__inv_delay_line(Module):
    """Module for library span_ion cell inv_delay_line.

    A string of identical delay line units.
    """
    yaml_file = pkg_resources.resource_filename(__name__,
                                                os.path.join('netlist_info',
                                                             'inv_delay_line.yaml'))


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
            num_units = 'Number of units',
            export_mid = 'True to export the outputs of each unit',
            unit_params = 'inv_delay_line_unit parameters. All units are identical.'
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
        num_units = params['num_units']
        export_mid = params['export_mid']
        unit_params = params['unit_params']

        # Design instance
        self.instances['XDELAY'].design(**unit_params)

        # Wire up units together
        if num_units > 1:
            mid_suffix = f'<{num_units-2}:0>' if num_units > 2 else ''
            in_pin = ','.join(['in'] + [f'mid{mid_suffix}'])
            out_pin = ','.join([f'mid{mid_suffix}'] + ['out'])
            self.array_instance('XDELAY', [f'XDELAY<{num_units-1}:0>'], 
                                [{'VP': 'VP',
                                  'VN': 'VN',
                                  'in': in_pin,
                                  'out': out_pin}])
            if export_mid:
                self.rename_pin('mid', f'mid{mid_suffix}')

        # Pinout of the units
        if num_units < 2 or not export_mid:
            self.remove_pin('mid')
