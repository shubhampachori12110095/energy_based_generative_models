import matplotlib.pyplot as plt
from pathlib import Path
import argparse
import os
import time
import numpy as np

import torch

from utils import save_samples_energies
from data.toy import inf_train_gen
from networks.toy import Generator, EnergyModel, StatisticsNetwork, Encoder
from train_functions import train_generator, train_energy_model


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--save_path', required=True)

    parser.add_argument('--input_dim', type=int, default=2)
    parser.add_argument('--z_dim', type=int, default=2)
    parser.add_argument('--dim', type=int, default=512)

    parser.add_argument('--energy_model_iters', type=int, default=5)
    parser.add_argument('--mcmc_iters', type=int, default=0)
    parser.add_argument('--lamda', type=float, default=.1)
    parser.add_argument('--alpha', type=float, default=.01)
    parser.add_argument('--score_coeff', type=float, default=0.)
    parser.add_argument('--entropy_coeff', type=float, default=1.)
    parser.add_argument('--clip_gradient', type=float, default=0.)

    parser.add_argument('--batch_size', type=int, default=256)
    parser.add_argument('--iters', type=int, default=100000)
    parser.add_argument('--n_points', type=int, default=1600)
    parser.add_argument('--log_interval', type=int, default=100)
    parser.add_argument('--save_interval', type=int, default=1000)

    args = parser.parse_args()
    return args


args = parse_args()
root = Path(args.save_path)

#################################################
# Create Directories
#################################################
if root.exists():
    os.system('rm -rf %s' % str(root))

os.makedirs(str(root))
os.system('mkdir -p %s' % str(root / 'models'))
os.system('mkdir -p %s' % str(root / 'images'))
#################################################

itr = inf_train_gen(args.dataset, args.batch_size)
netG = Generator(args.input_dim, args.z_dim, args.dim).cuda()
netE = EnergyModel(args.input_dim, args.dim).cuda()
netEnc = Encoder(args.input_dim, args.z_dim, args.dim).cuda()
netH = StatisticsNetwork(args.input_dim, args.z_dim, args.dim).cuda()

params = {'lr': 1e-4, 'betas': (0.5, 0.9)}
# params = {'lr': 2e-4}
optE = torch.optim.Adam(netE.parameters(), **params)
optEnc = torch.optim.Adam(netEnc.parameters(), **params)
optG = torch.optim.Adam(netG.parameters(), **params)
optH = torch.optim.Adam(netH.parameters(), **params)

#################################################
# Dump Original Data
#################################################
orig_data = itr.__next__()
plt.clf()
plt.scatter(orig_data[:, 0], orig_data[:, 1])
plt.savefig(root / 'images/orig.png')
##################################################

start_time = time.time()
costs = []
g_costs = []
for iters in range(args.iters):
    x_real = torch.from_numpy(itr.__next__()).cuda()
    train_generator(x_real, netEnc, netG, netE, netH, optEnc, optG, optH, args, g_costs)

    for j in range(args.energy_model_iters):
        x_real = torch.from_numpy(itr.__next__()).cuda()
        train_energy_model(x_real, netEnc, netG, netE, optE, args, costs)

    if iters % args.log_interval == 0:
        print('Train Iter: {}/{} ({:.0f}%)\t'
              'E_costs: {} G_costs: {} Time: {:5.3f}'.format(
                  iters, args.iters,
                  (args.log_interval * iters) / args.iters,
                  np.asarray(costs).mean(0),
                  np.asarray(g_costs).mean(0),
                  (time.time() - start_time) / args.log_interval
              ))
        save_samples_energies(netG, netE, args)

        costs = []
        g_costs = []
        start_time = time.time()

    if iters % args.save_interval == 0:
        torch.save(
            netG.state_dict(),
            root / 'models/netG.pt'
        )
        torch.save(
            netE.state_dict(),
            root / 'models/netE.pt'
        )
        torch.save(
            netH.state_dict(),
            root / 'models/netD.pt'
        )
        torch.save(
            netEnc.state_dict(),
            root / 'models/netEnc.pt'
        )
