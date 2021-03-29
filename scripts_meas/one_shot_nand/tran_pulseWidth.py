# -*- coding: utf-8 -*-

from bag.core import BagProject
from bag.simulation.core import DesignManager
import sys, pdb, traceback

if __name__ == '__main__':
    config_file = sys.argv[1]
    # config_file = 'specs_mos_char/nch_svt_w0d22_l0d18.yaml'
    print(f'Using yaml {sys.argv[1]}', flush=True)
    local_dict = locals()

    if 'bprj' not in local_dict:
        print('Creating BAG project', flush=True)
        bprj = BagProject()
    else:
        print('Loading BAG project', flush=True)
        bprj = local_dict['bprj']

    try:
        sim = DesignManager(bprj, config_file)
        sim.characterize_designs(generate=True, measure=True, load_from_file=False)
    except:
        extype, value, tb = sys.exc_info()
        traceback.print_exc()
        pdb.post_mortem(tb)